"""OCR performance analytics, slow-job diagnostics, and SLO checks."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import mean
from typing import Any

from config import settings
from core.debug_logger import get_logger
from core.ocr_progress import recent_ocr_timings

logger = get_logger(__name__)

_PERCENTILES = (50, 90, 95, 99)

_DISTRIBUTION_FIELDS: tuple[tuple[str, str], ...] = (
    ("extraction_mode", "extraction_mode"),
    ("preclassification_type", "preclassification_type"),
    ("prompt_strategy", "prompt_strategy"),
    ("image_detail_strategy", "image_detail_strategy"),
    ("merge_strategy", "merge_strategy"),
    ("render_strategy", "render_strategy"),
    ("model_strategy", "model_strategy"),
    ("queue_class", "queue_class"),
)


@dataclass(frozen=True)
class SloConfig:
    total_ms: int
    openai_ms: int
    queue_wait_ms: int
    max_openai_calls: int
    max_fallback_rate: float

    @classmethod
    def from_settings(cls) -> SloConfig:
        return cls(
            total_ms=settings.ocr_slo_total_ms,
            openai_ms=settings.ocr_slo_openai_ms,
            queue_wait_ms=settings.ocr_slo_queue_wait_ms,
            max_openai_calls=settings.ocr_slo_max_openai_calls,
            max_fallback_rate=settings.ocr_slo_max_fallback_rate,
        )

    def as_dict(self) -> dict[str, int | float]:
        return {
            "total_ms": self.total_ms,
            "openai_ms": self.openai_ms,
            "queue_wait_ms": self.queue_wait_ms,
            "max_openai_calls": self.max_openai_calls,
            "max_fallback_rate": self.max_fallback_rate,
        }


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile on sorted values."""
    if not values:
        return None
    if p <= 0:
        return round(min(values), 1)
    if p >= 100:
        return round(max(values), 1)
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 1)
    rank = int(round((p / 100) * (len(ordered) - 1)))
    rank = max(0, min(rank, len(ordered) - 1))
    return round(ordered[rank], 1)


def percentile_summary(values: list[float]) -> dict[str, float | None]:
    return {f"p{p}": percentile(values, p) for p in _PERCENTILES}


