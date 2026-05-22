"""
Invoice extraction — OpenAI Vision is the primary OCR path (DOCS/8).

All PDF pages are rendered and processed (batched when needed). pdfplumber text
is supplemental context. Google Document AI / Tesseract are not implemented.
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
from services.ocr.pdf_reader import (
    extract_pdf_text,
    pdf_is_encrypted,
    pdf_page_count,
    pdf_text_usable,
    render_pdf_pages_as_images,
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

SYSTEM_PROMPT = """You are an invoice OCR and data extractor for Borek Finance.
You read complete invoice documents (all pages provided) in many formats: standard
tax invoices, proforma invoices, utility bills, SaaS receipts, hospitality bills,
credit notes, bilingual Albanian/English/Serbian layouts, and scanned multi-page PDFs.

The bill-to / Klienti / Customer block is the customer — never use customer tax IDs
(NUI, UNI, NRF, VAT, EIN) as invoice_number.

Return a single JSON object with these keys only:
invoice_date, name_of_company, address_of_company, invoice_number, amount, currency,
account_details, internal_note_description, client_employee_related, category,
confidence_score, needs_review.

Rules:
- Read every page: header and issuer on early pages; line items may span pages;
  totals, VAT, and payment due often appear on the last page.
- name_of_company = issuer in letterhead/header, not bill-to / Klienti / Customer.
- invoice_number: Invoice Ref, Fatura Nr., Invoice No., Bill number, Document number —
  not tax registration IDs. Accept 10210, 1/2026/0048, 3807F638-0011, 132018959018.
- amount: Total Amount Due, Për pagesë / For payment / Za naplatu, Amount due,
  Total invoice, Grand total — NOT utility "Total Due" that includes prior balance
  when a separate "Për pagesë" / For payment line exists.
- currency: ISO code as printed (EUR, USD, GBP, CHF, ALL, etc.).
- Dates: convert to YYYY-MM-DD (DD.MM.YYYY, DD/MM/YYYY, DD-MMM-YY, long month names).
- account_details: IBAN, bank name, SWIFT; concatenate briefly if multiple.
- internal_note_description: brief summary of line items or services when visible.
- category: Professional services, Utilities, Software, IT / Hardware, Office, Travel, Other.
- Do not guess invoice_number or amount; set needs_review true when uncertain.
- confidence_score: 0.0–1.0; needs_review: true if critical fields missing or unclear.
- Never include paid_at_date or paid_by."""

BATCH_SYSTEM_PROMPT = SYSTEM_PROMPT + """

You are viewing a page range of a longer invoice. Extract any fields visible on these
pages. Leave fields null if not on these pages. Put line-item detail in
internal_note_description. Do not invent totals from partial pages."""

MERGE_SYSTEM_PROMPT = """You merge partial JSON extractions from a multi-page invoice into one
final extraction. Use the same field keys as a single invoice extract.

Prefer: issuer and invoice_number from header pages; amount and currency from pages
showing totals, VAT, or "Për pagesë" / Amount due; combine internal_note_description
from all parts. Resolve conflicts by trusting pages that show the payment summary.
Apply the same rules as invoice extraction (no customer tax ID as invoice_number).
Return one JSON object only."""


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

            images = render_pdf_pages_as_images(
                content,
                max_pages=settings.openai_max_pdf_pages,
                scale=settings.openai_pdf_render_scale,
            )
            if not images:
                raise ExtractionError("PDF has no readable pages")

            raw_text = extract_pdf_text(content, max_pages=settings.openai_max_pdf_pages)
            supplemental = (
                raw_text[: settings.openai_max_supplemental_chars]
                if pdf_text_usable(raw_text)
                else None
            )

            meta = {
                "pages_processed": len(images),
                "total_pdf_pages": total_pages,
            }

            result, model_used, mode = await self._extract_pdf_pages(
                filename,
                images,
                supplemental_text=supplemental,
                total_pages=total_pages,
            )
            meta["extraction_mode"] = mode
            meta["model"] = model_used
            return await self._maybe_retry_strong(
                filename, result, model_used, meta,
                extract_fn=lambda m: self._extract_pdf_pages(
                    filename, images, supplemental_text=supplemental,
                    total_pages=total_pages, model=m,
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
                system_prompt=SYSTEM_PROMPT,
            )
            return result, model, "vision_full_document"

        partials: list[ExtractionResult] = []
        for start in range(0, len(images), batch_size):
            batch = images[start : start + batch_size]
            page_start = start + 1
            page_end = start + len(batch)
            partial = await self._openai_vision_extract(
                batch,
                label,
                supplemental_text=None,
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
                "\n\nFull PDF text layer (use for exact amounts and references):\n\n"
                f"{supplemental_text}"
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
        missing = self._ai_validation.validate_required_fields(result)
        if (
            missing
            or result.confidence_score < VISION_RETRY_CONFIDENCE
            or result.needs_review
        ) and settings.openai_model_strong != settings.openai_model:
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
            if retry_result.confidence_score >= result.confidence_score:
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
        system_prompt: str = SYSTEM_PROMPT,
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
                    "Read every page in this request completely before extracting. "
                    f"{scope}"
                ),
            },
        ]
        if supplemental_text and page_range and page_range[0] == 1:
            user_content.append(
                {
                    "type": "text",
                    "text": (
                        "Full PDF text layer (all pages; use for exact numbers; "
                        "prefer visual layout for totals and tables):\n\n"
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
                data["amount"] = float(data["amount"])
            if data.get("confidence_score") is not None:
                data["confidence_score"] = float(data["confidence_score"])
            return ExtractionResult.model_validate(data)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            raise ExtractionError(f"Invalid OpenAI response: {exc}") from exc
