from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import settings
from db.database_url import asyncpg_connect_args, use_null_pool


_engine_kwargs: dict = {
    "echo": False,
    "pool_pre_ping": True,
    "connect_args": asyncpg_connect_args(settings.database_url),
}
if use_null_pool(settings.database_url):
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
    )

engine = create_async_engine(settings.database_url, **_engine_kwargs)
async_session = async_sessionmaker(engine, expire_on_commit=False)
