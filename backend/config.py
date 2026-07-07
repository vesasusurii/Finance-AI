"""Application settings — single source for env vars (doc 12)."""

from pathlib import Path

from pydantic import Field, model_validator
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
    # Invoice OCR: OpenAI Vision only. GPT-4o-mini is fastest; GPT-5 needs a
    # much higher max_completion_tokens budget (reasoning tokens burn first).
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    openai_model_strong: str = Field(
        default="gpt-4o", validation_alias="OPENAI_MODEL_STRONG"
    )
    openai_timeout_seconds: int = Field(
        default=120, validation_alias="OPENAI_TIMEOUT_SECONDS"
    )
    openai_max_retries: int = Field(default=2, validation_alias="OPENAI_MAX_RETRIES")
    openai_reasoning_max_completion_tokens: int = Field(
        default=16000,
        validation_alias="OPENAI_REASONING_MAX_COMPLETION_TOKENS",
    )
    openai_strong_retry_enabled: bool = Field(
        default=False, validation_alias="OPENAI_STRONG_RETRY_ENABLED"
    )
    openai_hybrid_text_enabled: bool = Field(
        default=True, validation_alias="OPENAI_HYBRID_TEXT_ENABLED"
    )
    # Digital PDFs: try text layer / text-only LLM before rasterising pages for Vision.
    openai_text_first_enabled: bool = Field(
        default=True, validation_alias="OPENAI_TEXT_FIRST_ENABLED"
    )
    openai_text_first_max_pages: int = Field(
        default=10, validation_alias="OPENAI_TEXT_FIRST_MAX_PAGES"
    )
    openai_text_first_min_chars: int = Field(
        default=200, validation_alias="OPENAI_TEXT_FIRST_MIN_CHARS"
    )
    openai_field_recovery_enabled: bool = Field(
        default=False, validation_alias="OPENAI_FIELD_RECOVERY_ENABLED"
    )
    extraction_eval_baseline_accuracy: float = Field(
        default=1.0, validation_alias="EXTRACTION_EVAL_BASELINE_ACCURACY"
    )
    openai_max_pdf_pages: int = Field(
        default=25, validation_alias="OPENAI_MAX_PDF_PAGES"
    )
    openai_vision_pages_per_request: int = Field(
        default=8, validation_alias="OPENAI_VISION_PAGES_PER_REQUEST"
    )
    openai_vision_page_batch_size: int = Field(
        default=6, validation_alias="OPENAI_VISION_PAGE_BATCH_SIZE"
    )
    # Parallel PDF page batches improve multi-page throughput while keeping
    # per-upload OpenAI fan-out bounded for rate-limit safety.
    openai_page_batch_concurrency: int = Field(
        default=4, validation_alias="OPENAI_PAGE_BATCH_CONCURRENCY"
    )
    openai_max_supplemental_chars: int = Field(
        default=80000, validation_alias="OPENAI_MAX_SUPPLEMENTAL_CHARS"
    )
    openai_vision_supplemental_text_max_chars: int = Field(
        default=12000,
        validation_alias="OPENAI_VISION_SUPPLEMENTAL_TEXT_MAX_CHARS",
    )
    openai_pdf_render_scale: float = Field(
        default=1.5, validation_alias="OPENAI_PDF_RENDER_SCALE"
    )
    openai_parallel_pdf_rendering: bool = Field(
        default=True, validation_alias="OPENAI_PARALLEL_PDF_RENDERING"
    )
    openai_pdf_render_workers: int = Field(
        default=4, validation_alias="OPENAI_PDF_RENDER_WORKERS"
    )
    openai_vision_full_document_max_bytes: int = Field(
        default=2_500_000, validation_alias="OPENAI_VISION_FULL_DOCUMENT_MAX_BYTES"
    )
    openai_adaptive_image_detail: bool = Field(
        default=True, validation_alias="OPENAI_ADAPTIVE_IMAGE_DETAIL"
    )
    openai_adaptive_image_detail_middle: str = Field(
        default="low", validation_alias="OPENAI_ADAPTIVE_IMAGE_DETAIL_MIDDLE"
    )
    # Dynamic Vision page selection: score pages and send only likely invoice pages.
    openai_dynamic_page_selection_enabled: bool = Field(
        default=True, validation_alias="OPENAI_DYNAMIC_PAGE_SELECTION_ENABLED"
    )
    openai_dynamic_page_selection_max_pages: int = Field(
        default=4, validation_alias="OPENAI_DYNAMIC_PAGE_SELECTION_MAX_PAGES"
    )
    openai_deterministic_merge_enabled: bool = Field(
        default=True, validation_alias="OPENAI_DETERMINISTIC_MERGE_ENABLED"
    )
    openai_deterministic_merge_min_confidence: float = Field(
        default=0.7, validation_alias="OPENAI_DETERMINISTIC_MERGE_MIN_CONFIDENCE"
    )
    ocr_cache_enabled: bool = Field(default=True, validation_alias="OCR_CACHE_ENABLED")
    max_startup_recovery_jobs: int = Field(
        default=50, validation_alias="MAX_STARTUP_RECOVERY_JOBS"
    )

    # Bank comment hybrid extraction (doc 9). Regex always runs first; LLM is
    # called only on comments where `needs_llm_fallback` returns True.
    bank_comment_use_llm: bool = Field(
        default=False, validation_alias="BANK_COMMENT_USE_LLM"
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

    fx_conversion_enabled: bool = Field(
        default=True, validation_alias="FX_CONVERSION_ENABLED"
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
    app_base_url: str = Field(
        default="http://localhost:5173",
        validation_alias="APP_BASE_URL",
    )
    log_level: str = Field(default="info", validation_alias="LOG_LEVEL")
    slow_route_ms: int = Field(default=1500, validation_alias="SLOW_ROUTE_MS")
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    rq_default_queue: str = Field(default="finance-ai", validation_alias="RQ_DEFAULT_QUEUE")
    queue_mode: str = Field(default="adaptive", validation_alias="QUEUE_MODE")
    rq_ocr_high_queue: str = Field(
        default="ocr_high_priority", validation_alias="RQ_OCR_HIGH_QUEUE"
    )
    rq_ocr_normal_queue: str = Field(default="ocr_normal", validation_alias="RQ_OCR_NORMAL_QUEUE")
    rq_review_queue: str = Field(default="review", validation_alias="RQ_REVIEW_QUEUE")
    rq_transaction_queue: str = Field(
        default="transaction", validation_alias="RQ_TRANSACTION_QUEUE"
    )
    task_max_retries: int = Field(default=3, validation_alias="TASK_MAX_RETRIES")
    task_retry_base_seconds: int = Field(
        default=10, validation_alias="TASK_RETRY_BASE_SECONDS"
    )
    openai_rps_limit: float = Field(default=5.0, validation_alias="OPENAI_RPS_LIMIT")
    openai_concurrency_limit: int = Field(
        default=4, validation_alias="OPENAI_CONCURRENCY_LIMIT"
    )
    ocr_backlog_defer_threshold: int = Field(
        default=5000, validation_alias="OCR_BACKLOG_DEFER_THRESHOLD"
    )
    ocr_avg_wait_defer_seconds: int = Field(
        default=60, validation_alias="OCR_AVG_WAIT_DEFER_SECONDS"
    )
    worker_metrics_window_seconds: int = Field(
        default=600, validation_alias="WORKER_METRICS_WINDOW_SECONDS"
    )

    # Supabase Session pooler caps total clients (often 15). Backend + worker each
    # hold a SQLAlchemy pool — keep defaults conservative; tune via .env per plan.
    db_pool_size: int = Field(default=2, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=2, validation_alias="DB_MAX_OVERFLOW")
    db_pool_timeout_seconds: int = Field(
        default=10, validation_alias="DB_POOL_TIMEOUT_SECONDS"
    )
    db_pool_recycle_seconds: int = Field(
        default=1800, validation_alias="DB_POOL_RECYCLE_SECONDS"
    )

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

    # Auth rate limits (sliding window via Redis)
    auth_login_rate_limit: int = Field(default=5, validation_alias="AUTH_LOGIN_RATE_LIMIT")
    auth_login_rate_window_seconds: int = Field(
        default=60, validation_alias="AUTH_LOGIN_RATE_WINDOW_SECONDS"
    )
    auth_forgot_password_rate_limit: int = Field(
        default=5, validation_alias="AUTH_FORGOT_PASSWORD_RATE_LIMIT"
    )
    auth_forgot_password_rate_window_seconds: int = Field(
        default=300, validation_alias="AUTH_FORGOT_PASSWORD_RATE_WINDOW_SECONDS"
    )

    @property
    def is_production_like(self) -> bool:
        return self.environment in ("staging", "production")

    @model_validator(mode="after")
    def normalize_database_url(self) -> "Settings":
        from db.database_url import prefer_supabase_transaction_pooler

        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        self.database_url = prefer_supabase_transaction_pooler(url)
        return self

    @model_validator(mode="after")
    def apply_legacy_jwt_expire_minutes(self) -> "Settings":
        import os

        if (
            self.jwt_expire_minutes is not None
            and "JWT_ACCESS_EXPIRE_MINUTES" not in os.environ
        ):
            self.jwt_access_expire_minutes = self.jwt_expire_minutes
        return self

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if not self.is_production_like:
            return self
        weak_jwt = (
            len(self.jwt_secret) < 32
            or "change_me" in self.jwt_secret.lower()
            or "dev_jwt" in self.jwt_secret.lower()
        )
        if weak_jwt:
            raise ValueError("JWT_SECRET is too weak for staging/production")
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in staging/production")
        if self.debug:
            raise ValueError("DEBUG must be false in staging/production")
        return self


def validate_settings_on_startup() -> list[str]:
    """Return non-fatal warnings for local misconfiguration."""
    warnings: list[str] = []
    if settings.environment == "local":
        if len(settings.jwt_secret) < 32:
            warnings.append("JWT_SECRET is shorter than 32 characters")
        if "change_me" in settings.jwt_secret.lower():
            warnings.append("JWT_SECRET still uses a placeholder value")
        if settings.debug:
            warnings.append("DEBUG logging is enabled")
        if settings.openai_model != "gpt-4o-mini":
            warnings.append(
                "OPENAI_MODEL is not gpt-4o-mini; local invoice OCR may be slow"
            )
        if settings.openai_max_retries > 2:
            warnings.append("OPENAI_MAX_RETRIES above 2 can slow local invoice OCR")
        if settings.openai_strong_retry_enabled:
            warnings.append("OPENAI_STRONG_RETRY_ENABLED slows local invoice OCR")
        if settings.openai_field_recovery_enabled:
            warnings.append("OPENAI_FIELD_RECOVERY_ENABLED slows local invoice OCR")
    return warnings


settings = Settings()
