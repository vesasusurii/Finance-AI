import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.debug_logger import get_logger
from core.exceptions import AppError
from config import settings

logger = get_logger(__name__)


class RequestHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        start = time.perf_counter()
        logger.info(
            "%s %s — started",
            request.method,
            request.url.path,
            extra={"correlation_id": correlation_id},
        )
        try:
            response = await call_next(request)
        except AppError as exc:
            logger.exception(
                "%s %s — AppError",
                request.method,
                request.url.path,
                extra={"correlation_id": correlation_id},
            )
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": str(exc)},
            )
        except Exception:
            logger.exception(
                "%s %s — unhandled",
                request.method,
                request.url.path,
                extra={"correlation_id": correlation_id},
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "message": "An unexpected error occurred.",
                },
            )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        log_fn = logger.warning if elapsed_ms >= settings.slow_route_ms else logger.info
        log_fn(
            "%s %s — %s — %sms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            extra={
                "correlation_id": correlation_id,
                "latency_ms": elapsed_ms,
                "slow_route": elapsed_ms >= settings.slow_route_ms,
            },
        )
        response.headers["X-Correlation-ID"] = correlation_id
        return response
