"""
Invoice extraction — OpenAI Vision primary with optional PDF text-layer hybrid (DOCS/8).

PDFs are rasterised page-by-page for OpenAI Vision. When a text layer is present,
pdfplumber hints are merged with Vision output. JPEG, JPG, and PNG uploads are
sent directly to Vision without conversion.
"""

import asyncio
import base64
import json
import time
from dataclasses import dataclass, replace

from sqlalchemy.exc import IntegrityError

from core.document_types import resolve_document_mime
from fastapi import UploadFile
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from config import settings
from core.debug_logger import debug_trace, get_logger, log_typed_fields
from core.exceptions import ExtractionError
from core.ocr_progress import (
    get_ocr_progress,
    normalize_ocr_timing_fields,
    record_recent_ocr_timing,
    update_ocr_progress,
)
from repositories.audit_repository import AuditRepository
from repositories.invoice_access_repository import InvoiceAccessRepository
from repositories.invoice_repository import DuplicateInvoiceNumberError, InvoiceRepository
from repositories.upload_repository import UploadRepository
from utils.content_hash import sha256_hex
from schemas.auth import UserContext
from schemas.invoice import ExtractionResult, UploadItemResponse
from ai.prompts import VISION_SYSTEM_PROMPT
from ai.prompts.builders.prompt_builder import (
    build_batch_system_prompt,
    build_merge_system_prompt,
    build_vision_system_prompt,
    estimate_prompt_tokens,
    prompt_strategy_label,
)
from core.document_categories import DocumentCategory
from services.ai_validation_service import AIValidationService
from services.deterministic_partial_merge_service import DeterministicPartialMergeService
from services.document_classifier_service import DocumentClassifierService
from services.adaptive_model_routing_service import AdaptiveModelRoutingService
from services.field_recovery_service import FieldRecoveryService
from services.targeted_field_recovery_service import TargetedFieldRecoveryService
from services.hybrid_extraction_service import HybridExtractionService
from services.document_preclassification_service import (
    DocumentPreclassificationService,
    PreclassificationResult,
)
from services.text_first_extraction_service import TextFirstExtractionService
from services.adaptive_render_scale_service import (
    build_adaptive_render_plan,
    estimate_image_bytes,
    log_render_plan,
)
from services.pipeline_overlap_service import (
    PipelineOverlapTracker,
    build_persistence_prep,
    build_validation_prep,
    run_parallel,
)
from services.vision_page_selection_service import VisionPageSelection, select_vision_pages
from services.ocr.pdf_page_analyzer import PageContentAnalysis, analyze_pdf_pages
from services.ocr.pdf_text_extractor import (
    TextLayerHints,
    extract_pdf_page_texts,
    extract_pdf_text,
    parse_text_layer_hints,
)
from services.ocr.pdf_reader import (
    pdf_is_encrypted,
    pdf_page_count,
    render_pdf_pages,
)
from utils.file_storage import resolve_upload_bytes, save_bytes
from utils.openai_chat import chat_completion_kwargs, is_reasoning_model

logger = get_logger(__name__)

EXTRACTION_PROVIDER = "openai_vision"

ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}
MAX_FILE_BYTES = 20 * 1024 * 1024

# GPT-4 output budget; GPT-5/o-series also spend tokens on internal reasoning first.
_MAX_TOKENS = 2400

_MIDDLE_IMAGE_DETAIL_LEVELS = frozenset({"low", "auto"})


def _image_detail_for_page(page_num: int, total_pages: int) -> str:
    """OpenAI Vision detail for a 1-based page index."""
    if not settings.openai_adaptive_image_detail:
        return "high"
    if total_pages <= 1:
        return "high"
    if page_num <= 1 or page_num >= total_pages:
        return "high"
    middle = settings.openai_adaptive_image_detail_middle.strip().lower()
    if middle not in _MIDDLE_IMAGE_DETAIL_LEVELS:
        return "low"
    return middle


def _image_detail_strategy_name() -> str:
    if settings.openai_adaptive_image_detail:
        return "adaptive_first_last_high"
    return "all_high"


def _cap_vision_supplemental_text(text: str | None) -> tuple[str | None, int]:
    if not text:
        return None, 0
    capped = text[: settings.openai_vision_supplemental_text_max_chars]
    return capped, len(capped)


@dataclass(frozen=True)
class _ExtractionContext:
    document_category: DocumentCategory
    text_hints: TextLayerHints
    supplemental_text: str | None
    vision_system_prompt: str
    batch_system_prompt: str
    text_extraction_ms: float = 0.0
    document_classification_ms: float = 0.0
    prompt_strategy: str = "minimal"
    supplemental_text_chars: int = 0
    estimated_prompt_tokens: int = 0
    page_texts: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreparedUpload:
    upload_id: int
    stored_filename: str
    mime: str
    storage_path: str
    file_size: int
    content: bytes | None = None
    duplicate_reprocess: bool = False


