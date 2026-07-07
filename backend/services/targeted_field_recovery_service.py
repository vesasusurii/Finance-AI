"""Targeted single-call recovery for a small number of missing invoice fields."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from config import settings
from core.debug_logger import debug_trace, get_logger
from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from utils.openai_chat import chat_completion_kwargs

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = get_logger(__name__)

TARGETABLE_FIELDS: tuple[str, ...] = (
    "invoice_number",
    "invoice_date",
    "amount",
    "currency",
    "account_details",
    "debt",
)

_HEADER_FIELDS = frozenset({"invoice_number", "invoice_date", "currency"})
_PAYMENT_FIELDS = frozenset({"amount", "account_details", "debt"})

_FIELD_HINTS: dict[str, str] = {
    "invoice_number": "Invoice number from the header (not IBAN or tax ID).",
    "invoice_date": "Issue date in YYYY-MM-DD (not due date).",
    "amount": "Final payable grand total with VAT (not subtotal or line items).",
    "currency": "Three-letter currency code such as EUR or USD.",
    "account_details": "IBAN or bank account for payment.",
    "debt": "Amount due / balance payable if shown separately from total.",
}


@dataclass(frozen=True)
class TargetedRecoveryOutcome:
    result: ExtractionResult
    metadata: dict[str, object]


class TargetedFieldRecoveryService:
    """Recover 1–2 missing critical fields with one small Vision call."""

    def __init__(
        self,
        openai_client: AsyncOpenAI | None,
        ai_validation: AIValidationService | None = None,
    ) -> None:
        self._openai = openai_client
        self._ai_validation = ai_validation or AIValidationService()

    @staticmethod
    def _empty_metadata() -> dict[str, object]:
        return {
            "targeted_recovery_used": False,
            "targeted_recovery_fields": [],
            "targeted_recovery_ms": None,
            "targeted_recovery_openai_calls": 0,
            "targeted_recovery_success": False,
        }

    @staticmethod
    def missing_targetable_fields(result: ExtractionResult) -> list[str]:
        missing: list[str] = []
        if not result.invoice_number:
            missing.append("invoice_number")
        if not result.invoice_date:
            missing.append("invoice_date")
        if result.amount is None:
            missing.append("amount")
        if not result.currency:
            missing.append("currency")
        if not result.account_details:
            missing.append("account_details")
        if result.debt is None:
            missing.append("debt")
        return missing

    def should_attempt(
        self,
        result: ExtractionResult,
        *,
        images: list[tuple[bytes, str]],
    ) -> tuple[bool, list[str]]:
        if not settings.openai_targeted_field_recovery_enabled:
            return False, []
        if settings.openai_field_recovery_enabled:
            return False, []
        if not images or self._openai is None:
            return False, []

        missing_required = self._ai_validation.validate_required_fields(result)
        missing_targetable = self.missing_targetable_fields(result)
        max_fields = max(1, settings.openai_targeted_field_recovery_max_fields)
        min_confidence = settings.openai_targeted_field_recovery_min_confidence

        if not missing_required:
            return False, []
        if len(missing_required) > max_fields:
            return False, []
        if result.confidence_score < min_confidence:
            return False, []

        priority = [
            field
            for field in missing_targetable
            if field in missing_required and field in TARGETABLE_FIELDS
        ]
        fields = priority[:max_fields]
        if not fields:
            return False, []
        return True, fields

    @debug_trace
    async def recover_missing_fields(
        self,
        result: ExtractionResult,
        *,
        images: list[tuple[bytes, str]],
        model: str,
        filename: str,
    ) -> TargetedRecoveryOutcome:
        meta = self._empty_metadata()
        should_run, fields = self.should_attempt(result, images=images)
        if not should_run:
            return TargetedRecoveryOutcome(result=result, metadata=meta)

        selected_images = self._select_images(fields, images)
        prompt = self._build_prompt(fields)
        t0 = time.perf_counter()
        payload = await self._call_openai(
            fields=fields,
            prompt=prompt,
            images=selected_images,
            model=model,
            filename=filename,
        )
        meta["targeted_recovery_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        meta["targeted_recovery_openai_calls"] = 1
        meta["targeted_recovery_used"] = True
        meta["targeted_recovery_fields"] = fields

        if not payload:
            logger.info(
                "Targeted field recovery failed for %s (fields=%s)",
                filename,
                fields,
            )
            failed = result.model_copy(
                update={
                    "needs_review": True,
                    "review_reasons": [
                        *result.review_reasons,
                        "targeted_recovery_failed",
                    ],
                }
            )
            return TargetedRecoveryOutcome(result=failed, metadata=meta)

        merged = self._merge_recovered(result, payload, fields)
        merged = self._ai_validation.sanitize_and_validate(merged)
        recovered = [
            field
            for field in fields
            if self._field_present(merged, field)
            and not self._field_present(result, field)
        ]
        meta["targeted_recovery_success"] = bool(recovered)
        if not recovered:
            merged = merged.model_copy(
                update={
                    "needs_review": True,
                    "review_reasons": [
                        *merged.review_reasons,
                        "targeted_recovery_failed",
                    ],
                }
            )
        else:
            logger.info(
                "Targeted field recovery for %s succeeded: %s",
                filename,
                ", ".join(recovered),
            )
        return TargetedRecoveryOutcome(result=merged, metadata=meta)

    @staticmethod
    def _field_present(result: ExtractionResult, field: str) -> bool:
        value = getattr(result, field)
        if field in {"amount", "debt"}:
            return value is not None
        return bool(value)

    @staticmethod
    def _select_images(
        fields: list[str],
        images: list[tuple[bytes, str]],
    ) -> list[tuple[bytes, str]]:
        if len(images) == 1:
            return images

        needs_header = any(field in _HEADER_FIELDS for field in fields)
        needs_payment = any(field in _PAYMENT_FIELDS for field in fields)
        selected: list[tuple[bytes, str]] = []

        if needs_header:
            selected.append(images[0])
        if needs_payment:
            last = images[-1]
            if last not in selected:
                selected.append(last)
        if not selected:
            selected = [images[0]]
        return selected

    @staticmethod
    def _build_prompt(fields: list[str]) -> str:
        lines = [
            "Extract ONLY the missing invoice fields listed below.",
            "Return one JSON object containing just those keys.",
            "Use null for any field you cannot find.",
            "",
            "Missing fields:",
        ]
        for field in fields:
            lines.append(f"- {field}: {_FIELD_HINTS[field]}")
        lines += [
            "",
            "Use the first page image for header fields.",
            "Use the final page image for totals, IBAN, and payment fields.",
        ]
        return "\n".join(lines)

    async def _call_openai(
        self,
        *,
        fields: list[str],
        prompt: str,
        images: list[tuple[bytes, str]],
        model: str,
        filename: str,
    ) -> dict[str, Any] | None:
        user_content: list[dict] = [
            {"type": "text", "text": f"Document: {filename}\n\n{prompt}"},
        ]
        for index, (img_bytes, mime) in enumerate(images, start=1):
            role = "header page" if index == 1 and len(images) > 1 else "payment page"
            if len(images) == 1:
                role = "invoice page"
            user_content.append({"type": "text", "text": f"─── {role} ───"})
            b64 = base64.standard_b64encode(img_bytes).decode("ascii")
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime};base64,{b64}",
                        "detail": "high",
                    },
                }
            )

        schema_hint = ", ".join(f'"{field}": ...' for field in fields)
        try:
            response = await self._openai.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You recover missing invoice fields. "
                            f"Return JSON only, e.g. {{{schema_hint}}}."
                        ),
                    },
                    {"role": "user", "content": user_content},
                ],
                **chat_completion_kwargs(
                    model,
                    max_output_tokens=256,
                    temperature=0,
                    response_format={"type": "json_object"},
                ),
            )
            raw = (response.choices[0].message.content or "{}").strip()
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return None
            return payload
        except Exception as exc:
            logger.warning(
                "Targeted field recovery OpenAI call failed for %s: %s",
                filename,
                exc,
            )
            return None

    @staticmethod
    def _merge_recovered(
        result: ExtractionResult,
        payload: dict[str, Any],
        fields: list[str],
    ) -> ExtractionResult:
        data = result.model_dump()
        for field in fields:
            if field not in payload:
                continue
            value = payload[field]
            if value is None or value == "":
                continue
            if field in {"amount", "debt"}:
                try:
                    data[field] = float(value)
                except (TypeError, ValueError):
                    continue
            else:
                data[field] = str(value).strip()
        return ExtractionResult.model_validate(data)
