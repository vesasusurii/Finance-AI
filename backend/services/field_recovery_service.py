"""Focused second-pass extraction for missing critical fields."""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING

from core.debug_logger import debug_trace, get_logger
from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from utils.openai_chat import chat_completion_kwargs

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = get_logger(__name__)

CRITICAL_FIELDS = (
    "invoice_number",
    "invoice_date",
    "amount",
    "name_of_company",
)

_FIELD_PROMPTS: dict[str, str] = {
    "invoice_number": (
        "Extract ONLY `invoice_number` from the HEADER area of this invoice. "
        "Look for INVOICE ###, FATURA - INVOICE ####, Numri i faturës, Belegnummer. "
        "Never return fiscal numbers, IBANs, or bank accounts. "
        'Return JSON: {"invoice_number": "..."} or null if not found.'
    ),
    "invoice_date": (
        "Extract ONLY `invoice_date` in YYYY-MM-DD format from the invoice header. "
        "Use issue date, not due date. "
        'Return JSON: {"invoice_date": "YYYY-MM-DD"} or null.'
    ),
    "amount": (
        "Extract ONLY the final payable `amount` (with VAT / grand total). "
        "Use Vlera me TVSH, Total Amount Due, Bruttobetrag, Gjithësejt vlerat — "
        "NOT sub-totals or line items. "
        'Return JSON: {"amount": 123.45} or null.'
    ),
    "name_of_company": (
        "Extract ONLY the issuer/supplier `name_of_company` (NOT the buyer/client). "
        "On Albanian invoices the buyer is at top — skip it; use the supplier near FATURA title. "
        'Return JSON: {"name_of_company": "..."} or null.'
    ),
}


class FieldRecoveryService:
    def __init__(
        self,
        openai_client: AsyncOpenAI | None,
        ai_validation: AIValidationService | None = None,
    ) -> None:
        self._openai = openai_client
        self._ai_validation = ai_validation or AIValidationService()

    @debug_trace
    async def recover_missing_fields(
        self,
        result: ExtractionResult,
        *,
        images: list[tuple[bytes, str]],
        model: str,
        filename: str,
    ) -> ExtractionResult:
        """Run focused Vision passes for each missing critical field."""
        if self._openai is None:
            return result

        missing = self._ai_validation.validate_required_fields(result)
        if not missing or not images:
            return result

        data = result.model_dump()
        recovered: list[str] = []

        # Use first page for header fields; last page for amount on multi-page docs
        header_image = images[0]
        totals_image = images[-1] if len(images) > 1 else images[0]

        for field in missing:
            target_images = (
                [totals_image] if field == "amount" and len(images) > 1 else [header_image]
            )
            value = await self._recover_field(
                field,
                images=target_images,
                model=model,
                filename=filename,
            )
            if value is not None:
                data[field] = value
                recovered.append(field)

        if recovered:
            logger.info(
                "Field recovery for %s succeeded: %s",
                filename,
                ", ".join(recovered),
            )
            return self._ai_validation.sanitize_and_validate(
                ExtractionResult.model_validate(data)
            )
        return result

    async def _recover_field(
        self,
        field: str,
        *,
        images: list[tuple[bytes, str]],
        model: str,
        filename: str,
    ) -> object | None:
        prompt = _FIELD_PROMPTS[field]
        user_content: list[dict] = [
            {"type": "text", "text": f"Document: {filename}\n\n{prompt}"},
        ]
        for img_bytes, mime in images:
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

        try:
            response = await self._openai.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise invoice field extractor. JSON only.",
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
            return payload.get(field)
        except Exception as exc:
            logger.warning("Field recovery failed for %s on %s: %s", field, filename, exc)
            return None