class InvoiceExtractionService:
    def __init__(
        self,
        upload_repo: UploadRepository,
        invoice_repo: InvoiceRepository,
        invoice_access_repo: InvoiceAccessRepository,
        audit_repo: AuditRepository,
        ai_validation: AIValidationService,
        openai_client: AsyncOpenAI | None,
    ) -> None:
        self._upload_repo = upload_repo
        self._invoice_repo = invoice_repo
        self._invoice_access_repo = invoice_access_repo
        self._audit_repo = audit_repo
        self._ai_validation = ai_validation
        self._openai = openai_client
        self._classifier = DocumentClassifierService()
        self._hybrid = HybridExtractionService(ai_validation)
        self._field_recovery = FieldRecoveryService(openai_client, ai_validation)
        self._targeted_field_recovery = TargetedFieldRecoveryService(
            openai_client, ai_validation
        )
        self._text_first = TextFirstExtractionService(openai_client, ai_validation)
        self._preclassification = DocumentPreclassificationService()
        self._model_routing = AdaptiveModelRoutingService(ai_validation)
        self._deterministic_merge = DeterministicPartialMergeService(ai_validation)
        self._progress_upload_id: int | None = None
        self._openai_timings: list[dict] = []
        self._last_merge_ms: float | None = None
        self._last_merge_meta: dict[str, object] = {}
        self._last_page_selection_meta: dict[str, object] = {}
        self._last_render_meta: dict[str, object] = {}
        self._page_analyses: list[PageContentAnalysis] = []
        self._last_preclassification: PreclassificationResult | None = None
        self._last_preclassification_meta: dict[str, object] = {}
        self._last_hybrid_merge_ms: float | None = None
        self._last_field_recovery_ms: float | None = None
        self._last_targeted_recovery_meta: dict[str, object] = {}
        self._image_detail_high_pages: set[int] = set()
        self._image_detail_low_pages: set[int] = set()
        self._pipeline_overlap = PipelineOverlapTracker(
            enabled=settings.openai_pipeline_overlap_enabled
        )
        self._overlap_content: bytes | None = None

    def _reset_pipeline_overlap(self, content: bytes | None) -> None:
        self._overlap_content = content
        self._pipeline_overlap = PipelineOverlapTracker(
            enabled=settings.openai_pipeline_overlap_enabled
        )

    def _pipeline_overlap_meta(self) -> dict[str, object]:
        return self._pipeline_overlap.metadata()

    async def _openai_vision_call(self, *args, **kwargs) -> ExtractionResult:
        """Vision extract with optional persistence-prep overlap."""
        if not self._pipeline_overlap.enabled:
            return await self._openai_vision_extract(*args, **kwargs)

        async def vision() -> ExtractionResult:
            return await self._openai_vision_extract(*args, **kwargs)

        async def prep():
            if self._pipeline_overlap.persistence_prep is not None:
                return self._pipeline_overlap.persistence_prep
            self._pipeline_overlap.tasks.append("persistence_prep")
            built = build_persistence_prep(self._overlap_content)
            self._pipeline_overlap.persistence_prep = built
            return built

        result, _ = await run_parallel(
            vision,
            prep,
            section="vision_persistence_prep",
            tracker=self._pipeline_overlap,
        )
        return result

    def _reset_image_detail_tracking(self) -> None:
        self._image_detail_high_pages = set()
        self._image_detail_low_pages = set()

    def _record_image_detail_page(self, page_num: int, detail: str) -> None:
        if detail == "high":
            self._image_detail_high_pages.add(page_num)
            self._image_detail_low_pages.discard(page_num)
        else:
            self._image_detail_low_pages.add(page_num)
            self._image_detail_high_pages.discard(page_num)

    def _image_detail_meta(self, total_pages: int | None) -> dict[str, object]:
        pages = total_pages if total_pages else 1
        return {
            "image_detail_strategy": _image_detail_strategy_name(),
            "high_detail_pages": sorted(self._image_detail_high_pages),
            "low_detail_pages": sorted(self._image_detail_low_pages),
            "total_pages": pages,
        }

    def _prompt_meta(self, ctx: _ExtractionContext | None, *, mode: str) -> dict[str, object]:
        if ctx is None:
            return {}
        strategy = prompt_strategy_label(
            mode=mode,
            document_category=ctx.document_category,
        )
        system_prompt = (
            ctx.batch_system_prompt
            if mode
            in {
                "batch",
                "vision_batched",
                "vision_batched_merge",
                "vision_first_last_middle",
                "vision_dynamic",
                "vision_dynamic_fallback",
            }
            else ctx.vision_system_prompt
        )
        if mode == "merge":
            system_prompt = build_merge_system_prompt()
        return {
            "prompt_strategy": strategy,
            "supplemental_text_chars": ctx.supplemental_text_chars,
            "estimated_prompt_tokens": estimate_prompt_tokens(
                system_prompt,
                ctx.supplemental_text or "",
            ),
        }

    def _text_first_skip_meta(self) -> dict[str, object]:
        route = self._text_first.last_route
        if route is None:
            return {}
        return route.metadata()

    def _vision_pages_to_render(
        self,
        *,
        total_pages: int,
        ctx: _ExtractionContext,
        preclass: PreclassificationResult | None = None,
    ) -> tuple[list[int], VisionPageSelection | None]:
        use_dynamic = (
            settings.openai_dynamic_page_selection_enabled and total_pages > 2
        )
        if (
            preclass is not None
            and settings.openai_preclassification_routing_enabled
        ):
            if preclass.prefer_full_document_vision:
                use_dynamic = False
            elif (
                preclass.prefer_dynamic_vision is False
                and settings.openai_dynamic_page_selection_enabled
            ):
                use_dynamic = False

        if use_dynamic:
            page_texts = list(ctx.page_texts) if ctx.page_texts else None
            selection = select_vision_pages(
                total_pages=total_pages,
                page_texts=page_texts,
            )
            self._last_page_selection_meta = selection.metadata()
            return list(selection.selected_pages), selection
        all_pages = list(range(1, total_pages + 1))
        return all_pages, None

    def _mark_routing_fallback(self) -> None:
        if self._last_preclassification is None:
            return
        self._last_preclassification = self._last_preclassification.with_fallback()
        self._last_preclassification_meta = self._last_preclassification.metadata()

    def _render_page_numbers(
        self,
        content: bytes,
        page_numbers: list[int],
        *,
        total_pages: int,
        skipped_pages: tuple[int, ...] = (),
    ) -> tuple[dict[int, tuple[bytes, str]], dict[str, object]]:
        if not page_numbers:
            return {}, {}
        if not self._page_analyses:
            self._page_analyses = analyze_pdf_pages(content)

        render_plan = build_adaptive_render_plan(
            total_pages=total_pages,
            pages_to_render=page_numbers,
            analyses=self._page_analyses,
        )
        log_render_plan(total_pages=total_pages, plan=render_plan)
        page_scales = {plan.page_num: plan.scale for plan in render_plan.pages}
        page_reasons = {plan.page_num: plan.reason for plan in render_plan.pages}
        average_scale = (
            round(sum(page_scales.values()) / len(page_scales), 3)
            if page_scales
            else settings.openai_pdf_render_scale
        )
        estimated_bytes = estimate_image_bytes(
            page_count=len(page_numbers),
            average_scale=average_scale,
        )
        render_result = render_pdf_pages(
            content,
            max_pages=settings.openai_max_pdf_pages,
            page_indices=[page_num - 1 for page_num in page_numbers],
            page_scales=page_scales,
            page_render_reason=page_reasons,
            render_scale_strategy=render_plan.strategy,
            skipped_page_numbers=skipped_pages,
            estimated_image_bytes=estimated_bytes,
        )
        page_images = {
            page_num: image
            for page_num, image in zip(render_result.page_numbers, render_result.images)
        }
        render_meta = {
            "render_ms": render_result.render_ms,
            "render_strategy": render_result.render_strategy,
            "render_parallel_ms": render_result.render_parallel_ms,
            "rendered_page_count": render_result.rendered_page_count,
            "rendered_image_bytes": render_result.actual_image_bytes,
            "render_scale_strategy": render_result.render_scale_strategy,
            "page_render_scales": {
                str(k): v for k, v in render_result.page_render_scales.items()
            },
            "page_render_reason": {
                str(k): v for k, v in render_result.page_render_reason.items()
            },
            "average_render_scale": render_result.average_render_scale,
            "estimated_image_bytes": render_result.estimated_image_bytes,
            "actual_image_bytes": render_result.actual_image_bytes,
            "skipped_render_pages": list(render_result.skipped_page_numbers),
        }
        return page_images, render_meta

    def _render_pdf_for_vision(
        self,
        content: bytes,
        *,
        total_pages: int,
        ctx: _ExtractionContext,
        pages_to_render: list[int],
        skipped_pages: tuple[int, ...] = (),
    ) -> tuple[dict[int, tuple[bytes, str]], dict[str, object]]:
        page_images, render_meta = self._render_page_numbers(
            content,
            pages_to_render,
            total_pages=total_pages,
            skipped_pages=skipped_pages,
        )
        self._last_render_meta = render_meta
        return page_images, render_meta

    def _render_additional_pages(
        self,
        content: bytes,
        page_images: dict[int, tuple[bytes, str]],
        pages: list[int],
        *,
        total_pages: int,
    ) -> dict[int, tuple[bytes, str]]:
        missing = sorted(page for page in pages if page not in page_images)
        if not missing:
            return page_images

        extra_plan = build_adaptive_render_plan(
            total_pages=total_pages,
            pages_to_render=missing,
            analyses=self._page_analyses,
        )
        page_scales = {plan.page_num: plan.scale for plan in extra_plan.pages}
        page_reasons = {plan.page_num: plan.reason for plan in extra_plan.pages}
        extra_result = render_pdf_pages(
            content,
            max_pages=settings.openai_max_pdf_pages,
            page_indices=[page_num - 1 for page_num in missing],
            page_scales=page_scales,
            page_render_reason=page_reasons,
            render_scale_strategy=extra_plan.strategy,
        )
        for page_num, image in zip(extra_result.page_numbers, extra_result.images):
            page_images[page_num] = image
            logger.info(
                "Page %d → scale %.2f (%s)",
                page_num,
                page_scales.get(page_num, settings.openai_pdf_render_scale),
                page_reasons.get(page_num, "fallback render"),
            )
        return page_images

    @staticmethod
    def _contiguous_images(
        page_images: dict[int, tuple[bytes, str]],
        total_pages: int,
    ) -> list[tuple[bytes, str]]:
        return [page_images[page_num] for page_num in range(1, total_pages + 1)]

    def _update_progress(self, **fields) -> None:
        if self._progress_upload_id is not None:
            update_ocr_progress(self._progress_upload_id, **fields)

    async def _release_db_connection(self) -> None:
        """Return the checked-out connection before slow OCR / OpenAI work."""
        await self._upload_repo._session.close()

    # ─────────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────────

    @debug_trace
    async def extract_from_bytes(
        self,
        *,
        filename: str,
        content: bytes,
        mime: str | None = None,
    ) -> tuple[ExtractionResult, dict]:
        """Run extraction without DB — used by eval scripts and tests."""
        resolved_mime = mime or resolve_document_mime(filename, None)
        return await self._extract(filename, resolved_mime, content)

    @debug_trace
    async def prepare_upload(
        self,
        file: UploadFile,
        user: UserContext,
        *,
        content: bytes | None = None,
    ) -> PreparedUpload | UploadItemResponse:
        """Store file bytes and create an upload row — fast path for async OCR."""
        logger.debug(
            "OCR upload prepare: filename=%r content_type=%r user_id=%r",
            file.filename, file.content_type, user.user_id,
        )
        if not file.filename:
            raise ExtractionError("Missing filename")

        if content is None:
            content = await file.read()
        logger.debug(
            "Read upload bytes: size=%d (%s)", len(content), type(content).__name__
        )
        if len(content) > MAX_FILE_BYTES:
            raise ExtractionError("File exceeds 20 MB limit")

        mime = resolve_document_mime(file.filename or "", file.content_type)
        logger.debug("Resolved mime: %r (%s)", mime, type(mime).__name__)
        if mime not in ALLOWED_MIME:
            raise ExtractionError(
                f"Unsupported file type: {mime}. Supported: PDF, JPEG, JPG, PNG."
            )

        from utils.mime_validation import (
            mime_validation_error,
            validate_content_matches_mime,
        )

        if not validate_content_matches_mime(content, mime):
            raise ExtractionError(mime_validation_error(mime))

        content_hash = sha256_hex(content) if settings.ocr_cache_enabled else None
        if content_hash is not None:
            existing = await self._handle_duplicate_upload(
                content_hash, file.filename, mime, user
            )
            if existing is not None:
                logger.info(
                    "OCR cache reused for filename=%r user_id=%d",
                    file.filename,
                    user.user_id,
                )
                return existing

        stored_filename = file.filename or "upload"

        storage_path, file_size = await save_bytes(
            content,
            user_id=user.user_id,
            filename=stored_filename,
            mime_type=mime,
        )
        try:
            async with self._upload_repo._session.begin_nested():
                upload_row = await self._upload_repo.create(
                    file_kind="invoice",
                    filename=stored_filename,
                    storage_path=storage_path,
                    mime_type=mime,
                    user_id=user.user_id,
                    processing_status="queued",
                    file_size=file_size,
                    content_sha256=content_hash,
                )
        except IntegrityError:
            logger.warning(
                "Duplicate content_sha256 on insert for %r — resolving existing row",
                stored_filename,
            )
            if content_hash is not None:
                existing = await self._handle_duplicate_upload(
                    content_hash, stored_filename, mime, user
                )
                if existing is not None:
                    return existing
            raise ExtractionError(
                "This file was already uploaded. Check your documents list."
            ) from None
        logger.debug(
            "Upload row created: id=%d storage_path=%r", upload_row.id, storage_path
        )
        update_ocr_progress(
            upload_row.id,
            document_id=upload_row.id,
            filename=stored_filename,
            upload_status="queued",
            stage="queued",
            stage_label="Queued",
            queued_at=time.time(),
            model=self._model_routing.fast_model(),
            mime_type=mime,
            file_size=file_size,
            uploaded_by=user.user_id,
        )
        return PreparedUpload(
            upload_id=upload_row.id,
            stored_filename=stored_filename,
            mime=mime,
            storage_path=storage_path,
            file_size=file_size,
            content=content,
        )

    @debug_trace
    async def complete_upload(
        self,
        upload_id: int,
        user_id: int,
        *,
        content: bytes | None = None,
    ) -> UploadItemResponse:
        """Run OCR and persist invoice data for a prepared upload row."""
        t0 = time.perf_counter()
        self._progress_upload_id = upload_id
        upload_row = await self._upload_repo.get(upload_id)
        if upload_row is None:
            raise ExtractionError(f"Upload {upload_id} not found")

        progress_snapshot = get_ocr_progress(upload_id)
        queue_wait_ms = None
        queued_at = progress_snapshot.get("queued_at")
        if isinstance(queued_at, (int, float)):
            queue_wait_ms = round((time.time() - float(queued_at)) * 1000, 1)
            self._update_progress(queue_wait_ms=queue_wait_ms)

        content_source = "memory"
        storage_download_ms = 0.0
        if content is None:
            content_source = "storage"
            storage_t0 = time.perf_counter()
            self._update_progress(
                stage="downloading",
                stage_label="Downloading file",
            )
            logger.info(
                "OCR upload_id=%d downloading bytes from Supabase/storage path=%s",
                upload_id,
                upload_row.storage_path,
            )
            content = await resolve_upload_bytes(
                upload_row.storage_path,
                original_filename=upload_row.original_filename,
            )
            storage_download_ms = round((time.perf_counter() - storage_t0) * 1000, 1)
        else:
            self._update_progress(
                stage="preparing",
                stage_label="Using uploaded file",
            )
            logger.info(
                "OCR upload_id=%d using in-memory upload bytes (%d bytes)",
                upload_id,
                len(content),
            )
        if content is None:
            raise ExtractionError("Stored upload file could not be read")
        logger.info(
            "OCR content resolved upload_id=%d source=%s bytes=%d storage_download_ms=%s",
            upload_id,
            content_source,
            len(content),
            storage_download_ms,
        )

        mime = upload_row.mime_type or "application/pdf"
        if mime == "image/jpg":
            mime = "image/jpeg"
        stored_filename = upload_row.original_filename
        source_file_id = upload_row.id

        # Release the read transaction and connection before slow OCR/OpenAI work.
        # The session re-acquires a connection when persisting results.
        await self._upload_repo.commit()
        await self._release_db_connection()

        try:
            extract_t0 = time.perf_counter()
            self._openai_timings = []
            self._last_merge_ms = None
            self._last_merge_meta = {}
            self._last_hybrid_merge_ms = None
            self._last_field_recovery_ms = None
            self._last_targeted_recovery_meta = {}
            self._reset_image_detail_tracking()
            self._reset_pipeline_overlap(content)
            result, model_used, meta = await self._extract(
                stored_filename, mime, content
            )
            extract_ms = round((time.perf_counter() - extract_t0) * 1000, 1)
            meta["ocr_ms"] = extract_ms
            meta["storage_download_ms"] = storage_download_ms
            meta["queue_wait_ms"] = queue_wait_ms
            logger.info(
                "OCR extract finished upload_id=%d ocr_ms=%s model=%s mode=%s",
                upload_id,
                extract_ms,
                model_used,
                meta.get("extraction_mode"),
            )
            log_typed_fields(logger, "OCR raw extraction", result)
            logger.debug("OCR meta: %r model_used=%r", meta, model_used)

            validation_t0 = time.perf_counter()
            result = self._ai_validation.sanitize_and_validate(result)
            meta["validation_ms"] = round(
                (time.perf_counter() - validation_t0) * 1000, 1
            )
            if self._last_hybrid_merge_ms is not None:
                meta["hybrid_merge_ms"] = self._last_hybrid_merge_ms
            if self._last_field_recovery_ms is not None:
                meta["field_recovery_ms"] = self._last_field_recovery_ms
            meta.update(self._last_targeted_recovery_meta)
            log_typed_fields(logger, "OCR after sanitize_and_validate", result)

            missing = self._ai_validation.validate_required_fields(result)
            logger.debug(
                "OCR missing required fields: %s (%s, len=%d)",
                missing, type(missing).__name__, len(missing),
            )
            if missing:
                result.needs_review = True
                result.confidence_score = min(result.confidence_score, 0.69)

            review_status = self._ai_validation.determine_review_status(result)
            logger.debug(
                "OCR review_status decision: %r (%s)",
                review_status, type(review_status).__name__,
            )

            persist_t0 = time.perf_counter()
            self._update_progress(
                stage="saving",
                stage_label="Saving invoice",
                upload_status="processing",
            )
            invoice = await self._invoice_repo.create(
                result, source_file_id, review_status, uploaded_by=user_id
            )
            logger.debug(
                "Invoice persisted: id=%d (%s)", invoice.id, type(invoice).__name__
            )

            await self._audit_repo.log(
                user_id,
                "invoice_extracted",
                "invoice",
                invoice.id,
                None,
                {
                    **result.model_dump(),
                    "provider": EXTRACTION_PROVIDER,
                    "model": model_used,
                    **meta,
                },
            )
            await self._upload_repo.update_status(source_file_id, "processed")
            persist_ms = round((time.perf_counter() - persist_t0) * 1000, 1)
            total_ms = round((time.perf_counter() - t0) * 1000, 1)
            meta["persist_ms"] = persist_ms
            meta["total_ms"] = total_ms
            meta["openai_calls"] = self._openai_timings
            meta["openai_total_ms"] = round(
                sum(float(call.get("openai_ms", 0.0)) for call in self._openai_timings),
                1,
            )
            meta["openai_call_count"] = len(self._openai_timings)
            timing_payload = normalize_ocr_timing_fields(
                {
                    "upload_id": source_file_id,
                    "invoice_id": invoice.id,
                    "model": model_used,
                    "extraction_mode": meta.get("extraction_mode"),
                    "queue_wait_ms": queue_wait_ms,
                    "queue_class": progress_snapshot.get("queue_class"),
                    "queue_priority": progress_snapshot.get("queue_priority"),
                    "queue_priority_reason": progress_snapshot.get("queue_priority_reason"),
                    "queue_starvation_boosted": progress_snapshot.get(
                        "queue_starvation_boosted"
                    ),
                    "pages_processed": meta.get("pages_processed"),
                    "total_pdf_pages": meta.get("total_pdf_pages"),
                    "text_layer_chars": meta.get("text_layer_chars"),
                    "text_extraction_ms": meta.get("text_extraction_ms"),
                    "document_classification_ms": meta.get(
                        "document_classification_ms"
                    ),
                    "text_llm_ms": meta.get("text_llm_ms"),
                    "render_ms": meta.get("render_ms"),
                    "rendered_image_bytes": meta.get("rendered_image_bytes"),
                    "merge_ms": meta.get("merge_ms"),
                    "hybrid_merge_ms": meta.get("hybrid_merge_ms"),
                    "field_recovery_ms": meta.get("field_recovery_ms"),
                    "validation_ms": meta.get("validation_ms"),
                    "storage_download_ms": storage_download_ms,
                    "ocr_ms": extract_ms,
                    "persist_ms": persist_ms,
                    "total_ms": total_ms,
                    "openai_total_ms": meta["openai_total_ms"],
                    "openai_call_count": meta["openai_call_count"],
                    "openai_calls": self._openai_timings,
                    "image_detail_strategy": meta.get("image_detail_strategy"),
                    "high_detail_pages": meta.get("high_detail_pages"),
                    "low_detail_pages": meta.get("low_detail_pages"),
                    "text_first_reason": meta.get("text_first_reason"),
                    "text_chars": meta.get("text_chars"),
                    "hints_found_count": meta.get("hints_found_count"),
                    "missing_hint_fields": meta.get("missing_hint_fields"),
                    "text_quality_score": meta.get("text_quality_score"),
                    "merge_strategy": meta.get("merge_strategy"),
                    "deterministic_merge_conflicts": meta.get(
                        "deterministic_merge_conflicts"
                    ),
                    "deterministic_merge_missing_fields": meta.get(
                        "deterministic_merge_missing_fields"
                    ),
                    "prompt_strategy": meta.get("prompt_strategy"),
                    "supplemental_text_chars": meta.get("supplemental_text_chars"),
                    "estimated_prompt_tokens": meta.get("estimated_prompt_tokens"),
                    "render_strategy": meta.get("render_strategy"),
                    "render_parallel_ms": meta.get("render_parallel_ms"),
                    "rendered_page_count": meta.get("rendered_page_count"),
                    "preclassification_type": meta.get("preclassification_type"),
                    "preclassification_reason": meta.get("preclassification_reason"),
                    "routing_decision": meta.get("routing_decision"),
                    "routing_fallback_used": meta.get("routing_fallback_used"),
                    "targeted_recovery_used": meta.get("targeted_recovery_used"),
                    "targeted_recovery_fields": meta.get("targeted_recovery_fields"),
                    "targeted_recovery_ms": meta.get("targeted_recovery_ms"),
                    "targeted_recovery_openai_calls": meta.get(
                        "targeted_recovery_openai_calls"
                    ),
                    "targeted_recovery_success": meta.get("targeted_recovery_success"),
                    "model_strategy": meta.get("model_strategy"),
                    "model_used": meta.get("model_used"),
                    "fallback_model_used": meta.get("fallback_model_used"),
                    "fallback_reason": meta.get("fallback_reason"),
                    "strong_model_openai_calls": meta.get("strong_model_openai_calls"),
                    "pipeline_overlap_enabled": meta.get("pipeline_overlap_enabled"),
                    "pipeline_overlap_saved_ms": meta.get("pipeline_overlap_saved_ms"),
                    "pipeline_overlap_tasks": meta.get("pipeline_overlap_tasks"),
                    "pipeline_overlap_fallback": meta.get("pipeline_overlap_fallback"),
                    "pipeline_parallel_sections": meta.get("pipeline_parallel_sections"),
                }
            )
            record_recent_ocr_timing(timing_payload)
            progress_fields = {
                key: value
                for key, value in timing_payload.items()
                if key not in {"upload_id", "openai_calls", "recorded_at"}
            }
            self._update_progress(
                stage="processed",
                stage_label="Invoice saved",
                upload_status="processed",
                **progress_fields,
            )
            return UploadItemResponse(
                upload_id=source_file_id,
                original_filename=stored_filename,
                processing_status="processed",
                invoice_id=invoice.id,
            )
        except DuplicateInvoiceNumberError as exc:
            logger.warning(
                "Duplicate invoice number for upload_id=%d: %s",
                upload_id,
                exc,
            )
            await self._upload_repo.rollback()
            await self._upload_repo.update_status(source_file_id, "failed")
            await self._upload_repo.commit()
            self._update_progress(
                stage="failed",
                stage_label="Extraction failed",
                upload_status="failed",
                error=str(exc),
            )
            raise ExtractionError(
                f"Invoice number already exists: {exc}"
            ) from exc
        except Exception as exc:
            logger.exception("Extraction failed for upload_id=%d", upload_id)
            await self._upload_repo.rollback()
            await self._upload_repo.update_status(source_file_id, "failed")
            await self._upload_repo.commit()
            self._update_progress(
                stage="failed",
                stage_label="Extraction failed",
                upload_status="failed",
                error=str(exc),
            )
            raise ExtractionError(str(exc)) from exc
        finally:
            self._progress_upload_id = None

    def _prepared_from_row(
        self,
        upload_row,
        mime: str,
        *,
        duplicate_reprocess: bool = False,
    ) -> PreparedUpload:
        resolved_mime = mime or upload_row.mime_type or "application/pdf"
        if resolved_mime == "image/jpg":
            resolved_mime = "image/jpeg"
        return PreparedUpload(
            upload_id=upload_row.id,
            stored_filename=upload_row.original_filename,
            mime=resolved_mime,
            storage_path=upload_row.storage_path,
            file_size=int(upload_row.file_size or 0),
            duplicate_reprocess=duplicate_reprocess,
        )

    async def _handle_duplicate_upload(
        self,
        content_hash: str,
        filename: str,
        mime: str,
        user: UserContext,
    ) -> UploadItemResponse | PreparedUpload | None:
        """If this file was uploaded before, link or reuse the existing upload row."""
        upload_row, invoice_row, owner_user = (
            await self._upload_repo.find_invoice_upload_by_hash(content_hash)
        )
        if upload_row is None:
            return None

        if invoice_row is not None:
            owner_email = owner_user.email if owner_user else "another user"
            if invoice_row.uploaded_by != user.user_id:
                await self._invoice_access_repo.grant(
                    invoice_row.id,
                    user.user_id,
                    grant_reason="duplicate_upload",
                )
            await self._audit_repo.log(
                user.user_id,
                "invoice_linked_duplicate",
                "invoice",
                invoice_row.id,
                None,
                {
                    "content_sha256": content_hash,
                    "original_uploader_id": invoice_row.uploaded_by,
                    "original_uploader_email": owner_email,
                },
            )
            message = (
                f"This invoice was first uploaded by {owner_email}. "
                "It is now available in your documents list."
            )
            if invoice_row.uploaded_by == user.user_id:
                message = (
                    f"You already uploaded this file (as {owner_email}). "
                    "Open the existing invoice in your documents list."
                )
            return UploadItemResponse(
                upload_id=upload_row.id,
                original_filename=filename,
                processing_status="linked",
                invoice_id=invoice_row.id,
                message=message,
                original_uploader_email=owner_email,
            )

        status = upload_row.processing_status
        if status in ("processing", "queued"):
            if upload_row.uploaded_by == user.user_id:
                return UploadItemResponse(
                    upload_id=upload_row.id,
                    original_filename=filename,
                    processing_status="processing",
                    message=(
                        "This file is already being processed. "
                        "Check the upload queue for progress."
                    ),
                )
            raise ExtractionError(
                "This file is already being processed by another user. "
                "Wait for them to finish or ask them to share the invoice."
            )

        if status in ("failed", "processed"):
            if upload_row.uploaded_by != user.user_id:
                owner_email = owner_user.email if owner_user else "another user"
                raise ExtractionError(
                    f"This file was already uploaded by {owner_email}. "
                    "Check your documents list or ask them to share the invoice."
                )
            await self._upload_repo.update_status(upload_row.id, "queued")
            return self._prepared_from_row(upload_row, mime, duplicate_reprocess=True)

        raise ExtractionError(
            "This file was already uploaded. Check your documents list."
        )

    # ─────────────────────────────────────────────────────────────────────
    # Extraction routing
    # ─────────────────────────────────────────────────────────────────────

    def _build_extraction_context(
        self,
        *,
        filename: str,
        content: bytes | None,
        mime: str,
    ) -> _ExtractionContext:
        raw_text = ""
        hints = TextLayerHints(raw_text="")
        page_texts: tuple[str, ...] = ()
        text_t0 = time.perf_counter()
        text_extraction_ms = 0.0
        if (
            mime == "application/pdf"
            and content
            and (
                settings.openai_hybrid_text_enabled
                or settings.openai_dynamic_page_selection_enabled
                or settings.openai_adaptive_render_scale
            )
        ):
            self._update_progress(
                stage="extracting_text",
                stage_label="Extracting PDF text",
            )
            pages = extract_pdf_page_texts(content)
            page_texts = tuple(pages)
            raw_text = "\n".join(text for text in pages if text.strip())
            hints = parse_text_layer_hints(raw_text)
            text_extraction_ms = round((time.perf_counter() - text_t0) * 1000, 1)
            self._update_progress(text_extraction_ms=text_extraction_ms)

        classify_t0 = time.perf_counter()
        category = self._classifier.classify(hints.raw_text or raw_text, filename=filename)
        document_classification_ms = round(
            (time.perf_counter() - classify_t0) * 1000, 1
        )
        supplemental: str | None = None
        supplemental_chars = 0
        if hints.has_usable_text:
            supplemental, supplemental_chars = _cap_vision_supplemental_text(raw_text)

        vision_prompt = build_vision_system_prompt(category)
        batch_prompt = build_batch_system_prompt(category)
        prompt_strategy = prompt_strategy_label(
            mode="vision",
            document_category=category,
        )
        estimated_tokens = estimate_prompt_tokens(
            vision_prompt,
            supplemental or "",
        )

        logger.info(
            "Extraction context filename=%r category=%s text_chars=%d supplemental_chars=%d prompt_tokens~=%d",
            filename,
            category.value,
            len(raw_text),
            supplemental_chars,
            estimated_tokens,
        )

        return _ExtractionContext(
            document_category=category,
            text_hints=hints,
            supplemental_text=supplemental,
            vision_system_prompt=vision_prompt,
            batch_system_prompt=batch_prompt,
            text_extraction_ms=text_extraction_ms,
            document_classification_ms=document_classification_ms,
            prompt_strategy=prompt_strategy,
            supplemental_text_chars=supplemental_chars,
            estimated_prompt_tokens=estimated_tokens,
            page_texts=page_texts,
        )

    async def _apply_post_vision_pipeline(
        self,
        result: ExtractionResult,
        *,
        ctx: _ExtractionContext,
        images: list[tuple[bytes, str]],
        filename: str,
        model: str,
    ) -> ExtractionResult:
        if settings.openai_hybrid_text_enabled:
            hybrid_t0 = time.perf_counter()
            result = self._hybrid.merge(result, ctx.text_hints)
            self._last_hybrid_merge_ms = round(
                (time.perf_counter() - hybrid_t0) * 1000, 1
            )

        if settings.openai_field_recovery_enabled:
            missing = self._ai_validation.validate_required_fields(result)
            if missing:
                logger.info(
                    "Field recovery triggered for %s (missing=%s)",
                    filename,
                    missing,
                )
                recovery_t0 = time.perf_counter()
                result = await self._field_recovery.recover_missing_fields(
                    result,
                    images=images,
                    model=model,
                    filename=filename,
                )
                self._last_field_recovery_ms = round(
                    (time.perf_counter() - recovery_t0) * 1000, 1
                )
        elif settings.openai_targeted_field_recovery_enabled and images:
            outcome = await self._targeted_field_recovery.recover_missing_fields(
                result,
                images=images,
                model=model,
                filename=filename,
            )
            result = outcome.result
            self._last_targeted_recovery_meta = outcome.metadata
        return result

    @debug_trace
    async def _try_text_first_pdf(
        self,
        filename: str,
        *,
        total_pages: int,
        ctx: _ExtractionContext,
        preclass: PreclassificationResult | None = None,
    ) -> tuple[ExtractionResult, str, str, dict] | None:
        """Fast path for digital PDFs — regex hints or text-only LLM, no Vision."""
        if (
            preclass is not None
            and settings.openai_preclassification_routing_enabled
            and not preclass.use_text_first
        ):
            logger.info(
                "Text-first skipped for %r: preclassification=%s (%s)",
                filename,
                preclass.preclassification_type,
                preclass.preclassification_reason,
            )
            return None

        route = self._text_first.evaluate_route(
            total_pages=total_pages,
            hints=ctx.text_hints,
        )
        self._text_first.last_route = route
        text_meta: dict = {
            **route.metadata(),
            **(
                preclass.metadata()
                if preclass is not None
                else {}
            ),
        }

        if not route.use_text_first:
            logger.info(
                "Text-first skipped for %r: %s (chars=%d, hints=%d, quality=%.3f)",
                filename,
                route.reason,
                route.text_chars,
                route.hints_found_count,
                route.text_quality_score,
            )
            return None

        if route.mode == "text_hints":
            hints_result = self._text_first.result_from_hints(ctx.text_hints)
            if hints_result is not None:
                logger.info(
                    "Text-first hints path for %r (pages=%d, chars=%d)",
                    filename,
                    total_pages,
                    route.text_chars,
                )
                return hints_result, None, "text_hints", {
                    **text_meta,
                    **self._model_routing.primary_metadata(
                        mode="text_hints",
                        model_used=None,
                    ),
                }

        text_llm_t0 = time.perf_counter()
        self._update_progress(
            stage="text_llm",
            stage_label="Extracting from PDF text",
        )
        text_result = await self._text_first.extract_from_text(
            raw_text=ctx.text_hints.raw_text,
            filename=filename,
            system_prompt=ctx.vision_system_prompt,
            model=self._model_routing.fast_model(),
            chat_completion=self._chat_completion,
            parse_response=self._parse_response,
            hints=ctx.text_hints,
            partial_hint_count=route.hints_found_count,
        )
        text_llm_ms = round((time.perf_counter() - text_llm_t0) * 1000, 1)
        self._update_progress(text_llm_ms=text_llm_ms)
        if text_result is not None:
            logger.info(
                "Text-first LLM path for %r (pages=%d, chars=%d, reason=%s)",
                filename,
                total_pages,
                route.text_chars,
                route.reason,
            )
            return text_result, self._model_routing.fast_model(), "text_llm", {
                **text_meta,
                "text_llm_ms": text_llm_ms,
                **self._model_routing.primary_metadata(
                    mode="text_llm",
                    model_used=self._model_routing.fast_model(),
                ),
            }

        text_meta["text_first_reason"] = "text_llm_insufficient"
        self._text_first.last_route = replace(route, reason="text_llm_insufficient")
        if (
            preclass is not None
            and preclass.routing_decision == "text_first"
        ):
            self._mark_routing_fallback()
            text_meta.update(self._last_preclassification_meta)
        logger.info(
            "Text-first insufficient for %r — falling back to Vision",
            filename,
        )
        return None

    @debug_trace
    async def _extract(
        self, filename: str, mime: str, content: bytes
    ) -> tuple[ExtractionResult, str, dict]:
        if self._openai is None or not settings.openai_api_key:
            raise ExtractionError("OPENAI_API_KEY is not configured")

        self._reset_image_detail_tracking()
        self._reset_pipeline_overlap(content)

        if mime == "application/pdf":
            if pdf_is_encrypted(content):
                raise ExtractionError("Password-protected PDF cannot be processed")

            total_pages = pdf_page_count(content)
            logger.debug(
                "PDF page count: %d (%s)", total_pages, type(total_pages).__name__
            )
            if total_pages > settings.openai_max_pdf_pages:
                raise ExtractionError(
                    f"PDF has {total_pages} pages; maximum is {settings.openai_max_pdf_pages}"
                )

            ctx = self._build_extraction_context(
                filename=filename, content=content, mime=mime
            )
            preclass = self._preclassification.classify(
                mime=mime,
                filename=filename,
                total_pages=total_pages,
                hints=ctx.text_hints,
                document_category=ctx.document_category,
                page_texts=ctx.page_texts,
            )
            self._last_preclassification = preclass
            self._last_preclassification_meta = preclass.metadata()
            logger.info(
                "Preclassified %r as %s → %s (%s)",
                filename,
                preclass.preclassification_type,
                preclass.routing_decision,
                preclass.preclassification_reason,
            )

            text_first = await self._try_text_first_pdf(
                filename,
                total_pages=total_pages,
                ctx=ctx,
                preclass=preclass,
            )
            if text_first is not None:
                result, model_used, mode, text_meta = text_first
                meta = {
                    "pages_processed": 0,
                    "total_pdf_pages": total_pages,
                    "document_category": ctx.document_category.value,
                    "text_layer_chars": len(ctx.text_hints.raw_text),
                    "text_extraction_ms": ctx.text_extraction_ms,
                    "document_classification_ms": ctx.document_classification_ms,
                    "extraction_mode": mode,
                    "model": model_used,
                    **text_meta,
                    **self._prompt_meta(ctx, mode=mode),
                    **self._image_detail_meta(total_pages),
                    **self._last_preclassification_meta,
                }
                return result, model_used, meta

            self._page_analyses = []
            self._last_render_meta = {}

            pages_to_render, vision_selection = self._vision_pages_to_render(
                total_pages=total_pages,
                ctx=ctx,
                preclass=preclass,
            )
            skipped_render_pages = tuple(
                page_num
                for page_num in range(1, total_pages + 1)
                if page_num not in pages_to_render
            )

            overlap_applied = False
            overlap_images: list[tuple[bytes, str]] = []
            overlap_use_edges_first = False
            if (
                settings.openai_pipeline_overlap_enabled
                and vision_selection is None
                and total_pages >= 3
            ):
                if not self._page_analyses:
                    self._page_analyses = analyze_pdf_pages(content)
                overlap_plan = build_adaptive_render_plan(
                    total_pages=total_pages,
                    pages_to_render=pages_to_render,
                    analyses=self._page_analyses,
                )
                overlap_avg_scale = (
                    round(
                        sum(plan.scale for plan in overlap_plan.pages)
                        / len(overlap_plan.pages),
                        3,
                    )
                    if overlap_plan.pages
                    else settings.openai_pdf_render_scale
                )
                overlap_estimated_bytes = estimate_image_bytes(
                    page_count=total_pages,
                    average_scale=overlap_avg_scale,
                )
                overlap_use_edges_first = total_pages >= 5
                try:
                    (
                        overlap_result,
                        overlap_model,
                        overlap_meta,
                        overlap_images,
                    ) = await self._extract_pdf_with_pipeline_overlap(
                        filename,
                        content,
                        total_pages=total_pages,
                        ctx=ctx,
                        preclass=preclass,
                        pages_to_render=pages_to_render,
                        skipped_render_pages=skipped_render_pages,
                    )
                    overlap_applied = True
                except ExtractionError as exc:
                    if "pipeline_overlap_not_applicable" not in str(exc):
                        logger.warning(
                            "Pipeline overlap failed for %r — falling back to sequential: %s",
                            filename,
                            exc,
                        )
                        self._pipeline_overlap.mark_fallback()
                except Exception as exc:
                    logger.warning(
                        "Pipeline overlap failed for %r — falling back to sequential: %s",
                        filename,
                        exc,
                    )
                    self._pipeline_overlap.mark_fallback()

            if overlap_applied:
                async def _run_pdf_overlap(model: str):
                    result, model_used, mode, page_images = await self._run_pdf_pipelined(
                        model,
                        filename,
                        content,
                        total_pages=total_pages,
                        ctx=ctx,
                        pages_to_render=pages_to_render,
                        skipped_render_pages=skipped_render_pages,
                        use_edges_first=overlap_use_edges_first,
                    )
                    finalized = await self._finalize_pipeline_overlap(
                        result,
                        model_used,
                        mode,
                        page_images,
                        total_pages=total_pages,
                        ctx=ctx,
                        filename=filename,
                    )
                    return finalized[0], finalized[1], finalized[2]["extraction_mode"]

                return await self._maybe_retry_strong(
                    filename,
                    overlap_result,
                    overlap_model,
                    overlap_meta,
                    extract_fn=_run_pdf_overlap,
                    images=overlap_images,
                    ctx=ctx,
                )

            self._update_progress(
                stage="rendering_pdf",
                stage_label="Rendering PDF pages",
            )
            page_images, render_meta = self._render_pdf_for_vision(
                content,
                total_pages=total_pages,
                ctx=ctx,
                pages_to_render=pages_to_render,
                skipped_pages=skipped_render_pages,
            )
            images = self._contiguous_images(page_images, total_pages) if not skipped_render_pages else [
                page_images[page_num] for page_num in pages_to_render
            ]
            render_ms = render_meta["render_ms"]
            rendered_bytes = render_meta.get("actual_image_bytes") or sum(
                len(img) for img, _mime in images
            )
            logger.debug(
                "Rendered PDF pages: selected=%s count=%d bytes=%d render_ms=%s strategy=%s",
                pages_to_render,
                len(images),
                rendered_bytes,
                render_ms,
                render_meta.get("render_strategy"),
            )
            if not images:
                raise ExtractionError("PDF has no readable pages")

            meta: dict = {
                "pages_processed": len(images),
                "total_pdf_pages": total_pages,
                "document_category": ctx.document_category.value,
                "text_layer_chars": len(ctx.text_hints.raw_text),
                "text_extraction_ms": ctx.text_extraction_ms,
                "document_classification_ms": ctx.document_classification_ms,
                **render_meta,
                **self._text_first_skip_meta(),
                **self._last_preclassification_meta,
            }
            if vision_selection is not None:
                meta.update(vision_selection.metadata())

            async def _run_pdf(model: str):
                self._last_page_selection_meta = (
                    vision_selection.metadata() if vision_selection else {}
                )
                use_edges_first = total_pages >= 5 or (
                    total_pages > 2
                    and rendered_bytes > settings.openai_vision_full_document_max_bytes
                )
                prefer_dynamic = (
                    preclass.prefer_dynamic_vision is True
                    if settings.openai_preclassification_routing_enabled
                    else None
                )
                prefer_full = (
                    preclass.prefer_full_document_vision is True
                    if settings.openai_preclassification_routing_enabled
                    else False
                )

                if vision_selection is not None and not prefer_full:
                    dynamic = await self._extract_pdf_dynamic_selection(
                        filename,
                        page_images,
                        total_pages=total_pages,
                        model=model,
                        ctx=ctx,
                        use_edges_first=use_edges_first,
                        selection=vision_selection,
                        content=content,
                    )
                    if dynamic is not None:
                        r, m, mode = dynamic
                        r = await self._apply_post_vision_pipeline(
                            r,
                            ctx=ctx,
                            images=self._contiguous_images(page_images, total_pages)
                            if len(page_images) == total_pages
                            else list(page_images.values()),
                            filename=filename,
                            model=m,
                        )
                        return r, m, mode
                    if prefer_dynamic:
                        self._mark_routing_fallback()

                full_images = page_images
                if len(page_images) < total_pages:
                    full_images = self._render_additional_pages(
                        content,
                        dict(page_images),
                        list(range(1, total_pages + 1)),
                        total_pages=total_pages,
                    )
                ordered_images = self._contiguous_images(full_images, total_pages)

                if use_edges_first:
                    r, m, mode = await self._extract_pdf_edges_then_middle(
                        filename,
                        ordered_images,
                        total_pages=total_pages,
                        model=model,
                        ctx=ctx,
                    )
                else:
                    r, m, mode = await self._extract_pdf_pages(
                        filename,
                        ordered_images,
                        total_pages=total_pages,
                        model=model,
                        ctx=ctx,
                    )
                r = await self._apply_post_vision_pipeline(
                    r, ctx=ctx, images=ordered_images, filename=filename, model=m
                )
                return r, m, mode

            try:
                result, model_used, mode = await _run_pdf(self._model_routing.fast_model())
            except ExtractionError as exc:
                result, model_used, mode = await self._retry_strong_after_failure(
                    filename,
                    exc,
                    extract_fn=_run_pdf,
                )
            meta["extraction_mode"] = mode
            meta["model"] = model_used
            if mode in {"vision_first_last", "vision_dynamic"}:
                meta["pages_processed"] = self._last_page_selection_meta.get(
                    "selected_vision_pages",
                    min(2, len(images)),
                )
                if isinstance(meta["pages_processed"], list):
                    meta["pages_processed"] = len(meta["pages_processed"])
            elif mode == "vision_dynamic_fallback":
                meta["pages_processed"] = len(images)
            else:
                meta["pages_processed"] = len(images)
            if self._last_merge_ms is not None:
                meta["merge_ms"] = self._last_merge_ms
            meta.update(self._last_merge_meta)
            meta.update(self._last_page_selection_meta)
            meta.update(self._last_render_meta)
            meta.update(self._last_preclassification_meta)
            meta.update(self._image_detail_meta(total_pages))
            meta.update(self._prompt_meta(ctx, mode=mode))
            meta.update(self._pipeline_overlap_meta())
            return await self._maybe_retry_strong(
                filename,
                result,
                model_used,
                meta,
                extract_fn=_run_pdf,
                images=images,
                ctx=ctx,
            )

        # Direct image upload
        ctx = self._build_extraction_context(
            filename=filename, content=None, mime=mime
        )
        preclass = self._preclassification.classify(
            mime=mime,
            filename=filename,
            total_pages=1,
            hints=ctx.text_hints,
            document_category=ctx.document_category,
            page_texts=ctx.page_texts,
        )
        self._last_preclassification = preclass
        self._last_preclassification_meta = preclass.metadata()
        vision_mime = "image/jpeg" if mime == "image/jpg" else mime
        images = [(content, vision_mime)]

        async def _extract_image(model: str):
            self._update_progress(
                stage="openai_vision",
                stage_label="Extracting with Vision",
                model=model,
            )
            r = await self._openai_vision_call(
                images,
                filename=filename,
                file_type="image",
                model=model,
                page_range=None,
                total_pages=1,
                system_prompt=ctx.vision_system_prompt,
                supplemental_text=ctx.supplemental_text,
                document_category=ctx.document_category,
            )
            r = await self._apply_post_vision_pipeline(
                r, ctx=ctx, images=images, filename=filename, model=model
            )
            return r, model, "vision_single"

        try:
            result, model_used, mode = await _extract_image(self._model_routing.fast_model())
        except ExtractionError as exc:
            result, model_used, mode = await self._retry_strong_after_failure(
                filename,
                exc,
                extract_fn=_extract_image,
            )
        meta = {
            "pages_processed": 1,
            "total_pdf_pages": None,
            "rendered_image_bytes": len(content),
            "extraction_mode": mode,
            "model": model_used,
            "document_category": ctx.document_category.value,
            **self._prompt_meta(ctx, mode=mode),
            **self._image_detail_meta(1),
            **self._last_preclassification_meta,
        }
        return await self._maybe_retry_strong(
            filename,
            result,
            model_used,
            meta,
            extract_fn=_extract_image,
            images=images,
            ctx=ctx,
        )

    # ─────────────────────────────────────────────────────────────────────
    # PDF multi-page extraction
    # ─────────────────────────────────────────────────────────────────────

    @debug_trace
    async def _extract_pdf_with_pipeline_overlap(
        self,
        filename: str,
        content: bytes,
        *,
        total_pages: int,
        ctx: _ExtractionContext,
        preclass: PreclassificationResult,
        pages_to_render: list[int],
        skipped_render_pages: tuple[int, ...],
    ) -> tuple[ExtractionResult, str, dict, list[tuple[bytes, str]]]:
        """Render→Vision overlap for full-document paths; raises if not applicable."""
        model = self._model_routing.fast_model()
        if not self._page_analyses:
            self._page_analyses = analyze_pdf_pages(content)

        render_plan = build_adaptive_render_plan(
            total_pages=total_pages,
            pages_to_render=pages_to_render,
            analyses=self._page_analyses,
        )
        average_scale = (
            round(
                sum(plan.scale for plan in render_plan.pages) / len(render_plan.pages),
                3,
            )
            if render_plan.pages
            else settings.openai_pdf_render_scale
        )
        estimated_bytes = estimate_image_bytes(
            page_count=total_pages,
            average_scale=average_scale,
        )
        use_edges_first = total_pages >= 5 or (
            total_pages > 2
            and estimated_bytes > settings.openai_vision_full_document_max_bytes
        )
        per_request = max(1, settings.openai_vision_pages_per_request)

        if total_pages >= 5:
            self._pipeline_overlap.tasks.append("render_edges_during_vision")
            result, model_used, mode, page_images = await self._pipelined_edges_extract(
                filename,
                content,
                total_pages=total_pages,
                ctx=ctx,
                model=model,
                pages_to_render=pages_to_render,
                skipped_render_pages=skipped_render_pages,
            )
        elif total_pages > per_request:
            self._pipeline_overlap.tasks.append("render_batches_during_vision")
            result, model_used, mode, page_images = await self._pipelined_batched_extract(
                filename,
                content,
                total_pages=total_pages,
                ctx=ctx,
                model=model,
                pages_to_render=pages_to_render,
                skipped_render_pages=skipped_render_pages,
            )
        else:
            raise ExtractionError("pipeline_overlap_not_applicable")

        return await self._finalize_pipeline_overlap(
            result,
            model_used,
            mode,
            page_images,
            total_pages=total_pages,
            ctx=ctx,
            filename=filename,
        )

    async def _finalize_pipeline_overlap(
        self,
        result: ExtractionResult,
        model_used: str,
        mode: str,
        page_images: dict[int, tuple[bytes, str]],
        *,
        total_pages: int,
        ctx: _ExtractionContext,
        filename: str,
    ) -> tuple[ExtractionResult, str, dict, list[tuple[bytes, str]]]:
        ordered_images = self._contiguous_images(page_images, total_pages)
        result = await self._apply_post_vision_pipeline(
            result,
            ctx=ctx,
            images=ordered_images,
            filename=filename,
            model=model_used,
        )
        render_meta = dict(self._last_render_meta)
        meta: dict = {
            "pages_processed": len(ordered_images),
            "total_pdf_pages": total_pages,
            "document_category": ctx.document_category.value,
            "text_layer_chars": len(ctx.text_hints.raw_text),
            "text_extraction_ms": ctx.text_extraction_ms,
            "document_classification_ms": ctx.document_classification_ms,
            "extraction_mode": mode,
            "model": model_used,
            **render_meta,
            **self._text_first_skip_meta(),
            **self._last_preclassification_meta,
            **self._pipeline_overlap_meta(),
        }
        if mode in {"vision_first_last", "vision_dynamic"}:
            meta["pages_processed"] = self._last_page_selection_meta.get(
                "selected_vision_pages",
                min(2, len(ordered_images)),
            )
            if isinstance(meta["pages_processed"], list):
                meta["pages_processed"] = len(meta["pages_processed"])
        if self._last_merge_ms is not None:
            meta["merge_ms"] = self._last_merge_ms
        meta.update(self._last_merge_meta)
        meta.update(self._last_page_selection_meta)
        meta.update(self._last_render_meta)
        meta.update(self._image_detail_meta(total_pages))
        meta.update(self._prompt_meta(ctx, mode=mode))
        return result, model_used, meta, ordered_images

    async def _run_pdf_pipelined(
        self,
        model: str,
        filename: str,
        content: bytes,
        *,
        total_pages: int,
        ctx: _ExtractionContext,
        pages_to_render: list[int],
        skipped_render_pages: tuple[int, ...],
        use_edges_first: bool,
    ) -> tuple[ExtractionResult, str, str, dict[int, tuple[bytes, str]]]:
        if use_edges_first and total_pages >= 5:
            return await self._pipelined_edges_extract(
                filename,
                content,
                total_pages=total_pages,
                ctx=ctx,
                model=model,
                pages_to_render=pages_to_render,
                skipped_render_pages=skipped_render_pages,
            )
        per_request = max(1, settings.openai_vision_pages_per_request)
        if total_pages > per_request:
            return await self._pipelined_batched_extract(
                filename,
                content,
                total_pages=total_pages,
                ctx=ctx,
                model=model,
                pages_to_render=pages_to_render,
                skipped_render_pages=skipped_render_pages,
            )
        raise ExtractionError("pipeline_overlap_not_applicable")

    async def _pipelined_edges_extract(
        self,
        filename: str,
        content: bytes,
        *,
        total_pages: int,
        ctx: _ExtractionContext,
        model: str,
        pages_to_render: list[int],
        skipped_render_pages: tuple[int, ...],
    ) -> tuple[ExtractionResult, str, str, dict[int, tuple[bytes, str]]]:
        """Render edge pages, start Vision, render middle pages concurrently."""
        edge_page_nums = [1] if total_pages == 1 else [1, total_pages]
        edge_to_render = [p for p in edge_page_nums if p in pages_to_render]
        middle_to_render = [p for p in pages_to_render if p not in edge_page_nums]

        self._update_progress(
            stage="rendering_pdf",
            stage_label="Rendering edge pages",
        )
        edge_images, edge_meta = self._render_page_numbers(
            content,
            edge_to_render,
            total_pages=total_pages,
            skipped_pages=skipped_render_pages,
        )
        self._last_render_meta = edge_meta

        middle_render_task: asyncio.Task | None = None
        if middle_to_render:
            self._pipeline_overlap.parallel_sections.append(
                "render_middle_during_vision"
            )

            async def _render_middle() -> dict[int, tuple[bytes, str]]:
                images, extra_meta = await asyncio.to_thread(
                    self._render_page_numbers,
                    content,
                    middle_to_render,
                    total_pages=total_pages,
                    skipped_pages=skipped_render_pages,
                )
                self._last_render_meta["render_ms"] = round(
                    float(self._last_render_meta.get("render_ms") or 0)
                    + float(extra_meta.get("render_ms") or 0),
                    1,
                )
                return images

            middle_render_task = asyncio.create_task(_render_middle())

        edge_list = [edge_images[p] for p in edge_to_render]
        result, model_used, mode = await self._extract_pdf_edges_then_middle(
            filename,
            edge_list,
            total_pages=total_pages,
            model=model,
            ctx=ctx,
            pending_render_task=middle_render_task,
            page_images=edge_images,
        )
        all_images = dict(edge_images)
        if middle_render_task is not None:
            if not middle_render_task.done():
                all_images.update(await middle_render_task)
            else:
                all_images.update(middle_render_task.result())
        return result, model_used, mode, all_images

    async def _pipelined_batched_extract(
        self,
        filename: str,
        content: bytes,
        *,
        total_pages: int,
        ctx: _ExtractionContext,
        model: str,
        pages_to_render: list[int],
        skipped_render_pages: tuple[int, ...],
    ) -> tuple[ExtractionResult, str, str, dict[int, tuple[bytes, str]]]:
        """Render first batch, start Vision, render remaining pages concurrently."""
        batch_size = max(1, settings.openai_vision_page_batch_size)
        first_page_nums = list(range(1, min(batch_size, total_pages) + 1))
        rest_page_nums = list(range(min(batch_size, total_pages) + 1, total_pages + 1))

        self._update_progress(
            stage="rendering_pdf",
            stage_label="Rendering first page batch",
        )
        first_images, first_meta = self._render_page_numbers(
            content,
            first_page_nums,
            total_pages=total_pages,
            skipped_pages=skipped_render_pages,
        )
        self._last_render_meta = first_meta
        self._pipeline_overlap.parallel_sections.append(
            "render_remaining_during_vision"
        )

        async def _render_rest() -> dict[int, tuple[bytes, str]]:
            if not rest_page_nums:
                return {}
            images, extra_meta = await asyncio.to_thread(
                self._render_page_numbers,
                content,
                rest_page_nums,
                total_pages=total_pages,
                skipped_pages=skipped_render_pages,
            )
            self._last_render_meta["render_ms"] = round(
                float(self._last_render_meta.get("render_ms") or 0)
                + float(extra_meta.get("render_ms") or 0),
                1,
            )
            return images

        rest_render_task = asyncio.create_task(_render_rest())
        first_batch = [first_images[p] for p in first_page_nums]

        self._update_progress(
            stage="openai_vision",
            stage_label="Extracting first page batch",
            model=model,
        )
        first_partial = await self._openai_vision_call(
            first_batch,
            filename=filename,
            file_type="pdf",
            model=model,
            page_range=(1, len(first_batch)),
            total_pages=total_pages,
            system_prompt=ctx.batch_system_prompt,
            supplemental_text=ctx.supplemental_text,
            document_category=ctx.document_category,
        )

        rest_images = await rest_render_task
        all_images = {**first_images, **rest_images}
        ordered = self._contiguous_images(all_images, total_pages)
        result, model_used, mode = await self._extract_pdf_pages_after_first(
            filename,
            ordered,
            total_pages=total_pages,
            model=model,
            ctx=ctx,
            first_partial=first_partial,
        )
        return result, model_used, mode, all_images

    @debug_trace
    async def _extract_pdf_pages_after_first(
        self,
        filename: str,
        images: list[tuple[bytes, str]],
        *,
        total_pages: int,
        model: str,
        ctx: _ExtractionContext,
        first_partial: ExtractionResult,
    ) -> tuple[ExtractionResult, str, str]:
        """Continue batched extraction after the first batch was extracted during render."""
        batch_size = max(1, settings.openai_vision_page_batch_size)
        batch_prompt = ctx.batch_system_prompt
        category = ctx.document_category
        supplemental = ctx.supplemental_text

        partials: list[ExtractionResult] = [first_partial]
        header_context: str | None = None
        if first_partial.name_of_company or first_partial.invoice_number:
            parts = []
            if first_partial.name_of_company:
                parts.append(f"Issuer: {first_partial.name_of_company}")
            if first_partial.invoice_number:
                parts.append(f"Invoice #: {first_partial.invoice_number}")
            if first_partial.invoice_date:
                parts.append(f"Date: {first_partial.invoice_date}")
            header_context = " | ".join(parts) if parts else None

        batches: list[tuple[int, int, list[tuple[bytes, str]]]] = []
        for start in range(0, len(images), batch_size):
            batch = images[start : start + batch_size]
            page_start = start + 1
            page_end = start + len(batch)
            if page_start == 1:
                continue
            batches.append((page_start, page_end, batch))

        if batches:
            concurrency = max(1, settings.openai_page_batch_concurrency)
            semaphore = asyncio.Semaphore(concurrency)
            self._update_progress(
                stage="openai_vision",
                stage_label="Extracting remaining page batches",
                model=model,
            )

            async def _extract_batch(
                page_start: int,
                page_end: int,
                batch: list[tuple[bytes, str]],
            ) -> ExtractionResult:
                async with semaphore:
                    return await self._openai_vision_call(
                        batch,
                        filename=filename,
                        file_type="pdf",
                        model=model,
                        page_range=(page_start, page_end),
                        total_pages=total_pages,
                        system_prompt=batch_prompt,
                        context_hint=header_context,
                        document_category=category,
                    )

            partials.extend(
                await asyncio.gather(
                    *(_extract_batch(*batch_info) for batch_info in batches)
                )
            )

        merged = await self._merge_partial_extractions(
            partials, total_pages=total_pages, model=model
        )
        return merged, model, "vision_batched_merge"

    @debug_trace
    async def _extract_pdf_dynamic_selection(
        self,
        filename: str,
        page_images: dict[int, tuple[bytes, str]],
        *,
        total_pages: int,
        model: str,
        ctx: _ExtractionContext,
        use_edges_first: bool,
        selection: VisionPageSelection,
        content: bytes,
    ) -> tuple[ExtractionResult, str, str] | None:
        """Run Vision on pre-selected pages; None triggers wider fallback."""
        self._last_page_selection_meta = selection.metadata()

        if len(selection.selected_pages) >= total_pages:
            return None

        selected_images = [
            page_images[page_num]
            for page_num in selection.selected_pages
            if page_num in page_images
        ]
        if len(selected_images) != len(selection.selected_pages):
            return None

        vision_prompt = ctx.vision_system_prompt
        category = ctx.document_category
        supplemental = ctx.supplemental_text

        self._update_progress(
            stage="openai_vision",
            stage_label="Extracting selected pages",
            model=model,
        )
        logger.info(
            "Dynamic Vision page selection for %r: selected=%s skipped=%s strategy=%s",
            filename,
            list(selection.selected_pages),
            list(selection.skipped_pages),
            selection.strategy,
        )

        result = await self._openai_vision_call(
            selected_images,
            filename=filename,
            file_type="pdf",
            model=model,
            page_range=None,
            page_numbers=list(selection.selected_pages),
            total_pages=total_pages,
            system_prompt=vision_prompt,
            supplemental_text=supplemental,
            document_category=category,
        )
        result = self._ai_validation.sanitize_and_validate(result)
        missing = self._ai_validation.validate_required_fields(result)
        suspicious = self._ai_validation.detect_suspicious_values(result)
        if not missing and not suspicious:
            return result, model, "vision_dynamic"

        if not selection.skipped_pages:
            return None

        logger.info(
            "Dynamic Vision insufficient for %r — falling back (missing=%s suspicious=%s)",
            filename,
            missing,
            suspicious,
        )
        self._last_page_selection_meta = {
            **selection.metadata(),
            "dynamic_fallback_reason": {
                "missing": missing,
                "suspicious": suspicious,
            },
        }

        expanded = self._render_additional_pages(
            content,
            dict(page_images),
            list(range(1, total_pages + 1)),
            total_pages=total_pages,
        )
        ordered_images = self._contiguous_images(expanded, total_pages)

        if use_edges_first:
            result, model, mode = await self._extract_pdf_edges_then_middle(
                filename,
                ordered_images,
                total_pages=total_pages,
                model=model,
                ctx=ctx,
            )
            self._mark_routing_fallback()
            return result, model, "vision_dynamic_fallback"

        result, model, mode = await self._extract_pdf_pages(
            filename,
            ordered_images,
            total_pages=total_pages,
            model=model,
            ctx=ctx,
        )
        self._mark_routing_fallback()
        return result, model, "vision_dynamic_fallback"

    @debug_trace
    async def _extract_pdf_edges_then_middle(
        self,
        filename: str,
        images: list[tuple[bytes, str]],
        *,
        total_pages: int,
        model: str,
        ctx: _ExtractionContext,
        pending_render_task: asyncio.Task | None = None,
        page_images: dict[int, tuple[bytes, str]] | None = None,
    ) -> tuple[ExtractionResult, str, str]:
        """Extract first/last pages before paying to read middle pages."""
        vision_prompt = ctx.vision_system_prompt
        category = ctx.document_category
        supplemental = ctx.supplemental_text

        self._update_progress(
            stage="openai_vision",
            stage_label="Extracting first and last pages",
            model=model,
        )

        first_task = self._openai_vision_call(
            [images[0]],
            filename=filename,
            file_type="pdf",
            model=model,
            page_range=(1, 1),
            total_pages=total_pages,
            system_prompt=vision_prompt,
            supplemental_text=supplemental,
            document_category=category,
        )
        last_task = self._openai_vision_call(
            [images[-1]],
            filename=filename,
            file_type="pdf",
            model=model,
            page_range=(total_pages, total_pages),
            total_pages=total_pages,
            system_prompt=vision_prompt,
            context_hint="Final page: focus on totals, payment details, and bank accounts.",
            document_category=category,
        )
        partials = list(await asyncio.gather(first_task, last_task))
        merged = await self._merge_partial_extractions(
            partials, total_pages=total_pages, model=model
        )
        merged = self._ai_validation.sanitize_and_validate(merged)
        missing = self._ai_validation.validate_required_fields(merged)
        suspicious = self._ai_validation.detect_suspicious_values(merged)
        if not missing and not suspicious:
            logger.info(
                "PDF first/last extraction sufficient for %r (pages=%d)",
                filename,
                total_pages,
            )
            if pending_render_task is not None:
                await pending_render_task
            return merged, model, "vision_first_last"

        middle_images = images[1:-1]
        if pending_render_task is not None and page_images is not None:
            extra = await pending_render_task
            page_images = {**page_images, **extra}
            ordered = self._contiguous_images(page_images, total_pages)
            middle_images = ordered[1:-1]

        if not middle_images:
            return merged, model, "vision_first_last"

        self._update_progress(
            stage="openai_vision",
            stage_label="Extracting middle pages",
            model=model,
        )
        logger.info(
            "PDF first/last needed middle pages for %r: missing=%s suspicious=%s",
            filename,
            missing,
            suspicious,
        )
        middle = await self._openai_vision_call(
            middle_images,
            filename=filename,
            file_type="pdf",
            model=model,
            page_range=(2, total_pages - 1),
            total_pages=total_pages,
            system_prompt=ctx.batch_system_prompt,
            context_hint=self._context_hint_from_result(partials[0]),
            document_category=category,
        )
        partials.insert(1, middle)
        merged = await self._merge_partial_extractions(
            partials, total_pages=total_pages, model=model
        )
        return merged, model, "vision_first_last_middle"

    def _context_hint_from_result(self, result: ExtractionResult) -> str | None:
        parts = []
        if result.name_of_company:
            parts.append(f"Issuer: {result.name_of_company}")
        if result.invoice_number:
            parts.append(f"Invoice #: {result.invoice_number}")
        if result.invoice_date:
            parts.append(f"Date: {result.invoice_date}")
        return " | ".join(parts) if parts else None

    @debug_trace
    async def _extract_pdf_pages(
        self,
        filename: str,
        images: list[tuple[bytes, str]],
        *,
        total_pages: int,
        model: str | None = None,
        ctx: _ExtractionContext | None = None,
    ) -> tuple[ExtractionResult, str, str]:
        model = model or self._model_routing.fast_model()
        per_request = max(1, settings.openai_vision_pages_per_request)
        batch_size = max(1, settings.openai_vision_page_batch_size)
        vision_prompt = ctx.vision_system_prompt if ctx else VISION_SYSTEM_PROMPT
        batch_prompt = ctx.batch_system_prompt if ctx else build_batch_system_prompt()
        supplemental = ctx.supplemental_text if ctx else None
        category = ctx.document_category if ctx else None

        # Single request — all pages fit in one call
        if len(images) <= per_request:
            self._update_progress(
                stage="openai_vision",
                stage_label="Extracting invoice pages",
                model=model,
            )
            result = await self._openai_vision_call(
                images,
                filename=filename,
                file_type="pdf",
                model=model,
                page_range=(1, len(images)),
                total_pages=total_pages,
                system_prompt=vision_prompt,
                supplemental_text=supplemental,
                document_category=category,
            )
            return result, model, "vision_full_document"

        # Batched extraction. The first batch still runs first so we can keep
        # the issuer/invoice context hint; remaining batches run concurrently
        # with a small per-upload cap to avoid rate-limit spikes.
        partials: list[ExtractionResult] = []
        header_context: str | None = None  # carry issuer + invoice # from batch 1
        batches: list[tuple[int, int, list[tuple[bytes, str]]]] = []

        for start in range(0, len(images), batch_size):
            batch = images[start : start + batch_size]
            page_start = start + 1
            page_end = start + len(batch)
            batches.append((page_start, page_end, batch))

        first_page_start, first_page_end, first_batch = batches[0]
        self._update_progress(
            stage="openai_vision",
            stage_label="Extracting first page batch",
            model=model,
        )
        first_partial = await self._openai_vision_call(
            first_batch,
            filename=filename,
            file_type="pdf",
            model=model,
            page_range=(first_page_start, first_page_end),
            total_pages=total_pages,
            system_prompt=batch_prompt,
            context_hint=None,
            supplemental_text=supplemental if first_page_start == 1 else None,
            document_category=category,
        )
        partials.append(first_partial)

        # After first batch: build context hint so later batches know the issuer.
        if first_partial.name_of_company or first_partial.invoice_number:
            parts = []
            if first_partial.name_of_company:
                parts.append(f"Issuer: {first_partial.name_of_company}")
            if first_partial.invoice_number:
                parts.append(f"Invoice #: {first_partial.invoice_number}")
            if first_partial.invoice_date:
                parts.append(f"Date: {first_partial.invoice_date}")
            header_context = " | ".join(parts) if parts else None

        remaining_batches = batches[1:]
        if remaining_batches:
            concurrency = max(1, settings.openai_page_batch_concurrency)
            semaphore = asyncio.Semaphore(concurrency)
            logger.info(
                "PDF OCR page batches filename=%r batches=%d concurrency=%d",
                filename,
                len(batches),
                concurrency,
            )
            self._update_progress(
                stage="openai_vision",
                stage_label="Extracting remaining page batches",
                model=model,
            )

            async def _extract_batch(
                page_start: int,
                page_end: int,
                batch: list[tuple[bytes, str]],
            ) -> ExtractionResult:
                async with semaphore:
                    return await self._openai_vision_call(
                        batch,
                        filename=filename,
                        file_type="pdf",
                        model=model,
                        page_range=(page_start, page_end),
                        total_pages=total_pages,
                        system_prompt=batch_prompt,
                        context_hint=header_context,
                        document_category=category,
                    )

            # asyncio.gather preserves input order, so merge semantics remain deterministic.
            partials.extend(
                await asyncio.gather(
                    *(_extract_batch(*batch_info) for batch_info in remaining_batches)
                )
            )

        merged = await self._merge_partial_extractions(
            partials, total_pages=total_pages, model=model
        )
        return merged, model, "vision_batched_merge"

    @debug_trace
    async def _merge_partial_extractions(
        self,
        partials: list[ExtractionResult],
        *,
        total_pages: int,
        model: str,
    ) -> ExtractionResult:
        if len(partials) == 1:
            return partials[0]

        self._update_progress(stage="merging", stage_label="Merging page results")
        merge_t0 = time.perf_counter()

        outcome = self._deterministic_merge.merge_partials(partials)
        self._last_merge_meta = outcome.metadata()

        if not outcome.use_llm and outcome.result is not None:
            self._last_merge_ms = round((time.perf_counter() - merge_t0) * 1000, 1)
            self._update_progress(merge_ms=self._last_merge_ms)
            logger.info(
                "Deterministic merge for %d partials (pages=%d) conflicts=%s",
                len(partials),
                total_pages,
                outcome.conflicts,
            )
            return outcome.result

        payload = [p.model_dump() for p in partials]
        user_text = (
            f"Merge these {len(partials)} partial Vision extractions from a "
            f"{total_pages}-page invoice into one final JSON.\n\n"
            f"Partials (index = page batch order, 0 = first pages):\n"
            f"{json.dumps(payload, indent=2, default=str)}"
        )
        if outcome.conflicts:
            user_text += (
                "\n\nDeterministic merge notes (conflicts to resolve):\n"
                + "\n".join(f"- {item}" for item in outcome.conflicts)
            )
        merge_prompt = build_merge_system_prompt()

        async def _llm_merge() -> ExtractionResult:
            response = await self._chat_completion(
                model=model,
                messages=[
                    {"role": "system", "content": merge_prompt},
                    {"role": "user", "content": user_text},
                ],
            )
            return self._parse_response(response.choices[0].message.content or "{}")

        async def _validation_prep():
            self._pipeline_overlap.tasks.append("validation_prep")
            return build_validation_prep(partials)

        if self._pipeline_overlap.enabled:
            merged, prep = await run_parallel(
                _llm_merge,
                _validation_prep,
                section="merge_validation_prep",
                tracker=self._pipeline_overlap,
            )
            if prep is not None:
                self._pipeline_overlap.validation_prep = prep
        else:
            merged = await _llm_merge()

        self._last_merge_ms = round((time.perf_counter() - merge_t0) * 1000, 1)
        self._last_merge_meta["merge_strategy"] = "llm"
        self._last_merge_meta["prompt_strategy"] = prompt_strategy_label(mode="merge")
        self._last_merge_meta["estimated_prompt_tokens"] = estimate_prompt_tokens(
            merge_prompt,
            user_text,
        )
        self._update_progress(merge_ms=self._last_merge_ms)
        logger.info(
            "LLM merge for %d partials (pages=%d) reason=%s",
            len(partials),
            total_pages,
            outcome.conflicts or outcome.missing_fields,
        )
        return merged

    # ─────────────────────────────────────────────────────────────────────
    # Retry with strong model
    # ─────────────────────────────────────────────────────────────────────

    @debug_trace
    async def _retry_strong_after_failure(
        self,
        filename: str,
        exc: ExtractionError,
        *,
        extract_fn,
    ) -> tuple[ExtractionResult, str, str]:
        """Retry invalid JSON or failed primary extraction only when enabled."""
        strong = self._model_routing.strong_model()
        if (
            not settings.openai_strong_retry_enabled
            or strong == self._model_routing.fast_model()
        ):
            raise exc
        logger.info(
            "Retrying %s with %s after primary extraction failed: %s",
            filename,
            strong,
            exc,
        )
        self._reset_image_detail_tracking()
        return await extract_fn(strong)

    @debug_trace
    async def _maybe_retry_strong(
        self,
        filename: str,
        result: ExtractionResult,
        model_used: str,
        meta: dict,
        *,
        extract_fn,
        images: list[tuple[bytes, str]] | None = None,
        ctx: _ExtractionContext | None = None,
    ) -> tuple[ExtractionResult, str, dict]:
        result = self._ai_validation.sanitize_and_validate(result)
        missing = self._ai_validation.validate_required_fields(result)
        suspicious = self._ai_validation.detect_suspicious_values(result)
        logger.debug(
            "Retry check: confidence=%.3f (float) missing=%s (%s) suspicious=%s (%s)",
            result.confidence_score,
            missing, type(missing).__name__,
            suspicious, type(suspicious).__name__,
        )

        should_retry, retry_reasons = self._model_routing.should_use_strong_fallback(
            result,
            meta,
        )

        if should_retry:
            strong = self._model_routing.strong_model()
            logger.info(
                "Strong-model retry for %s: model=%s reasons=%s",
                filename,
                strong,
                retry_reasons,
            )
            meta["strong_retry_reasons"] = retry_reasons
            self._reset_image_detail_tracking()
            retry_result, retry_model, retry_mode = await extract_fn(strong)
            retry_result = self._ai_validation.sanitize_and_validate(retry_result)
            retry_missing = self._ai_validation.validate_required_fields(retry_result)
            retry_suspicious = self._ai_validation.detect_suspicious_values(retry_result)

            # Keep retry if it is strictly better
            retry_is_better = (
                retry_result.confidence_score > result.confidence_score
                or (missing and not retry_missing)
                or (suspicious and not retry_suspicious)
            )
            if retry_is_better:
                meta["extraction_mode"] = retry_mode
                meta["model"] = retry_model
                meta.update(
                    self._model_routing.fallback_metadata(
                        fallback_reason=",".join(retry_reasons),
                    )
                )
                meta.update(
                    self._image_detail_meta(meta.get("total_pdf_pages"))
                )
                return retry_result, retry_model, meta

        if "model_strategy" not in meta:
            meta.update(
                self._model_routing.primary_metadata(
                    mode=str(meta.get("extraction_mode", "")),
                    model_used=model_used,
                )
            )
        meta["model"] = model_used
        return result, model_used, meta

    # ─────────────────────────────────────────────────────────────────────
    # Core Vision API call
    # ─────────────────────────────────────────────────────────────────────

    @debug_trace
    async def _openai_vision_extract(
        self,
        images: list[tuple[bytes, str]],
        *,
        filename: str,
        file_type: str,
        model: str,
        page_range: tuple[int, int] | None,
        total_pages: int,
        page_numbers: list[int] | None = None,
        system_prompt: str = VISION_SYSTEM_PROMPT,
        context_hint: str | None = None,
        supplemental_text: str | None = None,
        document_category: DocumentCategory | None = None,
    ) -> ExtractionResult:
        if page_numbers:
            if len(page_numbers) == 1:
                scope = (
                    f"Page {page_numbers[0]} of {total_pages}."
                    if total_pages > 1
                    else "Single page document."
                )
            else:
                listed = ", ".join(str(p) for p in page_numbers)
                scope = f"Pages {listed} of {total_pages}."
        elif page_range:
            start, end = page_range
            scope = (
                f"Pages {start}–{end} of {total_pages}."
                if total_pages > 1
                else "Single page document."
            )
        else:
            scope = "Single image document."

        doc_type_hint = (
            "Multi-page PDF invoice" if total_pages > 1
            else ("PDF invoice" if file_type == "pdf" else "Image invoice")
        )

        # Build structured instruction
        instruction_parts = [
            f"Document: {filename}",
            f"Type: {doc_type_hint}",
            f"Scope: {scope}",
        ]
        if context_hint:
            instruction_parts.append(
                f"Context from earlier pages of this document: {context_hint}"
            )
        if document_category is not None:
            instruction_parts.append(
                f"Classified document category: {document_category.value}"
            )
        if supplemental_text:
            capped, _ = _cap_vision_supplemental_text(supplemental_text)
            instruction_parts += [
                "",
                "Supplemental PDF text (cross-check with images):",
                capped or "",
            ]
        instruction_parts += [
            "",
            "Return one JSON object per the system prompt. Read all images before answering.",
        ]
        if total_pages > 1 and (page_range or page_numbers):
            if page_numbers:
                p_start = page_numbers[0]
                p_end = page_numbers[-1]
                includes_first = 1 in page_numbers
                includes_last = total_pages in page_numbers
            else:
                p_start, p_end = page_range  # type: ignore[misc]
                includes_first = p_start == 1
                includes_last = p_end == total_pages

            if (
                includes_first
                and includes_last
                and len(page_numbers or images) == total_pages
            ):
                instruction_parts.append(
                    f"All {total_pages} pages included — amount and IBAN from final page only."
                )
            elif includes_last and p_end == total_pages:
                instruction_parts.append(
                    "Selected pages include the final page — capture totals and payment details."
                )
            elif includes_first and p_start == 1:
                instruction_parts.append(
                    "Selected pages include the first page — capture header fields; amount null unless shown."
                )
            else:
                instruction_parts.append(
                    "Selected middle pages — line items only; amount null unless totals visible."
                )

        user_content: list[dict] = [
            {"type": "text", "text": "\n".join(instruction_parts)},
        ]

        for index, (img_bytes, mime) in enumerate(images, start=1):
            if page_numbers:
                page_num = page_numbers[index - 1]
            elif page_range:
                page_num = page_range[0] + index - 1
            else:
                page_num = index
            if len(images) > 1 or total_pages > 1:
                # Label each page with its role so the model knows where to look
                if total_pages > 1:
                    is_first = page_num == 1
                    is_last = page_num == total_pages
                    if is_first and is_last:
                        role = "only page"
                    elif is_first:
                        role = "HEADER PAGE — issuer, invoice number, invoice date, client block"
                    elif is_last:
                        role = "FINAL PAGE — grand total, VAT, Zahlbetrag, IBAN, bank details"
                    else:
                        role = "LINE-ITEMS PAGE — do not use item prices as the invoice amount"
                    label = f"─── Page {page_num} of {total_pages} ({role}) ───"
                else:
                    label = f"─── Page {page_num} of {total_pages} ───"
                user_content.append({"type": "text", "text": label})
            b64 = base64.standard_b64encode(img_bytes).decode("ascii")
            detail = _image_detail_for_page(page_num, total_pages)
            self._record_image_detail_page(page_num, detail)
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime};base64,{b64}",
                        "detail": detail,
                    },
                }
            )

        response = await self._chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            timeout_seconds=self._vision_timeout(len(images)),
        )
        return self._parse_response(response.choices[0].message.content or "{}")

    # ─────────────────────────────────────────────────────────────────────
    # OpenAI API wrapper
    # ─────────────────────────────────────────────────────────────────────

    @debug_trace
    def _vision_timeout(self, page_count: int) -> float:
        base = float(settings.openai_timeout_seconds)
        return min(300.0, base + page_count * 20.0)

    @debug_trace
    def _max_output_tokens(self, model: str) -> int:
        if is_reasoning_model(model):
            return settings.openai_reasoning_max_completion_tokens
        return _MAX_TOKENS

    @debug_trace
    async def _chat_completion(
        self, *, model: str, messages: list, timeout_seconds: float | None = None
    ):
        timeout = timeout_seconds or float(settings.openai_timeout_seconds)
        last_exc: Exception | None = None
        attempts = max(1, settings.openai_max_retries)
        token_budget = self._max_output_tokens(model)
        for attempt in range(attempts):
            try:
                openai_t0 = time.perf_counter()
                response = await self._openai.chat.completions.create(
                    model=model,
                    timeout=timeout,
                    messages=messages,
                    **chat_completion_kwargs(
                        model,
                        max_output_tokens=token_budget,
                        temperature=0,
                        response_format={"type": "json_object"},
                    ),
                )
                openai_ms = round((time.perf_counter() - openai_t0) * 1000, 1)
                self._openai_timings.append(
                    {
                        "model": model,
                        "attempt": attempt + 1,
                        "openai_ms": openai_ms,
                        "content_len": len((response.choices[0].message.content or "").strip()),
                    }
                )
                choice = response.choices[0]
                content = (choice.message.content or "").strip()
                logger.info(
                    "OpenAI OCR call complete model=%s attempt=%d openai_ms=%s finish_reason=%s content_len=%d",
                    model,
                    attempt + 1,
                    openai_ms,
                    choice.finish_reason,
                    len(content),
                )
                if (
                    is_reasoning_model(model)
                    and not content
                    and choice.finish_reason == "length"
                ):
                    logger.warning(
                        "OpenAI %s hit token limit with empty JSON (reasoning "
                        "consumed budget=%d); retrying with larger budget",
                        model,
                        token_budget,
                    )
                    token_budget = min(token_budget * 2, 32000)
                    continue
                if is_reasoning_model(model) and not content:
                    logger.warning(
                        "OpenAI %s returned empty content (finish_reason=%s)",
                        model,
                        choice.finish_reason,
                    )
                    if attempt + 1 < attempts:
                        continue
                return response
            except RateLimitError as exc:
                last_exc = exc
                if attempt + 1 >= attempts:
                    raise ExtractionError(
                        "OpenAI rate limit reached; try again shortly"
                    ) from exc
            except APIConnectionError as exc:
                last_exc = exc
                if attempt + 1 >= attempts:
                    raise ExtractionError("Cannot reach OpenAI API") from exc
            except APIStatusError as exc:
                last_exc = exc
                if exc.status_code and exc.status_code >= 500 and attempt + 1 < attempts:
                    continue
                if exc.status_code and exc.status_code >= 500:
                    raise ExtractionError("OpenAI service unavailable") from exc
                raise ExtractionError(f"OpenAI error: {exc}") from exc
        raise ExtractionError("OpenAI request failed") from last_exc

    @debug_trace
    def _parse_response(self, raw: str) -> ExtractionResult:
        # Strip any accidental markdown fences from the response
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(
                l for l in lines if not l.strip().startswith("```")
            ).strip()
        try:
            data = json.loads(cleaned)
            logger.debug(
                "Parsed OpenAI JSON: keys=%s (%s, len=%d)",
                list(data.keys()), type(data).__name__, len(data),
            )
            if data.get("amount") is not None:
                before_amount = data["amount"]
                normalized = self._ai_validation._normalize_amount(data["amount"])
                logger.debug(
                    "Amount normalization: %r (%s) -> %r (%s)",
                    before_amount, type(before_amount).__name__,
                    normalized, type(normalized).__name__,
                )
                data["amount"] = normalized
            if data.get("debt") is not None:
                data["debt"] = self._ai_validation._normalize_amount(data["debt"])
            if data.get("confidence_score") is not None:
                data["confidence_score"] = float(data["confidence_score"])
            result = ExtractionResult.model_validate(data)
            return self._ai_validation.sanitize_and_validate(result)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ExtractionError(f"Invalid OpenAI response: {exc}") from exc
