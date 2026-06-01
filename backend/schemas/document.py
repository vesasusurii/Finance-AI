from pydantic import BaseModel


class DocumentUploadItemResponse(BaseModel):
    document_id: int
    filename: str
    upload_status: str
    mime_type: str | None = None
    file_size: int | None = None
    invoice_id: int | None = None
    error: str | None = None
    message: str | None = None
    original_uploader_email: str | None = None


class DocumentUploadResponse(BaseModel):
    uploaded: int
    items: list[DocumentUploadItemResponse]


class DocumentStatusResponse(BaseModel):
    document_id: int
    filename: str
    upload_status: str
    mime_type: str | None = None
    file_size: int | None = None
    invoice_id: int | None = None
    error: str | None = None
