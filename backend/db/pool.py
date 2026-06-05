from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import settings


def _engine_connect_args(database_url: str) -> dict:
    """Supabase and other remote Postgres hosts require SSL."""
    parsed = urlparse(database_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    host = (parsed.hostname or "").lower()
    if host in ("db", "localhost", "127.0.0.1"):
        return {}
    return {"ssl": "require"}


engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
    pool_pre_ping=True,
    connect_args=_engine_connect_args(settings.database_url),
)
async_session = async_sessionmaker(engine, expire_on_commit=False)
