"""Deterministic merge of multi-page Vision partial extractions before LLM merge."""

from __future__ import annotations

from dataclasses import dataclass

from config import settings
from core.debug_logger import debug_trace, get_logger
from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService

logger = get_logger(__name__)

FIRST_PREFER_FIELDS = (
    "name_of_company",
    "address_of_company",
    "invoice_number",
    "invoice_date",
    "client_employee_related",
)

LAST_PREFER_FIELDS = (
    "amount",
    "debt",
    "currency",
    "account_details",
    "category",
)

OPTIONAL_LAST_FIELDS = ("internal_note_description",)

CRITICAL_CONFLICT_FIELDS = ("invoice_number", "invoice_date")


@dataclass(frozen=True)
class DeterministicMergeOutcome:
    result: ExtractionResult | None
    use_llm: bool
    strategy: str
    conflicts: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    confidence: float = 0.0

    def metadata(self) -> dict[str, object]:
        return {
            "merge_strategy": self.strategy,
            "deterministic_merge_conflicts": list(self.conflicts),
            "deterministic_merge_missing_fields": list(self.missing_fields),
        }


class DeterministicPartialMergeService:
    def __init__(
        self,
        ai_validation: AIValidationService | None = None,
    ) -> None:
        self._ai_validation = ai_validation or AIValidationService()

    @debug_trace
    def merge_partials(
        self,
        partials: list[ExtractionResult],
    ) -> DeterministicMergeOutcome:
        if not partials:
            return DeterministicMergeOutcome(
                result=None,
                use_llm=True,
                strategy="llm",
                conflicts=("no_partials",),
            )
        if len(partials) == 1:
            single = self._ai_validation.sanitize_and_validate(partials[0])
            return DeterministicMergeOutcome(
                result=single,
                use_llm=False,
                strategy="deterministic",
                confidence=single.confidence_score,
            )

        if not settings.openai_deterministic_merge_enabled:
            return DeterministicMergeOutcome(
                result=None,
                use_llm=True,
                strategy="llm",
                conflicts=("disabled",),
            )

        conflicts: list[str] = []
        unresolved_critical: list[str] = []

        merged: dict[str, object] = {}

        for field_name in FIRST_PREFER_FIELDS:
            merged[field_name] = self._first_non_empty(partials, field_name)
            conflict = self._detect_field_conflict(partials, field_name, prefer="first")
            if conflict:
                conflicts.append(conflict)
                if field_name in CRITICAL_CONFLICT_FIELDS:
                    unresolved_critical.append(conflict)

        for field_name in LAST_PREFER_FIELDS:
            merged[field_name] = self._last_non_empty(partials, field_name)
            conflict = self._detect_field_conflict(partials, field_name, prefer="last")
            if conflict:
                conflicts.append(conflict)
                if field_name == "amount":
                    # Totals on later pages win — not an LLM trigger.
                    pass

        merged["internal_note_description"] = self._merge_line_descriptions(partials)
        merged["document_type"] = self._first_non_empty(partials, "document_type")
        merged["field_confidences"] = self._merge_field_confidences(partials)
        merged["review_reasons"] = self._merge_review_reasons(partials)
        merged["needs_review"] = any(p.needs_review for p in partials)
        merged["confidence_score"] = self._merge_confidence(partials)

        try:
            result = ExtractionResult.model_validate(merged)
            result = self._ai_validation.sanitize_and_validate(result)
        except Exception as exc:
            logger.info("Deterministic merge produced invalid result: %s", exc)
            return DeterministicMergeOutcome(
                result=None,
                use_llm=True,
                strategy="llm",
                conflicts=tuple(conflicts + [f"invalid_merge:{exc}"]),
            )

        missing = self._ai_validation.validate_required_fields(result)
        suspicious = self._ai_validation.detect_suspicious_values(result)
        confidence = float(result.confidence_score)

        use_llm = bool(unresolved_critical) or bool(missing) or bool(suspicious)
        if confidence < settings.openai_deterministic_merge_min_confidence:
            use_llm = True
            conflicts.append("low_confidence")

        if use_llm:
            return DeterministicMergeOutcome(
                result=result,
                use_llm=True,
                strategy="llm",
                conflicts=tuple(conflicts),
                missing_fields=tuple(missing),
                confidence=confidence,
            )

        return DeterministicMergeOutcome(
            result=result,
            use_llm=False,
            strategy="deterministic",
            conflicts=tuple(conflicts),
            missing_fields=tuple(missing),
            confidence=confidence,
        )

    def _first_non_empty(
        self,
        partials: list[ExtractionResult],
        field_name: str,
    ) -> object | None:
        for partial in partials:
            value = getattr(partial, field_name, None)
            if value is not None and value != "":
                return value
        return None

    def _last_non_empty(
        self,
        partials: list[ExtractionResult],
        field_name: str,
    ) -> object | None:
        for partial in reversed(partials):
            value = getattr(partial, field_name, None)
            if value is not None and value != "":
                return value
        return None

    def _merge_line_descriptions(
        self,
        partials: list[ExtractionResult],
    ) -> str | None:
        seen: set[str] = set()
        lines: list[str] = []
        for partial in partials:
            raw = partial.internal_note_description
            if not raw:
                continue
            for chunk in str(raw).splitlines():
                text = chunk.strip()
                if not text:
                    continue
                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)
                lines.append(text)
        return "\n".join(lines) if lines else None

    def _merge_field_confidences(
        self,
        partials: list[ExtractionResult],
    ) -> dict[str, float] | None:
        merged: dict[str, float] = {}
        for partial in partials:
            if not partial.field_confidences:
                continue
            for key, value in partial.field_confidences.items():
                try:
                    score = float(value)
                except (TypeError, ValueError):
                    continue
                merged[key] = max(merged.get(key, 0.0), score)
        return merged or None

    def _merge_review_reasons(
        self,
        partials: list[ExtractionResult],
    ) -> list[str]:
        reasons: list[str] = []
        seen: set[str] = set()
        for partial in partials:
            for reason in partial.review_reasons or []:
                if reason not in seen:
                    seen.add(reason)
                    reasons.append(reason)
        return reasons

    def _merge_confidence(self, partials: list[ExtractionResult]) -> float:
        scores = [float(p.confidence_score) for p in partials if p.confidence_score]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 3)

    def _detect_field_conflict(
        self,
        partials: list[ExtractionResult],
        field_name: str,
        *,
        prefer: str,
    ) -> str | None:
        values = [
            getattr(p, field_name)
            for p in partials
            if getattr(p, field_name, None) not in (None, "")
        ]
        if len(values) < 2:
            return None

        if field_name == "invoice_number":
            cleaned = {
                self._ai_validation._clean_invoice_number(str(v)) for v in values
            }
            cleaned.discard(None)
            cleaned.discard("")
            if len(cleaned) > 1:
                return f"invoice_number_conflict:{sorted(cleaned)}"

        if field_name == "invoice_date":
            normalized = {
                self._ai_validation._normalize_date(str(v)) for v in values
            }
            normalized.discard(None)
            normalized.discard("")
            if len(normalized) > 1:
                return f"invoice_date_conflict:{sorted(normalized)}"

        if field_name == "amount":
            amounts = [self._ai_validation._normalize_amount(v) for v in values]
            amounts = [a for a in amounts if a is not None]
            if len(amounts) >= 2 and max(amounts) - min(amounts) > 0.02:
                return f"amount_conflict:{amounts}"

        if field_name == "name_of_company":
            if self._company_names_low_risk_conflict(values):
                return None
            return f"name_of_company_conflict:{values[:2]}"

        if field_name in {"address_of_company", "client_employee_related", "category"}:
            return None

        if prefer == "first":
            first = values[0]
            if any(str(v).strip() != str(first).strip() for v in values[1:]):
                return f"{field_name}_conflict"
        return None

    def _company_names_low_risk_conflict(self, values: list[object]) -> bool:
        normalized = [str(v).strip().lower() for v in values]
        if len(normalized) < 2:
            return True
        first = normalized[0]
        return all(first in other or other in first for other in normalized[1:])
