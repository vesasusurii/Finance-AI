"""
Invoice extraction — OpenAI Vision only (DOCS/8).

All invoice files (PDF, JPEG, JPG, PNG) are rasterised when needed and sent to
OpenAI Vision. No pdfplumber, Document AI, Tesseract, or other OCR providers.
"""

import base64
import json
import mimetypes

from fastapi import UploadFile
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from config import settings
from core.debug_logger import debug_trace, get_logger, log_typed_fields
from core.exceptions import ExtractionError
from repositories.audit_repository import AuditRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.upload_repository import UploadRepository
from schemas.auth import UserContext
from schemas.invoice import ExtractionResult, UploadItemResponse
from services.ai_validation_service import AIValidationService
from ai.prompts import (
    BATCH_SYSTEM_PROMPT,
    MERGE_SYSTEM_PROMPT,
    VISION_SYSTEM_PROMPT,
)
from services.ocr.pdf_reader import (
    pdf_is_encrypted,
    pdf_page_count,
    render_pdf_pages_as_images,
)
from utils.file_storage import save_upload

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

# Max tokens for extraction response — enough for full JSON, prevents truncation
_MAX_TOKENS = 2400  # Raised from 1800 — multi-page docs with multiple IBANs need headroom


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

    # ─────────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────────

    @debug_trace
    async def process_upload(
        self, file: UploadFile, user: UserContext
    ) -> UploadItemResponse:
        logger.debug(
            "OCR upload start: filename=%r content_type=%r user_id=%r",
            file.filename, file.content_type, user.user_id,
        )
        if not file.filename:
            raise ExtractionError("Missing filename")

        content = await file.read()
        logger.debug(
            "Read upload bytes: size=%d (%s)", len(content), type(content).__name__
        )
        if len(content) > MAX_FILE_BYTES:
            raise ExtractionError("File exceeds 20 MB limit")

        mime = file.content_type or mimetypes.guess_type(file.filename)[0] or ""
        logger.debug("Resolved mime: %r (%s)", mime, type(mime).__name__)
        if mime not in ALLOWED_MIME:
            raise ExtractionError(
                f"Unsupported file type: {mime}. Supported: PDF, JPEG, JPG, PNG."
            )

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
        logger.debug(
            "Upload row created: id=%d storage_path=%r", upload_row.id, storage_path
        )

        try:
            result, model_used, meta = await self._extract(
                file.filename, mime, content
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
                result, upload_row.id, review_status
            )
            logger.debug(
                "Invoice persisted: id=%d (%s)", invoice.id, type(invoice).__name__
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

    # ─────────────────────────────────────────────────────────────────────
    # Extraction routing
    # ─────────────────────────────────────────────────────────────────────

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
            }
            result, model_used, mode = await self._extract_pdf_pages(
                filename, images, total_pages=total_pages
            )
            meta["extraction_mode"] = mode
            meta["model"] = model_used
            return await self._maybe_retry_strong(
                filename,
                result,
                model_used,
                meta,
                extract_fn=lambda m: self._extract_pdf_pages(
                    filename, images, total_pages=total_pages, model=m
                ),
            )

        # Direct image upload
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
            )
            return r, model, "vision_single"

        result, model_used, mode = await _extract_image(settings.openai_model)
        meta = {"pages_processed": 1, "extraction_mode": mode, "model": model_used}
        return await self._maybe_retry_strong(
            filename, result, model_used, meta, extract_fn=_extract_image
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
    ) -> tuple[ExtractionResult, str, str]:
        model = model or settings.openai_model
        per_request = max(1, settings.openai_vision_pages_per_request)
        batch_size = max(1, settings.openai_vision_page_batch_size)

        # Single request — all pages fit in one call
        if len(images) <= per_request:
            result = await self._openai_vision_extract(
                images,
                filename=filename,
                file_type="pdf",
                model=model,
                page_range=(1, len(images)),
                total_pages=total_pages,
                system_prompt=VISION_SYSTEM_PROMPT,
            )
            return result, model, "vision_full_document"

        # Batched extraction with context carry-forward
        partials: list[ExtractionResult] = []
        header_context: str | None = None  # carry issuer + invoice # from batch 1

        for start in range(0, len(images), batch_size):
            batch = images[start : start + batch_size]
            page_start = start + 1
            page_end = start + len(batch)

            partial = await self._openai_vision_extract(
                batch,
                filename=filename,
                file_type="pdf",
                model=model,
                page_range=(page_start, page_end),
                total_pages=total_pages,
                system_prompt=BATCH_SYSTEM_PROMPT,
                context_hint=header_context,
            )
            partials.append(partial)

            # After first batch: build context hint so later batches know the issuer
            if start == 0 and (partial.name_of_company or partial.invoice_number):
                parts = []
                if partial.name_of_company:
                    parts.append(f"Issuer: {partial.name_of_company}")
                if partial.invoice_number:
                    parts.append(f"Invoice #: {partial.invoice_number}")
                if partial.invoice_date:
                    parts.append(f"Date: {partial.invoice_date}")
                header_context = " | ".join(parts) if parts else None

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
        suspicious = self._ai_validation.detect_suspicious_values(result)
        logger.debug(
            "Retry check: confidence=%.3f (float) missing=%s (%s) suspicious=%s (%s)",
            result.confidence_score,
            missing, type(missing).__name__,
            suspicious, type(suspicious).__name__,
        )

        should_retry = (
            (missing or result.confidence_score < VISION_RETRY_CONFIDENCE or suspicious)
            and settings.openai_model_strong != settings.openai_model
        )

        if should_retry:
            logger.info(
                "Retrying %s with %s (confidence=%.2f, missing=%s, suspicious=%s)",
                filename,
                settings.openai_model_strong,
                result.confidence_score,
                missing,
                suspicious,
            )
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
                "• invoice_number = alphanumeric value after Nr. Ref. / Nr. Ret. on the BOTTOM payment strip (below barcode).",
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
                    max_tokens=_MAX_TOKENS,
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
