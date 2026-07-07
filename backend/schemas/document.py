from pydantic import BaseModel, Field, model_validator


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
    download_ms: float | None = None
    text_extraction_ms: float | None = None
    document_classification_ms: float | None = None
    text_llm_ms: float | None = None
    ocr_ms: float | None = None
    render_ms: float | None = None
    rendered_image_bytes: int | None = None
    merge_ms: float | None = None
    hybrid_merge_ms: float | None = None
    field_recovery_ms: float | None = None
    validation_ms: float | None = None
    persist_ms: float | None = None
    total_ms: float | None = None
    openai_total_ms: float | None = None
    openai_call_count: int | None = None
    merge_strategy: str | None = None
    prompt_strategy: str | None = None
    image_detail_strategy: str | None = None
    render_strategy: str | None = None
    render_parallel_ms: float | None = None
    rendered_page_count: int | None = None
    estimated_prompt_tokens: int | None = None
    supplemental_text_chars: int | None = None

    @model_validator(mode="after")
    def _sync_download_alias(self) -> "DocumentStatusResponse":
        if self.download_ms is None and self.storage_download_ms is not None:
            self.download_ms = self.storage_download_ms
        elif self.storage_download_ms is None and self.download_ms is not None:
            self.storage_download_ms = self.download_ms
        return self


class DocumentStatusBatchRequest(BaseModel):
    document_ids: list[int] = Field(..., min_length=1, max_length=50)


class DocumentStatusBatchResponse(BaseModel):
    items: list[DocumentStatusResponse]
