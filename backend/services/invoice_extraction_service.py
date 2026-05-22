import base64
import io
import json
import mimetypes

import pdfplumber
from fastapi import UploadFile
from openai import AsyncOpenAI

from config import settings
from core.exceptions import ExtractionError
from repositories.audit_repository import AuditRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.upload_repository import UploadRepository
from schemas.auth import UserContext
from schemas.invoice import ExtractionResult, UploadItemResponse
from services.ai_validation_service import AIValidationService
from utils.file_storage import save_upload

ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}
MAX_FILE_BYTES = 20 * 1024 * 1024

SYSTEM_PROMPT = """You extract purchase invoice data for Borek Finance.
Return ONLY valid JSON with these keys (use null when unknown):
invoice_date (YYYY-MM-DD), name_of_company, address_of_company, invoice_number,
amount (number, total due), currency (ISO code), account_details, internal_note_description,
client_employee_related, category, confidence_score (0.0-1.0), needs_review (boolean).
Never guess invoice_number when uncertain — set needs_review true and lower confidence_score.
Do not use tax IDs (NUI/UNI/VAT) as invoice_number."""


class InvoiceExtractionService:
    def __init__(
        self,
        upload_repo: UploadRepository,
        invoice_repo: InvoiceRepository,
        audit_repo: AuditRepository,
        ai_validation: AIValidationService,
        openai_client: AsyncOpenAI,
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
            raise ExtractionError("File exceeds size limit")

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
            result = await self._extract(file.filename, mime, content)
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
                result.model_dump(),
            )
            await self._upload_repo.update_status(upload_row.id, "processed")
            return UploadItemResponse(
                upload_id=upload_row.id,
                original_filename=file.filename,
                processing_status="processed",
                invoice_id=invoice.id,
            )
        except Exception as exc:
            await self._upload_repo.update_status(upload_row.id, "failed")
            raise ExtractionError(str(exc)) from exc

    async def _extract(
        self, filename: str, mime: str, content: bytes
    ) -> ExtractionResult:
        if not settings.openai_api_key:
            raise ExtractionError("OPENAI_API_KEY is not configured")

        if mime == "application/pdf":
            text = self._pdf_text(content)
            if len(text.strip()) >= 50:
                return await self._extract_from_text(text)
            raise ExtractionError(
                "Could not extract text from PDF; upload a clearer scan or image file"
            )

        return await self._extract_from_image(content, mime, filename)

    def _pdf_text(self, content: bytes) -> str:
        parts: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages[:10]:
                parts.append(page.extract_text() or "")
        return "\n".join(parts)

    async def _extract_from_text(self, text: str) -> ExtractionResult:
        response = await self._openai.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Extract invoice fields from this document text:\n\n{text[:12000]}",
                },
            ],
        )
        return self._parse_response(response.choices[0].message.content or "{}")

    async def _extract_from_image(
        self, content: bytes, mime: str, filename: str
    ) -> ExtractionResult:
        b64 = base64.standard_b64encode(content).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"
        response = await self._openai.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Extract invoice fields from file: {filename}",
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        )
        return self._parse_response(response.choices[0].message.content or "{}")

    def _parse_response(self, raw: str) -> ExtractionResult:
        try:
            data = json.loads(raw)
            return ExtractionResult.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ExtractionError(f"Invalid AI response: {exc}") from exc
