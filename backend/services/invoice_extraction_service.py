"""
Invoice extraction — OpenAI Vision is the primary OCR path (DOCS/8).

Digital PDFs with a usable text layer are extracted via text-first (more accurate
for amounts and references). Scanned PDFs and images use Vision. Multi-page PDFs
are batched when needed, then merged with supplemental text on every batch.
"""

import base64
import json
import logging
import mimetypes

from fastapi import UploadFile
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from config import settings
from core.exceptions import ExtractionError
from repositories.audit_repository import AuditRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.upload_repository import UploadRepository
from schemas.auth import UserContext
from schemas.invoice import ExtractionResult, UploadItemResponse
from services.ai_validation_service import AIValidationService
from services.extraction_prompts import (
    BATCH_SYSTEM_PROMPT,
    MERGE_SYSTEM_PROMPT,
    TEXT_SYSTEM_PROMPT,
    VISION_SYSTEM_PROMPT,
)
from services.ocr.pdf_reader import (
    extract_pdf_text,
    pdf_is_encrypted,
    pdf_page_count,
    pdf_text_usable,
    render_pdf_pages_as_images,
    slice_pdf_text_by_pages,
)
from utils.file_storage import save_upload

logger = logging.getLogger(__name__)

EXTRACTION_PROVIDER = "openai_vision"

ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}
MAX_FILE_BYTES = 20 * 1024 * 1024
VISION_RETRY_CONFIDENCE = 0.85
TEXT_FIRST_MIN_CONFIDENCE = 0.80


