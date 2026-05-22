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
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    jwt_expire_minutes: int = Field(default=480, validation_alias="JWT_EXPIRE_MINUTES")
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    cookie_samesite: str = Field(default="lax", validation_alias="COOKIE_SAMESITE")
    log_level: str = Field(default="info", validation_alias="LOG_LEVEL")


settings = Settings()
