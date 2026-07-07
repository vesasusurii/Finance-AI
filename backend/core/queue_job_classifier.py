"""Lightweight OCR job classification for queue prioritisation."""

from __future__ import annotations

from dataclasses import dataclass

from config import settings

IMAGE_MIMES = frozenset({"image/jpeg", "image/jpg", "image/png"})
_LARGE_PAGE_THRESHOLD = 5
_LONG_SCANNED_PAGE_THRESHOLD = 3
_LARGE_FILE_BYTES = 2_000_000


@dataclass(frozen=True)
class QueueJobClassification:
    queue_class: str
    queue_priority: str
    queue_priority_reason: str
    queue_starvation_boosted: bool = False

    def metadata(self) -> dict[str, object]:
        return {
            "queue_class": self.queue_class,
            "queue_priority": self.queue_priority,
            "queue_priority_reason": self.queue_priority_reason,
            "queue_starvation_boosted": self.queue_starvation_boosted,
        }


def _legacy_priority(explicit: str | None, *, batch_upload: bool) -> QueueJobClassification:
    priority = explicit or ("high" if not batch_upload else "normal")
    return QueueJobClassification(
        queue_class="normal_job",
        queue_priority=priority,
        queue_priority_reason="legacy_priority",
    )


def classify_invoice_ocr_job(
    *,
    mime: str | None = None,
    file_size: int | None = None,
    page_count: int | None = None,
    has_text_layer: bool | None = None,
    text_chars: int | None = None,
    duplicate_reprocess: bool = False,
    duplicate_cache_hit: bool = False,
    redis_handoff: bool = False,
    uploaded_age_seconds: float | None = None,
    explicit_priority: str | None = None,
    batch_upload: bool = False,
) -> QueueJobClassification:
    """Classify an invoice OCR job before RQ enqueue."""
    if not settings.openai_queue_prioritization_enabled:
        return _legacy_priority(explicit_priority, batch_upload=batch_upload)

    if duplicate_cache_hit or duplicate_reprocess:
        return QueueJobClassification(
            queue_class="small_fast_job",
            queue_priority="high",
            queue_priority_reason="duplicate_cache_hit" if duplicate_cache_hit else "duplicate_reprocess",
        )

    pages = page_count or 1
    size = file_size or 0
    is_image = mime in IMAGE_MIMES if mime else False
    has_text = bool(has_text_layer)
    if text_chars is not None and text_chars >= settings.openai_text_first_min_chars:
        has_text = True

    if is_image or pages <= 1:
        if has_text or is_image or pages <= 1:
            return QueueJobClassification(
                queue_class="small_fast_job",
                queue_priority="high",
                queue_priority_reason="single_page_or_image",
            )

    if has_text and pages <= settings.openai_text_first_max_pages:
        return QueueJobClassification(
            queue_class="small_fast_job",
            queue_priority="high",
            queue_priority_reason="digital_pdf_text_layer",
        )

    if pages >= _LARGE_PAGE_THRESHOLD or (
        pages >= _LONG_SCANNED_PAGE_THRESHOLD
        and not has_text
        and size >= _LARGE_FILE_BYTES
    ):
        classification = QueueJobClassification(
            queue_class="large_slow_job",
            queue_priority="normal",
            queue_priority_reason="long_scanned_pdf",
        )
        if _should_starvation_boost(uploaded_age_seconds):
            return QueueJobClassification(
                queue_class=classification.queue_class,
                queue_priority="high",
                queue_priority_reason="starvation_boost",
                queue_starvation_boosted=True,
            )
        return classification

    if redis_handoff:
        reason = "normal_with_redis_handoff"
    else:
        reason = "normal_invoice"
    return QueueJobClassification(
        queue_class="normal_job",
        queue_priority="normal",
        queue_priority_reason=reason,
    )


def inspect_upload_content(content: bytes, mime: str) -> tuple[int | None, bool, int]:
    """Best-effort page count and text-layer signals from upload bytes."""
    if mime in IMAGE_MIMES:
        return 1, False, 0

    if mime != "application/pdf":
        return None, False, 0

    try:
        from services.ocr.pdf_reader import pdf_page_count
        from services.ocr.pdf_text_extractor import extract_pdf_text

        pages = pdf_page_count(content)
        text = extract_pdf_text(content)
        text_chars = len(text.strip())
        has_text = text_chars >= settings.openai_text_first_min_chars
        return pages, has_text, text_chars
    except Exception:
        return None, False, 0


def classify_from_upload(
    *,
    mime: str,
    file_size: int,
    content: bytes | None,
    duplicate_reprocess: bool = False,
    uploaded_age_seconds: float | None = None,
    explicit_priority: str | None = None,
    batch_upload: bool = False,
) -> QueueJobClassification:
    page_count: int | None = None
    has_text_layer: bool | None = None
    text_chars = 0
    if content:
        page_count, has_text_layer, text_chars = inspect_upload_content(content, mime)

    return classify_invoice_ocr_job(
        mime=mime,
        file_size=file_size,
        page_count=page_count,
        has_text_layer=has_text_layer,
        text_chars=text_chars,
        duplicate_reprocess=duplicate_reprocess,
        redis_handoff=content is not None,
        uploaded_age_seconds=uploaded_age_seconds,
        explicit_priority=explicit_priority,
        batch_upload=batch_upload,
    )


def _should_starvation_boost(uploaded_age_seconds: float | None) -> bool:
    if uploaded_age_seconds is None:
        return False
    return uploaded_age_seconds >= settings.openai_queue_starvation_boost_seconds
