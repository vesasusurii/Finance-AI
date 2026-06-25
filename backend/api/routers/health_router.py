from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db_session
from core.redis_client import get_redis_connection

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_db_session)):
    checks: dict[str, str] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "unreachable"

    try:
        if get_redis_connection().ping():
            checks["redis"] = "ok"
        else:
            checks["redis"] = "unreachable"
    except Exception:
        checks["redis"] = "unreachable"

    if all(status == "ok" for status in checks.values()):
        return {"status": "ready", **checks}
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", **checks},
    )
