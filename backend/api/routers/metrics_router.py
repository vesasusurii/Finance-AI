from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from config import settings
from core.ocr_progress import recent_ocr_timings
from core.system_mode import current_system_mode
from core.worker_metrics import metrics_snapshot
from schemas.auth import UserContext

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/workers")
async def worker_metrics(_user: UserContext = Depends(get_current_user)) -> dict:
    metrics = metrics_snapshot()
    metrics["system_mode"] = current_system_mode()
    metrics["ocr_runtime_config"] = {
        "openai_model": settings.openai_model,
        "openai_model_strong": settings.openai_model_strong,
        "openai_max_retries": settings.openai_max_retries,
        "openai_strong_retry_enabled": settings.openai_strong_retry_enabled,
        "openai_field_recovery_enabled": settings.openai_field_recovery_enabled,
        "openai_text_first_enabled": settings.openai_text_first_enabled,
        "openai_hybrid_text_enabled": settings.openai_hybrid_text_enabled,
        "openai_vision_pages_per_request": settings.openai_vision_pages_per_request,
        "openai_vision_page_batch_size": settings.openai_vision_page_batch_size,
        "openai_page_batch_concurrency": settings.openai_page_batch_concurrency,
        "openai_pdf_render_scale": settings.openai_pdf_render_scale,
        "openai_vision_full_document_max_bytes": settings.openai_vision_full_document_max_bytes,
        "openai_adaptive_image_detail": settings.openai_adaptive_image_detail,
        "openai_adaptive_image_detail_middle": settings.openai_adaptive_image_detail_middle,
        "openai_deterministic_merge_enabled": settings.openai_deterministic_merge_enabled,
        "openai_deterministic_merge_min_confidence": settings.openai_deterministic_merge_min_confidence,
        "openai_rps_limit": settings.openai_rps_limit,
        "openai_concurrency_limit": settings.openai_concurrency_limit,
        "queue_mode": settings.queue_mode,
        "storage_backend": settings.storage_backend,
        "ocr_cache_enabled": settings.ocr_cache_enabled,
    }
    metrics["recent_ocr_timings"] = recent_ocr_timings()
    return metrics
