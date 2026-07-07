"""Database URL helpers for local Postgres vs Supabase pooler."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def _normalized_host(database_url: str) -> str:
    parsed = urlparse(
        database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    return (parsed.hostname or "").lower()


def is_supabase_pooler(database_url: str) -> bool:
    return "pooler.supabase.com" in _normalized_host(database_url)


def is_supabase_session_pooler(database_url: str) -> bool:
    if not is_supabase_pooler(database_url):
        return False
    parsed = urlparse(
        database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    return parsed.port in (None, 5432)


def prefer_supabase_transaction_pooler(database_url: str) -> str:
    """Use Supabase transaction pooler (6543) instead of session pooler (5432)."""
    if not is_supabase_session_pooler(database_url):
        return database_url

    parsed = urlparse(
        database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    scheme = "postgresql+asyncpg" if "+asyncpg" in database_url else "postgresql"
    host = parsed.hostname or ""
    if parsed.port == 5432:
        userinfo = parsed.netloc.rsplit("@", 1)[0]
        netloc = f"{userinfo}@{host}:6543"
    elif parsed.port is None:
        netloc = f"{parsed.netloc}:6543" if parsed.netloc else f"{host}:6543"
    else:
        return database_url
    rebuilt = urlunparse(
        (
            scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
    return rebuilt


def asyncpg_connect_args(database_url: str) -> dict:
    """Connection args for asyncpg — SSL for remote hosts, no stmt cache on pooler."""
    parsed = urlparse(
        database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    host = (parsed.hostname or "").lower()
    args: dict = {}
    if host not in ("db", "localhost", "127.0.0.1"):
        args["ssl"] = "require"
    if is_supabase_pooler(database_url):
        # PgBouncer transaction mode does not support prepared statement caching.
        args["statement_cache_size"] = 0
    return args


def use_null_pool(database_url: str) -> bool:
    """Let Supabase PgBouncer own pooling; avoid double-pooling in SQLAlchemy."""
    return is_supabase_pooler(database_url)