def _distribution(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        raw = row.get(field)
        if raw is None or raw == "":
            key = "unknown"
        else:
            key = str(raw)
        counter[key] += 1
    return dict(counter)


def _is_fallback(row: dict[str, Any]) -> bool:
    if row.get("fallback_model_used"):
        return True
    if row.get("routing_fallback_used"):
        return True
    if row.get("pipeline_overlap_fallback"):
        return True
    if row.get("strong_model_openai_calls"):
        try:
            return int(row["strong_model_openai_calls"]) > 0
        except (TypeError, ValueError):
            return False
    return False


def _targeted_recovery_used(row: dict[str, Any]) -> bool:
    return bool(row.get("targeted_recovery_used"))


def classify_slowness(row: dict[str, Any], slo: SloConfig | None = None) -> str:
    """Return the primary reason a job was slow."""
    slo = slo or SloConfig.from_settings()
    if _is_fallback(row):
        return "fallback_retry"

    call_count = _int(row.get("openai_call_count")) or 0
    if call_count > slo.max_openai_calls:
        return "too_many_openai_calls"

    stages = {
        "queue_wait": _float(row.get("queue_wait_ms")) or 0.0,
        "openai_latency": _float(row.get("openai_total_ms")) or 0.0,
        "render_latency": _float(row.get("render_ms")) or 0.0,
        "merge_latency": _float(row.get("merge_ms")) or 0.0,
    }
    dominant = max(stages, key=stages.get)
    if stages[dominant] > 0:
        return dominant
    return "openai_latency"


def slo_violations_for_job(row: dict[str, Any], slo: SloConfig | None = None) -> list[str]:
    slo = slo or SloConfig.from_settings()
    violations: list[str] = []
    total_ms = _float(row.get("total_ms"))
    openai_ms = _float(row.get("openai_total_ms"))
    queue_wait_ms = _float(row.get("queue_wait_ms"))
    call_count = _int(row.get("openai_call_count"))

    if total_ms is not None and total_ms > slo.total_ms:
        violations.append("total_ms")
    if openai_ms is not None and openai_ms > slo.openai_ms:
        violations.append("openai_total_ms")
    if queue_wait_ms is not None and queue_wait_ms > slo.queue_wait_ms:
        violations.append("queue_wait_ms")
    if call_count is not None and call_count > slo.max_openai_calls:
        violations.append("openai_call_count")
    return violations


def log_slo_violations(row: dict[str, Any]) -> None:
    violations = slo_violations_for_job(row)
    if not violations:
        return
    document_id = row.get("upload_id") or row.get("document_id")
    logger.warning(
        "OCR SLO violation document_id=%s violations=%s total_ms=%s openai_total_ms=%s "
        "queue_wait_ms=%s openai_call_count=%s extraction_mode=%s",
        document_id,
        violations,
        row.get("total_ms"),
        row.get("openai_total_ms"),
        row.get("queue_wait_ms"),
        row.get("openai_call_count"),
        row.get("extraction_mode"),
    )


def slow_job_entry(row: dict[str, Any], slo: SloConfig | None = None) -> dict[str, Any]:
    slo = slo or SloConfig.from_settings()
    document_id = row.get("upload_id") or row.get("document_id")
    return {
        "document_id": document_id,
        "extraction_mode": row.get("extraction_mode"),
        "total_ms": _float(row.get("total_ms")),
        "openai_total_ms": _float(row.get("openai_total_ms")),
        "queue_wait_ms": _float(row.get("queue_wait_ms")),
        "render_ms": _float(row.get("render_ms")),
        "merge_ms": _float(row.get("merge_ms")),
        "openai_call_count": _int(row.get("openai_call_count")),
        "slowness_reason": classify_slowness(row, slo),
        "slo_violations": slo_violations_for_job(row, slo),
    }


def build_ocr_analytics(*, limit: int = 50) -> dict[str, Any]:
    rows = recent_ocr_timings(limit=limit)
    slo = SloConfig.from_settings()

    if not rows:
        return {
            "sample_size": 0,
            "percentiles": {
                "total_ms": percentile_summary([]),
                "openai_total_ms": percentile_summary([]),
                "queue_wait_ms": percentile_summary([]),
                "render_ms": percentile_summary([]),
            },
            "averages": {
                "openai_call_count": 0,
                "pipeline_overlap_saved_ms": 0,
            },
            "distributions": {key: {} for key, _ in _DISTRIBUTION_FIELDS},
            "rates": {
                "targeted_recovery_usage": 0,
                "fallback_usage": 0,
            },
            "slow_jobs": [],
            "slo_violations": [],
            "slo_config": slo.as_dict(),
        }

    total_ms_vals = [v for v in (_float(r.get("total_ms")) for r in rows) if v is not None]
    openai_vals = [
        v for v in (_float(r.get("openai_total_ms")) for r in rows) if v is not None
    ]
    queue_vals = [
        v for v in (_float(r.get("queue_wait_ms")) for r in rows) if v is not None
    ]
    render_vals = [v for v in (_float(r.get("render_ms")) for r in rows) if v is not None]

    call_counts = [
        v for v in (_int(r.get("openai_call_count")) for r in rows) if v is not None
    ]
    overlap_vals = [
        v
        for v in (_float(r.get("pipeline_overlap_saved_ms")) for r in rows)
        if v is not None
    ]

    fallback_count = sum(1 for row in rows if _is_fallback(row))
    targeted_count = sum(1 for row in rows if _targeted_recovery_used(row))
    sample_size = len(rows)

    slow_jobs = sorted(
        [slow_job_entry(row, slo) for row in rows if _float(row.get("total_ms")) is not None],
        key=lambda item: item.get("total_ms") or 0,
        reverse=True,
    )[:10]

    violation_rows: list[dict[str, Any]] = []
    for row in rows:
        violations = slo_violations_for_job(row, slo)
        if violations:
            entry = slow_job_entry(row, slo)
            entry["violations"] = violations
            violation_rows.append(entry)

    analytics = {
        "sample_size": sample_size,
        "percentiles": {
            "total_ms": percentile_summary(total_ms_vals),
            "openai_total_ms": percentile_summary(openai_vals),
            "queue_wait_ms": percentile_summary(queue_vals),
            "render_ms": percentile_summary(render_vals),
        },
        "averages": {
            "openai_call_count": round(mean(call_counts), 2) if call_counts else 0,
            "pipeline_overlap_saved_ms": round(mean(overlap_vals), 1)
            if overlap_vals
            else 0,
        },
        "distributions": {
            key: _distribution(rows, field) for key, field in _DISTRIBUTION_FIELDS
        },
        "rates": {
            "targeted_recovery_usage": round(targeted_count / sample_size, 4),
            "fallback_usage": round(fallback_count / sample_size, 4),
        },
        "slow_jobs": slow_jobs,
        "slo_violations": violation_rows[:20],
        "slo_config": slo.as_dict(),
    }

    if analytics["rates"]["fallback_usage"] > slo.max_fallback_rate:
        logger.warning(
            "OCR fallback usage rate %.1f%% exceeds SLO threshold %.1f%% (sample=%d)",
            analytics["rates"]["fallback_usage"] * 100,
            slo.max_fallback_rate * 100,
            sample_size,
        )

    return analytics
