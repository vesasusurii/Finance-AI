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
    stage: str | None = None
    stage_label: str | None = None
    model: str | None = None
    extraction_mode: str | None = None
    pages_processed: int | None = None
    total_pdf_pages: int | None = None
    queue_wait_ms: float | None = None
    storage_download_ms: float | None = None
    text_extraction_ms: float | None = None
    text_llm_ms: float | None = None
    ocr_ms: float | None = None
    render_ms: float | None = None
    rendered_image_bytes: int | None = None
    merge_ms: float | None = None
    persist_ms: float | None = None
    total_ms: float | None = None
    openai_total_ms: float | None = None
    openai_call_count: int | None = None
