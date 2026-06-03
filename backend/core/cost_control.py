from __future__ import annotations

from contextlib import contextmanager

from config import settings


@contextmanager
def apply_ocr_cost_controls(system_mode: str):
    original_pages_per_request = settings.openai_vision_pages_per_request
    original_page_batch_size = settings.openai_vision_page_batch_size
    if settings.queue_mode == "adaptive" and system_mode in {"stressed", "degraded"}:
        settings.openai_vision_pages_per_request = max(
            1,
            settings.openai_vision_pages_per_request // 2,
        )
        settings.openai_vision_page_batch_size = max(
            1,
            settings.openai_vision_page_batch_size // 2,
        )
    try:
        yield
    finally:
        settings.openai_vision_pages_per_request = original_pages_per_request
        settings.openai_vision_page_batch_size = original_page_batch_size
