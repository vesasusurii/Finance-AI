from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from models.invoice import Invoice
from models.uploaded_file import UploadedFile
from models.user import User


class UploadRepository:
    DOCUMENT_KINDS = ("invoice", "document")

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        file_kind: str,
        filename: str,
        storage_path: str,
        mime_type: str | None,
        user_id: int,
        processing_status: str = "pending",
        file_size: int | None = None,
        content_sha256: str | None = None,
    ) -> UploadedFile:
        row = UploadedFile(
            original_filename=filename,
            storage_path=storage_path,
            mime_type=mime_type,
            file_kind=file_kind,
            uploaded_by=user_id,
            processing_status=processing_status,
            file_size=file_size,
            content_sha256=content_sha256,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def get(self, upload_id: int) -> UploadedFile | None:
        return await self._session.get(UploadedFile, upload_id)

    async def update_status(self, upload_id: int, status: str) -> None:
        row = await self.get(upload_id)
        if row:
            row.processing_status = status
            await self._session.flush()

    async def delete(self, upload_id: int) -> None:
        row = await self.get(upload_id)
        if row:
            await self._session.delete(row)
            await self._session.flush()

    async def find_invoice_upload_by_hash(
        self, content_sha256: str
    ) -> tuple[UploadedFile | None, Invoice | None, User | None]:
        """Return the canonical invoice upload for this file hash, if any."""
        owner_id = case(
            (Invoice.id.isnot(None), Invoice.uploaded_by),
            else_=UploadedFile.uploaded_by,
        )
        q = (
            select(UploadedFile, Invoice, User)
            .outerjoin(Invoice, Invoice.source_file_id == UploadedFile.id)
            .join(User, User.id == owner_id)
            .where(
                UploadedFile.file_kind == "invoice",
                UploadedFile.content_sha256 == content_sha256,
            )
            .limit(1)
        )
        result = await self._session.execute(q)
        row = result.one_or_none()
        if row is None:
            return None, None, None
        upload, invoice, user = row
        return upload, invoice, user
