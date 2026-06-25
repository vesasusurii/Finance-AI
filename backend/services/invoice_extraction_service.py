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
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from core.document_types import resolve_document_mime
from fastapi import UploadFile
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from config import settings
from core.debug_logger import debug_trace, get_logger, log_typed_fields
from core.exceptions import ExtractionError
from repositories.audit_repository import AuditRepository
from repositories.invoice_access_repository import InvoiceAccessRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.upload_repository import UploadRepository
from utils.content_hash import sha256_hex
from schemas.auth import UserContext
from schemas.invoice import ExtractionResult, UploadItemResponse
from ai.prompts import MERGE_SYSTEM_PROMPT, VISION_SYSTEM_PROMPT
from ai.prompts.builders.prompt_builder import (
    build_batch_system_prompt,
    build_vision_system_prompt,
)
from core.document_categories import DocumentCategory
from services.ai_validation_service import AIValidationService
from services.document_classifier_service import DocumentClassifierService
from services.field_recovery_service import FieldRecoveryService
from services.hybrid_extraction_service import HybridExtractionService
from services.text_first_extraction_service import TextFirstExtractionService
from services.ocr.pdf_text_extractor import (
    TextLayerHints,
    extract_pdf_text,
    parse_text_layer_hints,
)
from services.ocr.pdf_reader import (
    pdf_is_encrypted,
    pdf_page_count,
    render_pdf_pages_as_images,
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

# Retry with the strong model when confidence is below this threshold
# OR when any critical field is missing.
VISION_RETRY_CONFIDENCE = 0.82

# GPT-4 output budget; GPT-5/o-series also spend tokens on internal reasoning first.
_MAX_TOKENS = 2400


@dataclass(frozen=True)
class _ExtractionContext:
    document_category: DocumentCategory
    text_hints: TextLayerHints
    supplemental_text: str | None
    vision_system_prompt: str
    batch_system_prompt: str


@dataclass(frozen=True)
class PreparedUpload:
    upload_id: int
    stored_filename: str
    mime: str
    storage_path: str
    file_size: int
    content: bytes | None = None


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
        self._text_first = TextFirstExtractionService(openai_client, ai_validation)

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
        upload_source: str = "portal",
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
                    upload_source=upload_source,
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
        upload_row = await self._upload_repo.get(upload_id)
        if upload_row is None:
            raise ExtractionError(f"Upload {upload_id} not found")

        content_source = "memory"
        storage_download_ms = 0.0
        if content is None:
            content_source = "storage"
            storage_t0 = time.perf_counter()
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

        try:
            extract_t0 = time.perf_counter()
            result, model_used, meta = await self._extract(
                stored_filename, mime, content
            )
            extract_ms = round((time.perf_counter() - extract_t0) * 1000, 1)
            meta["ocr_ms"] = extract_ms
            meta["storage_download_ms"] = storage_download_ms
            logger.info(
                "OCR extract finished upload_id=%d ocr_ms=%s model=%s mode=%s",
                upload_id,
                extract_ms,
                model_used,
                meta.get("extraction_mode"),
            )
            log_typed_fields(logger, "OCR raw extraction", result)
            logger.debug("OCR meta: %r model_used=%r", meta, model_used)

            result = self._ai_validation.sanitize_and_validate(result)
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

            invoice = await self._invoice_repo.create(
                result, upload_row.id, review_status, uploaded_by=user_id
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
            await self._upload_repo.update_status(upload_row.id, "processed")
            return UploadItemResponse(
                upload_id=upload_row.id,
                original_filename=stored_filename,
                processing_status="processed",
                invoice_id=invoice.id,
            )
        except Exception as exc:
            logger.exception("Extraction failed for upload_id=%d", upload_id)
            await self._upload_repo.update_status(upload_row.id, "failed")
            raise ExtractionError(str(exc)) from exc

    def _prepared_from_row(self, upload_row, mime: str) -> PreparedUpload:
        resolved_mime = mime or upload_row.mime_type or "application/pdf"
        if resolved_mime == "image/jpg":
            resolved_mime = "image/jpeg"
        return PreparedUpload(
            upload_id=upload_row.id,
            stored_filename=upload_row.original_filename,
            mime=resolved_mime,
            storage_path=upload_row.storage_path,
            file_size=int(upload_row.file_size or 0),
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
            return self._prepared_from_row(upload_row, mime)

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
        if (
            mime == "application/pdf"
            and content
            and settings.openai_hybrid_text_enabled
        ):
            raw_text = extract_pdf_text(content)
            hints = parse_text_layer_hints(raw_text)

        category = self._classifier.classify(hints.raw_text or raw_text, filename=filename)
        supplemental: str | None = None
        if hints.has_usable_text:
            supplemental = raw_text[: settings.openai_max_supplemental_chars]

        logger.info(
            "Extraction context filename=%r category=%s text_chars=%d",
            filename,
            category.value,
            len(raw_text),
        )

        return _ExtractionContext(
            document_category=category,
            text_hints=hints,
            supplemental_text=supplemental,
            vision_system_prompt=build_vision_system_prompt(
                category,
                legacy_include_utility=False,
            ),
            batch_system_prompt=build_batch_system_prompt(
                category,
                legacy_include_utility=False,
            ),
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
            result = self._hybrid.merge(result, ctx.text_hints)

        if settings.openai_field_recovery_enabled:
            missing = self._ai_validation.validate_required_fields(result)
            if missing:
                logger.info(
                    "Field recovery triggered for %s (missing=%s)",
                    filename,
                    missing,
                )
                result = await self._field_recovery.recover_missing_fields(
                    result,
                    images=images,
                    model=model,
                    filename=filename,
                )
        return result

    @debug_trace
    async def _try_text_first_pdf(
        self,
        filename: str,
        *,
        total_pages: int,
        ctx: _ExtractionContext,
    ) -> tuple[ExtractionResult, str, str] | None:
        """Fast path for digital PDFs — regex hints or text-only LLM, no Vision."""
        if not self._text_first.can_attempt(
            total_pages=total_pages,
            hints=ctx.text_hints,
        ):
            return None

        hints_result = self._text_first.result_from_hints(ctx.text_hints)
        if hints_result is not None:
            logger.info(
                "Text-first hints path for %r (pages=%d, chars=%d)",
                filename,
                total_pages,
                len(ctx.text_hints.raw_text),
            )
            return hints_result, settings.openai_model, "text_hints"

        text_result = await self._text_first.extract_from_text(
            raw_text=ctx.text_hints.raw_text,
            filename=filename,
            system_prompt=ctx.vision_system_prompt,
            model=settings.openai_model,
            chat_completion=self._chat_completion,
            parse_response=self._parse_response,
        )
        if text_result is not None:
            logger.info(
                "Text-first LLM path for %r (pages=%d, chars=%d)",
                filename,
                total_pages,
                len(ctx.text_hints.raw_text),
            )
            return text_result, settings.openai_model, "text_llm"

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
            text_first = await self._try_text_first_pdf(
                filename,
                total_pages=total_pages,
                ctx=ctx,
            )
            if text_first is not None:
                result, model_used, mode = text_first
                meta = {
                    "pages_processed": total_pages,
                    "total_pdf_pages": total_pages,
                    "document_category": ctx.document_category.value,
                    "text_layer_chars": len(ctx.text_hints.raw_text),
                    "extraction_mode": mode,
                    "model": model_used,
                }
                return result, model_used, meta

            images = render_pdf_pages_as_images(
                content,
                max_pages=settings.openai_max_pdf_pages,
                scale=settings.openai_pdf_render_scale,
            )
            logger.debug(
                "Rendered PDF pages: count=%d (%s of (bytes, mime) tuples)",
                len(images), type(images).__name__,
            )
            if not images:
                raise ExtractionError("PDF has no readable pages")

            meta: dict = {
                "pages_processed": len(images),
                "total_pdf_pages": total_pages,
                "document_category": ctx.document_category.value,
                "text_layer_chars": len(ctx.text_hints.raw_text),
            }

            async def _run_pdf(model: str):
                r, m, mode = await self._extract_pdf_pages(
                    filename,
                    images,
                    total_pages=total_pages,
                    model=model,
                    ctx=ctx,
                )
                r = await self._apply_post_vision_pipeline(
                    r, ctx=ctx, images=images, filename=filename, model=m
                )
                return r, m, mode

            try:
                result, model_used, mode = await _run_pdf(settings.openai_model)
            except ExtractionError as exc:
                result, model_used, mode = await self._retry_strong_after_failure(
                    filename,
                    exc,
                    extract_fn=_run_pdf,
                )
            meta["extraction_mode"] = mode
            meta["model"] = model_used
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
        vision_mime = "image/jpeg" if mime == "image/jpg" else mime
        images = [(content, vision_mime)]

        async def _extract_image(model: str):
            r = await self._openai_vision_extract(
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
            result, model_used, mode = await _extract_image(settings.openai_model)
        except ExtractionError as exc:
            result, model_used, mode = await self._retry_strong_after_failure(
                filename,
                exc,
                extract_fn=_extract_image,
            )
        meta = {
            "pages_processed": 1,
            "extraction_mode": mode,
            "model": model_used,
            "document_category": ctx.document_category.value,
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
    async def _extract_pdf_pages(
        self,
        filename: str,
        images: list[tuple[bytes, str]],
        *,
        total_pages: int,
        model: str | None = None,
        ctx: _ExtractionContext | None = None,
    ) -> tuple[ExtractionResult, str, str]:
        model = model or settings.openai_model
        per_request = max(1, settings.openai_vision_pages_per_request)
        batch_size = max(1, settings.openai_vision_page_batch_size)
        vision_prompt = ctx.vision_system_prompt if ctx else VISION_SYSTEM_PROMPT
        batch_prompt = ctx.batch_system_prompt if ctx else build_batch_system_prompt()
        supplemental = ctx.supplemental_text if ctx else None
        category = ctx.document_category if ctx else None

        # Single request — all pages fit in one call
        if len(images) <= per_request:
            result = await self._openai_vision_extract(
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
        first_partial = await self._openai_vision_extract(
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

            async def _extract_batch(
                page_start: int,
                page_end: int,
                batch: list[tuple[bytes, str]],
            ) -> ExtractionResult:
                async with semaphore:
                    return await self._openai_vision_extract(
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
        payload = [p.model_dump() for p in partials]
        user_text = (
            f"Merge these {len(partials)} partial Vision extractions from a "
            f"{total_pages}-page invoice into one final JSON.\n\n"
            f"Partials (index = page batch order, 0 = first pages):\n"
            f"{json.dumps(payload, indent=2, default=str)}"
        )
        response = await self._chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": MERGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        )
        return self._parse_response(response.choices[0].message.content or "{}")

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
        if (
            not settings.openai_strong_retry_enabled
            or settings.openai_model_strong == settings.openai_model
        ):
            raise exc
        logger.info(
            "Retrying %s with %s after primary extraction failed: %s",
            filename,
            settings.openai_model_strong,
            exc,
        )
        return await extract_fn(settings.openai_model_strong)

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

        retry_reasons: list[str] = []
        for field in missing:
            retry_reasons.append(f"missing_{field}")
        if result.confidence_score < VISION_RETRY_CONFIDENCE:
            retry_reasons.append(
                f"low_confidence:{result.confidence_score:.2f}<{VISION_RETRY_CONFIDENCE}"
            )
        for issue in suspicious:
            retry_reasons.append(f"suspicious:{issue}")

        should_retry = (
            settings.openai_strong_retry_enabled
            and bool(retry_reasons)
            and settings.openai_model_strong != settings.openai_model
            and not str(meta.get("extraction_mode", "")).startswith("text_")
        )

        if should_retry:
            logger.info(
                "Strong-model retry for %s: model=%s reasons=%s",
                filename,
                settings.openai_model_strong,
                retry_reasons,
            )
            meta["strong_retry_reasons"] = retry_reasons
            retry_result, retry_model, retry_mode = await extract_fn(
                settings.openai_model_strong
            )
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
                return retry_result, retry_model, meta

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
        system_prompt: str = VISION_SYSTEM_PROMPT,
        context_hint: str | None = None,
        supplemental_text: str | None = None,
        document_category: DocumentCategory | None = None,
    ) -> ExtractionResult:
        if page_range:
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
            instruction_parts += [
                "",
                "Supplemental text extracted from PDF text layer (cross-check with images):",
                supplemental_text[: settings.openai_max_supplemental_chars],
            ]
        instruction_parts += [
            "",
            "Instructions:",
            "1. Study EVERY image completely — read every text block including headers, footers, and small print.",
            "2. Follow the visual scanning strategy from the system prompt (top→bottom, header→totals→payment).",
            "3. Apply all field rules exactly — especially the amount decision tree.",
            "4. Return a single JSON object. Nothing else.",
        ]
        fn_lower = filename.lower()
        if "kesco" in fn_lower:
            instruction_parts += [
                "",
                "KESCO bill detected:",
                "• invoice_number = exact value after Nr. Ref. / Nr. Ret. on the BOTTOM payment strip (below barcode), as printed.",
                "• NEVER use Shifra e konsumatorit, Customer ID, DPR codes, or other numeric-only header IDs.",
            ]
        elif any(
            token in fn_lower for token in ("pastrimi", "mbeturinave", "krm")
        ):
            instruction_parts += [
                "",
                "Pastrimi / KRM waste bill detected:",
                "• amount = Gjithsej borxhi / Total Due / Ukupan dug (includes prior debt).",
                "• NOT Vlera mujore e fatures / Monthly Invoice Total / Per pagese alone.",
                "• invoice_number = Nr.-No.-Br. in header; debt = Borgji paraprak / Previous due.",
                "• Capture all bank accounts from Xhirollogaria block.",
            ]
        elif any(
            token in fn_lower
            for token in ("ujesjel", "ujësjell", "ujesjell", "water", "ujesjelles")
        ):
            instruction_parts += [
                "",
                "Regional water bill — CRITICAL invoice_number:",
                "• Scan bottom 10–15%: full payment string above barcode (^F[0-9]+[A-Z]?$, usually 12+ digits after F).",
                "• Read twice character-by-character; if reads disagree → invoice_number null, needs_review true.",
                "• Optional trailing letter A–Z varies per bill — read from document. Never truncate to header Bill number.",
                "• FORBIDDEN: Customer ID, NUI/NIPT, meter #, amounts, dates, values not starting with F.",
            ]

        # Multi-page specific guidance injected directly into the user message
        # so the model receives it regardless of which system prompt is active.
        if total_pages > 1 and page_range:
            p_start, p_end = page_range
            is_full_document = (p_start == 1 and p_end == total_pages)
            instruction_parts += [
                "",
                f"MULTI-PAGE DOCUMENT — {total_pages} pages:",
            ]
            if is_full_document:
                instruction_parts += [
                    f"  • You are receiving ALL {total_pages} pages in order.",
                    "  • Page 1 = header (issuer name, address, invoice number, date, client block).",
                    f"  • Page {total_pages} = FINAL PAGE (grand total incl. VAT, Zahlbetrag/Amount due, IBAN, bank).",
                    "  • AMOUNT rule: extract `amount` ONLY from the grand-total / Bruttobetrag / Zahlbetrag line",
                    "    on the FINAL page. NEVER use individual line-item prices from earlier pages.",
                    "  • IBAN rule: read ALL IBANs from the final page footer; list every one.",
                ]
            else:
                instruction_parts += [
                    f"  • You are processing pages {p_start}–{p_end} of {total_pages}.",
                    f"  • {'This is the FIRST page — capture header fields.' if p_start == 1 else ''}",
                    f"  • {'This is the FINAL page — capture totals and IBAN.' if p_end == total_pages else 'Line-items page — set amount to null (totals come later).'}",
                ]

        user_content: list[dict] = [
            {"type": "text", "text": "\n".join(instruction_parts)},
        ]

        for index, (img_bytes, mime) in enumerate(images, start=1):
            page_num = (page_range[0] + index - 1) if page_range else index
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
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime};base64,{b64}",
                        "detail": "high",
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
