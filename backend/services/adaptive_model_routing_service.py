"""Adaptive OpenAI model selection — fast by default, strong only when needed."""

from __future__ import annotations

from dataclasses import dataclass

from config import settings
from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from services.deterministic_partial_merge_service import CRITICAL_CONFLICT_FIELDS

VISION_RETRY_CONFIDENCE = 0.82

_UTILITY_CATEGORIES = frozenset({"utility"})


@dataclass(frozen=True)
class ModelRoutingDecision:
    model_strategy: str
    model_used: str | None
    fallback_model_used: str | None = None
    fallback_reason: str | None = None
    strong_model_openai_calls: int = 0

    def metadata(self) -> dict[str, object]:
        return {
            "model_strategy": self.model_strategy,
            "model_used": self.model_used,
            "fallback_model_used": self.fallback_model_used,
            "fallback_reason": self.fallback_reason,
            "strong_model_openai_calls": self.strong_model_openai_calls,
        }


class AdaptiveModelRoutingService:
    """Route extraction workloads to fast or strong OpenAI models."""

    def __init__(
        self,
        ai_validation: AIValidationService | None = None,
    ) -> None:
        self._ai_validation = ai_validation or AIValidationService()

    @staticmethod
    def adaptive_enabled() -> bool:
        return settings.openai_adaptive_model_routing_enabled

    def fast_model(self) -> str:
        if self.adaptive_enabled():
            return settings.openai_fast_model
        return settings.openai_model

    def strong_model(self) -> str:
        return settings.openai_model_strong

    @staticmethod
    def strategy_for_mode(mode: str) -> str:
        if mode == "text_hints":
            return "none"
        if mode == "text_llm":
            return "fast_text"
        if mode == "targeted_recovery":
            return "fast_vision"
        return "fast_vision"

    def primary_metadata(self, *, mode: str, model_used: str | None) -> dict[str, object]:
        return ModelRoutingDecision(
            model_strategy=self.strategy_for_mode(mode),
            model_used=model_used,
            strong_model_openai_calls=0,
        ).metadata()

    def should_use_strong_fallback(
        self,
        result: ExtractionResult,
        meta: dict,
    ) -> tuple[bool, list[str]]:
        if not settings.openai_strong_retry_enabled:
            return False, []
        if self.strong_model() == self.fast_model():
            return False, []

        mode = str(meta.get("extraction_mode", ""))
        if mode.startswith("text_"):
            return False, []

        if meta.get("targeted_recovery_success"):
            return False, []

        missing = self._ai_validation.validate_required_fields(result)
        suspicious = self._ai_validation.detect_suspicious_values(result)
        merge_strategy = meta.get("merge_strategy")
        merge_conflicts = meta.get("deterministic_merge_conflicts") or []
        critical_conflicts = [
            field
            for field in merge_conflicts
            if field in CRITICAL_CONFLICT_FIELDS
        ]

        if (
            merge_strategy == "deterministic"
            and not missing
            and not critical_conflicts
        ):
            return False, []

        reasons: list[str] = []

        if missing:
            if meta.get("targeted_recovery_used") and not meta.get(
                "targeted_recovery_success"
            ):
                reasons.append("targeted_recovery_failed")
            for field in missing:
                reasons.append(f"missing_{field}")

        if critical_conflicts:
            for field in critical_conflicts:
                reasons.append(f"critical_conflict:{field}")

        if self._utility_parse_failed(result, meta, missing):
            reasons.append("utility_parse_failure")

        if (
            result.confidence_score < VISION_RETRY_CONFIDENCE
            and missing
        ):
            reasons.append(
                f"low_confidence:{result.confidence_score:.2f}<{VISION_RETRY_CONFIDENCE}"
            )

        if not self.adaptive_enabled():
            if result.confidence_score < VISION_RETRY_CONFIDENCE:
                reasons.append(
                    f"low_confidence:{result.confidence_score:.2f}<{VISION_RETRY_CONFIDENCE}"
                )
            for issue in suspicious:
                reasons.append(f"suspicious:{issue}")
        elif suspicious and missing:
            for issue in suspicious:
                reasons.append(f"suspicious:{issue}")

        deduped = list(dict.fromkeys(reasons))
        return bool(deduped), deduped

    @staticmethod
    def _utility_parse_failed(
        result: ExtractionResult,
        meta: dict,
        missing: list[str],
    ) -> bool:
        category = str(meta.get("document_category", "")).lower()
        if category not in _UTILITY_CATEGORIES:
            return False
        if missing:
            return True
        utility_flags = {
            "kesco_invoice_number_not_nr_ref",
            "utility_customer_invalid",
            "utility_description_missing",
        }
        return any(reason in utility_flags for reason in result.review_reasons)

    def fallback_metadata(
        self,
        *,
        fallback_reason: str,
        strong_calls: int = 1,
    ) -> dict[str, object]:
        return ModelRoutingDecision(
            model_strategy="strong_fallback",
            model_used=self.fast_model(),
            fallback_model_used=self.strong_model(),
            fallback_reason=fallback_reason,
            strong_model_openai_calls=strong_calls,
        ).metadata()
