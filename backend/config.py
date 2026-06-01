"""Application settings — single source for env vars (doc 12)."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent
# Docker runs with cwd /app (backend/); local dev may use repo root .env
_ENV_FILES = [
    p for p in (_BACKEND_DIR / ".env", _REPO_ROOT / ".env") if p.is_file()
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES or ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(validation_alias="DATABASE_URL")
    jwt_secret: str = Field(validation_alias="JWT_SECRET")
    storage_path: str = Field(validation_alias="STORAGE_PATH")
    storage_backend: str = Field(default="local", validation_alias="STORAGE_BACKEND")
    supabase_url: str = Field(default="", validation_alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(
        default="", validation_alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_storage_bucket: str = Field(
        default="invoices", validation_alias="SUPABASE_STORAGE_BUCKET"
    )
    cors_origins: str = Field(validation_alias="CORS_ORIGINS")

    environment: str = Field(default="local", validation_alias="ENVIRONMENT")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    # Invoice OCR: OpenAI Vision only (gpt-4o-mini). Strong model on low-confidence retry.
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

    # Bank comment hybrid extraction (doc 9). Regex always runs first; LLM is
    # called only on comments where `needs_llm_fallback` returns True.
    bank_comment_use_llm: bool = Field(
        default=True, validation_alias="BANK_COMMENT_USE_LLM"
    )
    bank_comment_llm_model: str = Field(
        default="gpt-4o-mini", validation_alias="BANK_COMMENT_LLM_MODEL"
    )
    bank_comment_llm_batch_size: int = Field(
        default=25, validation_alias="BANK_COMMENT_LLM_BATCH_SIZE"
    )
    bank_comment_llm_timeout_seconds: int = Field(
        default=60, validation_alias="BANK_COMMENT_LLM_TIMEOUT_SECONDS"
    )
    bank_comment_llm_max_retries: int = Field(
        default=2, validation_alias="BANK_COMMENT_LLM_MAX_RETRIES"
    )

    match_amount_tolerance_eur: float = Field(
        default=0.02, validation_alias="MATCH_AMOUNT_TOLERANCE_EUR"
    )
    batch_amount_matching_enabled: bool = Field(
        default=True, validation_alias="BATCH_AMOUNT_MATCHING_ENABLED"
    )
    batch_amount_date_window_days: int = Field(
        default=90, validation_alias="BATCH_AMOUNT_DATE_WINDOW_DAYS"
    )

    jwt_access_expire_minutes: int = Field(
        default=15, validation_alias="JWT_ACCESS_EXPIRE_MINUTES"
    )
    jwt_refresh_expire_days: int = Field(
        default=7, validation_alias="JWT_REFRESH_EXPIRE_DAYS"
    )
    # Legacy alias — maps to access token lifetime if set without JWT_ACCESS_EXPIRE_MINUTES
    jwt_expire_minutes: int | None = Field(
        default=None, validation_alias="JWT_EXPIRE_MINUTES"
    )
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    cookie_samesite: str = Field(default="lax", validation_alias="COOKIE_SAMESITE")
    smtp_host: str = Field(default="", validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_username: str = Field(default="", validation_alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", validation_alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(
        default="no-reply@borek.com",
        validation_alias="SMTP_FROM_EMAIL",
    )
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")
    log_level: str = Field(default="info", validation_alias="LOG_LEVEL")

    # Verbose function-trace logging — keep OFF in production. See core/debug_logger.py
    debug: bool = Field(default=False, validation_alias="DEBUG")
    debug_log_dir: str = Field(default="/var/log/borek", validation_alias="DEBUG_LOG_DIR")
    debug_log_file: str = Field(
        default="backend-debug.log", validation_alias="DEBUG_LOG_FILE"
    )
    debug_log_max_bytes: int = Field(
        default=10 * 1024 * 1024, validation_alias="DEBUG_LOG_MAX_BYTES"
    )
    debug_log_backups: int = Field(default=5, validation_alias="DEBUG_LOG_BACKUPS")
    debug_max_value_chars: int = Field(
        default=400, validation_alias="DEBUG_MAX_VALUE_CHARS"
    )


settings = Settings()
