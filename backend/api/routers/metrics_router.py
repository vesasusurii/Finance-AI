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
        "openai_adaptive_model_routing_enabled": settings.openai_adaptive_model_routing_enabled,
        "openai_fast_model": settings.openai_fast_model,
        "openai_max_retries": settings.openai_max_retries,
        "openai_strong_retry_enabled": settings.openai_strong_retry_enabled,
        "openai_field_recovery_enabled": settings.openai_field_recovery_enabled,
        "openai_targeted_field_recovery_enabled": settings.openai_targeted_field_recovery_enabled,
        "openai_targeted_field_recovery_max_fields": settings.openai_targeted_field_recovery_max_fields,
        "openai_preclassification_routing_enabled": settings.openai_preclassification_routing_enabled,
        "openai_queue_prioritization_enabled": settings.openai_queue_prioritization_enabled,
        "openai_queue_starvation_boost_seconds": settings.openai_queue_starvation_boost_seconds,
        "openai_pipeline_overlap_enabled": settings.openai_pipeline_overlap_enabled,
        "openai_text_first_enabled": settings.openai_text_first_enabled,
        "openai_hybrid_text_enabled": settings.openai_hybrid_text_enabled,
        "openai_vision_pages_per_request": settings.openai_vision_pages_per_request,
        "openai_vision_page_batch_size": settings.openai_vision_page_batch_size,
        "openai_page_batch_concurrency": settings.openai_page_batch_concurrency,
        "openai_pdf_render_scale": settings.openai_pdf_render_scale,
        "openai_adaptive_render_scale": settings.openai_adaptive_render_scale,
        "openai_render_scale_high": settings.openai_render_scale_high,
        "openai_render_scale_medium": settings.openai_render_scale_medium,
        "openai_render_scale_low": settings.openai_render_scale_low,
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
        "ocr_slo_total_ms": settings.ocr_slo_total_ms,
        "ocr_slo_openai_ms": settings.ocr_slo_openai_ms,
        "ocr_slo_queue_wait_ms": settings.ocr_slo_queue_wait_ms,
        "ocr_slo_max_openai_calls": settings.ocr_slo_max_openai_calls,
        "ocr_slo_max_fallback_rate": settings.ocr_slo_max_fallback_rate,
    }
    metrics["recent_ocr_timings"] = recent_ocr_timings()
    return metrics
