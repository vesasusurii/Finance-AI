"""Application settings — single source for env vars (doc 12)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(validation_alias="DATABASE_URL")
    jwt_secret: str = Field(validation_alias="JWT_SECRET")
    storage_path: str = Field(validation_alias="STORAGE_PATH")
    cors_origins: str = Field(validation_alias="CORS_ORIGINS")

    environment: str = Field(default="local", validation_alias="ENVIRONMENT")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    # Primary OCR: OpenAI Vision (gpt-4o-mini). Strong model used on low-confidence retry.
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    openai_model_strong: str = Field(
        default="gpt-4o", validation_alias="OPENAI_MODEL_STRONG"
    )
    openai_timeout_seconds: int = Field(
        default=120, validation_alias="OPENAI_TIMEOUT_SECONDS"
    )
    openai_max_retries: int = Field(default=2, validation_alias="OPENAI_MAX_RETRIES")
    openai_max_pdf_pages: int = Field(
        default=25, validation_alias="OPENAI_MAX_PDF_PAGES"
    )
    openai_vision_pages_per_request: int = Field(
        default=6, validation_alias="OPENAI_VISION_PAGES_PER_REQUEST"
    )
    openai_vision_page_batch_size: int = Field(
        default=5, validation_alias="OPENAI_VISION_PAGE_BATCH_SIZE"
    )
    openai_max_supplemental_chars: int = Field(
        default=80000, validation_alias="OPENAI_MAX_SUPPLEMENTAL_CHARS"
    )
    openai_pdf_render_scale: float = Field(
        default=2.5, validation_alias="OPENAI_PDF_RENDER_SCALE"
    )
    jwt_expire_minutes: int = Field(default=480, validation_alias="JWT_EXPIRE_MINUTES")
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    cookie_samesite: str = Field(default="lax", validation_alias="COOKIE_SAMESITE")
    log_level: str = Field(default="info", validation_alias="LOG_LEVEL")


settings = Settings()
