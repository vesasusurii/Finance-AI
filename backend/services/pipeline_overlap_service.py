"""Pipeline overlap orchestration — run independent stages concurrently."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, TypeVar

from config import settings
from utils.content_hash import sha256_hex

T = TypeVar("T")
U = TypeVar("U")


@dataclass
class PersistencePrep:
    content_hash: str | None = None
    provider: str = "openai_vision"
    audit_action: str = "invoice_extracted"
    audit_entity_type: str = "invoice"


@dataclass
class ValidationPrep:
    partial_count: int
    fields_present: int
    confidence_scores: list[float]


@dataclass
class PipelineOverlapTracker:
    enabled: bool
    saved_ms: float = 0.0
    tasks: list[str] = field(default_factory=list)
    parallel_sections: list[str] = field(default_factory=list)
    fallback: bool = False
    persistence_prep: PersistencePrep | None = None
    validation_prep: ValidationPrep | None = None

    def mark_fallback(self) -> None:
        self.fallback = True

    def record_parallel(self, section: str, primary_ms: float, overlap_ms: float) -> None:
        saved = round(min(primary_ms, overlap_ms), 1)
        if saved <= 0:
            return
        self.saved_ms = round(self.saved_ms + saved, 1)
        if section not in self.parallel_sections:
            self.parallel_sections.append(section)

    def metadata(self) -> dict[str, object]:
        return {
            "pipeline_overlap_enabled": self.enabled,
            "pipeline_overlap_saved_ms": round(self.saved_ms, 1),
            "pipeline_overlap_tasks": list(self.tasks),
            "pipeline_overlap_fallback": self.fallback,
            "pipeline_parallel_sections": list(self.parallel_sections),
        }


def build_persistence_prep(content: bytes | None) -> PersistencePrep:
    content_hash = None
    if content is not None and settings.ocr_cache_enabled:
        content_hash = sha256_hex(content)
    return PersistencePrep(content_hash=content_hash)


def build_validation_prep(partials: list[Any]) -> ValidationPrep:
    field_names: set[str] = set()
    confidence_scores: list[float] = []
    for partial in partials:
        if hasattr(partial, "model_dump"):
            payload = partial.model_dump()
        elif isinstance(partial, dict):
            payload = partial
        else:
            continue
        for key, value in payload.items():
            if value is not None and key != "line_items":
                field_names.add(key)
        score = payload.get("confidence_score")
        if isinstance(score, (int, float)):
            confidence_scores.append(float(score))
    return ValidationPrep(
        partial_count=len(partials),
        fields_present=len(field_names),
        confidence_scores=confidence_scores,
    )


async def run_parallel(
    primary: Callable[[], Awaitable[T]],
    overlap: Callable[[], Awaitable[U]],
    *,
    section: str,
    tracker: PipelineOverlapTracker | None,
) -> tuple[T, U | None]:
    """Run two awaitables concurrently; record estimated wall-clock savings."""
    if tracker is None or not tracker.enabled:
        return await primary(), None

    overlap_t0 = time.perf_counter()
    primary_t0 = time.perf_counter()
    primary_task = asyncio.create_task(primary())
    overlap_task = asyncio.create_task(overlap())
    try:
        primary_result = await primary_task
        primary_ms = (time.perf_counter() - primary_t0) * 1000
        overlap_ms = (time.perf_counter() - overlap_t0) * 1000
        try:
            overlap_result = await overlap_task
        except asyncio.CancelledError:
            overlap_result = None
        tracker.record_parallel(section, primary_ms, overlap_ms)
        if section not in tracker.tasks:
            tracker.tasks.append(section)
        return primary_result, overlap_result
    except Exception:
        overlap_task.cancel()
        try:
            await overlap_task
        except asyncio.CancelledError:
            pass
        raise


async def run_parallel_or_sequential(
    *,
    enabled: bool,
    parallel_fn: Callable[[], Awaitable[T]],
    sequential_fn: Callable[[], Awaitable[T]],
    tracker: PipelineOverlapTracker | None,
) -> T:
    if not enabled or tracker is None or not tracker.enabled:
        return await sequential_fn()
    try:
        return await parallel_fn()
    except Exception:
        if tracker is not None:
            tracker.mark_fallback()
        return await sequential_fn()
