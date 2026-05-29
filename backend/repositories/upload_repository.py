from sqlalchemy.ext.asyncio import AsyncSession

from models.uploaded_file import UploadedFile


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
    ) -> UploadedFile:
        row = UploadedFile(
            original_filename=filename,
            storage_path=storage_path,
            mime_type=mime_type,
            file_kind=file_kind,
            uploaded_by=user_id,
            processing_status=processing_status,
            file_size=file_size,
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
