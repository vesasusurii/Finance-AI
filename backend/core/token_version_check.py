"""Validate JWT token_version against the database (with Redis cache)."""

from __future__ import annotations

from core.token_version_cache import cache_token_version, get_cached_token_version
from db.pool import async_session
from repositories.user_repository import UserRepository


async def token_version_valid(user_id: int, jwt_version: int) -> bool:
    cached = get_cached_token_version(user_id)
    if cached is not None:
        return cached == jwt_version

    async with async_session() as session:
        db_version = await UserRepository(session).get_token_version(user_id)
    if db_version is None:
        return False
    cache_token_version(user_id, db_version)
    return db_version == jwt_version