class InvoiceExtractionService:
    def __init__(
        self,
        upload_repo: UploadRepository,
        invoice_repo: InvoiceRepository,
        audit_repo: AuditRepository,
        ai_validation: AIValidationService,
        openai_client: AsyncOpenAI | None,
    ) -> None:
        self._upload_repo = upload_repo
        self._invoice_repo = invoice_repo
        self._audit_repo = audit_repo
        self._ai_validation = ai_validation
        self._openai = openai_client

    async def process_upload(
        self, file: UploadFile, user: UserContext
    ) -> UploadItemResponse:
        if not file.filename:
            raise ExtractionError("Missing filename")

        content = await file.read()
        if len(content) > MAX_FILE_BYTES:
            raise ExtractionError("File exceeds 20 MB limit")

        mime = file.content_type or mimetypes.guess_type(file.filename)[0] or ""
        if mime not in ALLOWED_MIME:
            raise ExtractionError(f"Unsupported file type: {mime}")

        await file.seek(0)
        storage_path = await save_upload(file, "invoices")
        upload_row = await self._upload_repo.create(
            file_kind="invoice",
            filename=file.filename,
            storage_path=storage_path,
            mime_type=mime,
            user_id=user.user_id,
            processing_status="processing",
        )

        try:
            result, model_used, meta = await self._extract(
                file.filename, mime, content
            )
            result = self._ai_validation.sanitize_and_validate(result)
            missing = self._ai_validation.validate_required_fields(result)
            if missing:
                result.needs_review = True
                result.confidence_score = min(result.confidence_score, 0.69)

            review_status = self._ai_validation.determine_review_status(result)
            invoice = await self._invoice_repo.create(
                result, upload_row.id, review_status
            )
            await self._audit_repo.log(
                user.user_id,
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
                original_filename=file.filename,
                processing_status="processed",
                invoice_id=invoice.id,
            )
        except Exception as exc:
            logger.exception("Extraction failed for %s", file.filename)
            await self._upload_repo.update_status(upload_row.id, "failed")
            raise ExtractionError(str(exc)) from exc

    async def _extract(
        self, filename: str, mime: str, content: bytes
    ) -> tuple[ExtractionResult, str, dict]:
        if self._openai is None or not settings.openai_api_key:
            raise ExtractionError("OPENAI_API_KEY is not configured")

        meta: dict = {"pages_processed": 1, "extraction_mode": "vision_single"}

        if mime == "application/pdf":
            if pdf_is_encrypted(content):
                raise ExtractionError("Password-protected PDF cannot be processed")

            total_pages = pdf_page_count(content)
            if total_pages > settings.openai_max_pdf_pages:
                raise ExtractionError(
                    f"PDF has {total_pages} pages; maximum is "
                    f"{settings.openai_max_pdf_pages}"
                )

            raw_text = extract_pdf_text(content, max_pages=settings.openai_max_pdf_pages)
            supplemental_full = (
                raw_text[: settings.openai_max_supplemental_chars]
                if pdf_text_usable(raw_text)
                else None
            )

            if supplemental_full:
                text_result, text_model = await self._try_text_first_extract(
                    filename, supplemental_full, total_pages
                )
                if text_result is not None:
                    meta = {
                        "pages_processed": total_pages,
                        "total_pdf_pages": total_pages,
                        "extraction_mode": "text_layer",
                        "model": text_model,
                    }
                    return await self._maybe_retry_strong(
                        filename,
                        text_result,
                        text_model,
                        meta,
                        extract_fn=lambda m: self._extract_from_text(
                            filename, supplemental_full, total_pages, model=m
                        ),
                    )

            images = render_pdf_pages_as_images(
                content,
                max_pages=settings.openai_max_pdf_pages,
                scale=settings.openai_pdf_render_scale,
            )
            if not images:
                raise ExtractionError("PDF has no readable pages")

            meta = {
                "pages_processed": len(images),
                "total_pdf_pages": total_pages,
            }

            result, model_used, mode = await self._extract_pdf_pages(
                filename,
                images,
                supplemental_text=supplemental_full,
                total_pages=total_pages,
            )
            meta["extraction_mode"] = mode
            meta["model"] = model_used
            return await self._maybe_retry_strong(
                filename,
                result,
                model_used,
                meta,
                extract_fn=lambda m: self._extract_pdf_pages(
                    filename,
                    images,
                    supplemental_text=supplemental_full,
                    total_pages=total_pages,
                    model=m,
                ),
            )

        images = [(content, mime)]

        async def extract_image(model: str):
            r = await self._openai_vision_extract(
                images,
                f"Image invoice: {filename}",
                supplemental_text=None,
                model=model,
                page_range=None,
                total_pages=1,
            )
            return r, model, "vision_single"

        result, model_used, mode = await extract_image(settings.openai_model)
        meta["extraction_mode"] = mode
        return await self._maybe_retry_strong(
            filename, result, model_used, meta, extract_fn=extract_image
        )

    async def _try_text_first_extract(
        self,
        filename: str,
        full_text: str,
        total_pages: int,
    ) -> tuple[ExtractionResult | None, str]:
        """Text-layer path for digital PDFs; returns None if quality is insufficient."""
        try:
            result, model = await self._extract_from_text(
                filename, full_text, total_pages, model=settings.openai_model
            )
            result = self._ai_validation.sanitize_and_validate(result)
            missing = self._ai_validation.validate_required_fields(result)
            if (
                not missing
                and result.confidence_score >= TEXT_FIRST_MIN_CONFIDENCE
                and not result.needs_review
            ):
                return result, model
            logger.info(
                "Text-first extract insufficient for %s (missing=%s, confidence=%.2f)",
                filename,
                missing,
                result.confidence_score,
            )
        except Exception:
            logger.info("Text-first extract failed for %s, using Vision", filename)
        return None, settings.openai_model

    async def _extract_from_text(
        self,
        filename: str,
        full_text: str,
        total_pages: int,
        *,
        model: str | None = None,
    ) -> tuple[ExtractionResult, str]:
        model = model or settings.openai_model
        user_text = (
            f"Digital PDF invoice: {filename}\n"
            f"Pages: {total_pages}\n\n"
            "Full document text (all pages):\n\n"
            f"{full_text}"
        )
        response = await self._chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": TEXT_SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        )
        return self._parse_response(response.choices[0].message.content or "{}"), model

    async def _extract_pdf_pages(
        self,
        filename: str,
        images: list[tuple[bytes, str]],
        *,
        supplemental_text: str | None,
        total_pages: int,
        model: str | None = None,
    ) -> tuple[ExtractionResult, str, str]:
        model = model or settings.openai_model
        label = f"PDF invoice: {filename}"
        per_request = max(1, settings.openai_vision_pages_per_request)
        batch_size = max(1, settings.openai_vision_page_batch_size)

        if len(images) <= per_request:
            result = await self._openai_vision_extract(
                images,
                label,
                supplemental_text=supplemental_text,
                model=model,
                page_range=(1, len(images)),
                total_pages=total_pages,
                system_prompt=VISION_SYSTEM_PROMPT,
            )
            return result, model, "vision_full_document"

        partials: list[ExtractionResult] = []
        for start in range(0, len(images), batch_size):
            batch = images[start : start + batch_size]
            page_start = start + 1
            page_end = start + len(batch)
            batch_supplemental = None
            if supplemental_text:
                batch_supplemental = slice_pdf_text_by_pages(
                    supplemental_text, page_start, page_end
                )
                if not batch_supplemental.strip():
                    batch_supplemental = None

            partial = await self._openai_vision_extract(
                batch,
                label,
                supplemental_text=batch_supplemental,
                model=model,
                page_range=(page_start, page_end),
                total_pages=total_pages,
                system_prompt=BATCH_SYSTEM_PROMPT,
            )
            partials.append(partial)

        merged = await self._merge_partial_extractions(
            partials,
            supplemental_text=supplemental_text,
            total_pages=total_pages,
            model=model,
        )
        return merged, model, "vision_batched_merge"

    async def _merge_partial_extractions(
        self,
        partials: list[ExtractionResult],
        *,
        supplemental_text: str | None,
        total_pages: int,
        model: str,
    ) -> ExtractionResult:
        payload = [p.model_dump() for p in partials]
        user_text = (
            f"Merge {len(partials)} partial extractions from a {total_pages}-page "
            f"invoice into one JSON.\n\nPartials:\n{json.dumps(payload, indent=2)}"
        )
        if supplemental_text:
            user_text += (
                "\n\nFull PDF text layer (authoritative for amounts and references):\n\n"
                f"{supplemental_text[: settings.openai_max_supplemental_chars]}"
            )

        response = await self._chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": MERGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        )
        return self._parse_response(response.choices[0].message.content or "{}")

    async def _maybe_retry_strong(
        self,
        filename: str,
        result: ExtractionResult,
        model_used: str,
        meta: dict,
        *,
        extract_fn,
    ) -> tuple[ExtractionResult, str, dict]:
        result = self._ai_validation.sanitize_and_validate(result)
        missing = self._ai_validation.validate_required_fields(result)
        should_retry = (
            missing
            or result.confidence_score < VISION_RETRY_CONFIDENCE
        ) and settings.openai_model_strong != settings.openai_model

        if should_retry:
            logger.info(
                "Retrying %s with %s (confidence=%.2f, missing=%s)",
                filename,
                settings.openai_model_strong,
                result.confidence_score,
                missing,
            )
            retry_result, retry_model, retry_mode = await extract_fn(
                settings.openai_model_strong
            )
            retry_result = self._ai_validation.sanitize_and_validate(retry_result)
            retry_missing = self._ai_validation.validate_required_fields(retry_result)
            retry_score = retry_result.confidence_score
            original_score = result.confidence_score
            if (
                retry_score > original_score
                or (retry_missing and not missing)
                or (not retry_missing and missing)
            ):
                meta["extraction_mode"] = retry_mode
                meta["model"] = retry_model
                return retry_result, retry_model, meta
        meta["model"] = model_used
        return result, model_used, meta

    async def _openai_vision_extract(
        self,
        images: list[tuple[bytes, str]],
        label: str,
        *,
        supplemental_text: str | None,
        model: str,
        page_range: tuple[int, int] | None,
        total_pages: int,
        system_prompt: str = VISION_SYSTEM_PROMPT,
    ) -> ExtractionResult:
        if page_range:
            start, end = page_range
            scope = (
                f"Pages {start}–{end} of {total_pages}."
                if total_pages > 1
                else f"Page {start}."
            )
        else:
            scope = f"All {len(images)} page(s)."

        user_content: list[dict] = [
            {
                "type": "text",
                "text": (
                    f"{label}\n"
                    "Study every page image in order before extracting. "
                    f"{scope}\n"
                    "Return one JSON object only."
                ),
            },
        ]
        if supplemental_text:
            user_content.append(
                {
                    "type": "text",
                    "text": (
                        "PDF text for these pages (use for exact numbers and refs; "
                        "prefer images for layout and totals):\n\n"
                        f"{supplemental_text}"
                    ),
                }
            )

        for index, (img_bytes, mime) in enumerate(images, start=1):
            page_num = (page_range[0] + index - 1) if page_range else index
            if len(images) > 1 or total_pages > 1:
                user_content.append(
                    {"type": "text", "text": f"--- Page {page_num} of {total_pages} ---"}
                )
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

    def _vision_timeout(self, page_count: int) -> float:
        base = float(settings.openai_timeout_seconds)
        return min(300.0, base + page_count * 15.0)

    async def _chat_completion(
        self, *, model: str, messages: list, timeout_seconds: float | None = None
    ):
        timeout = timeout_seconds or float(settings.openai_timeout_seconds)
        last_exc: Exception | None = None
        attempts = max(1, settings.openai_max_retries)
        for attempt in range(attempts):
            try:
                return await self._openai.chat.completions.create(
                    model=model,
                    temperature=0,
                    response_format={"type": "json_object"},
                    timeout=timeout,
                    messages=messages,
                )
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

    def _parse_response(self, raw: str) -> ExtractionResult:
        try:
            data = json.loads(raw)
            if data.get("amount") is not None:
                normalized = self._ai_validation._normalize_amount(data["amount"])
                data["amount"] = normalized
            if data.get("confidence_score") is not None:
                data["confidence_score"] = float(data["confidence_score"])
            result = ExtractionResult.model_validate(data)
            return self._ai_validation.sanitize_and_validate(result)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ExtractionError(f"Invalid OpenAI response: {exc}") from exc
