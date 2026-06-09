"""
Borek Finance — FastAPI application.
"""

import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI

from api.routers import (
    admin_audit_router,
    admin_router,
    admin_user_router,
    auth_router,
    bank_statement_router,
    document_router,
    export_router,
    health_router,
    invoice_router,
    metrics_router,
    reconciliation_router,
    review_router,
)
from config import settings, validate_settings_on_startup
from core.debug_logger import get_logger, setup_debug_logging
from core.exceptions import AppError, ExcelParseError, ExtractionError, ExportError
from db.pool import engine
from middleware.auth import AuthMiddleware
from middleware.cors import setup_cors
from middleware.request_handler import RequestHandlerMiddleware
from middleware.security_headers import SecurityHeadersMiddleware
from utils.file_storage import bind_http_client
from services.upload_recovery import recover_stuck_invoice_uploads

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
setup_debug_logging()
logger = get_logger(__name__)

_IS_LOCAL = settings.environment == "local"


def _client_error_message(exc: Exception, *, fallback: str) -> str:
    if _IS_LOCAL:
        return str(exc)
    return fallback


@asynccontextmanager
async def lifespan(app: FastAPI):
    for warning in validate_settings_on_startup():
        logger.warning("Startup config warning: %s", warning)
    logger.info(
        "Starting Borek Finance backend (env=%s, debug=%s, log_dir=%s)",
        settings.environment,
        settings.debug,
        settings.debug_log_dir,
    )
    os.makedirs(settings.storage_path, exist_ok=True)
    os.makedirs(os.path.join(settings.storage_path, "invoices"), exist_ok=True)
    os.makedirs(os.path.join(settings.storage_path, "bank_statements"), exist_ok=True)
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    bind_http_client(app.state.http_client)
    if settings.storage_backend == "supabase":
        if not settings.supabase_url or not settings.supabase_service_role_key:
            logger.warning(
                "STORAGE_BACKEND=supabase but SUPABASE_URL or "
                "SUPABASE_SERVICE_ROLE_KEY is missing — uploads may fail."
            )
    app.state.openai_client = (
        AsyncOpenAI(api_key=settings.openai_api_key)
        if settings.openai_api_key
        else None
    )
    logger.debug(
        "OpenAI client configured: %s (model=%s, strong=%s)",
        app.state.openai_client is not None,
        settings.openai_model,
        settings.openai_model_strong,
    )
    try:
        await recover_stuck_invoice_uploads(app.state.openai_client)
    except Exception as exc:
        logger.warning(
            "Startup OCR recovery skipped (is Redis running? REDIS_URL=%s): %s",
            settings.redis_url,
            exc,
        )
    yield
    logger.info("Shutting down Borek Finance backend")
    await app.state.http_client.aclose()
    if app.state.openai_client is not None:
        await app.state.openai_client.close()
    await engine.dispose()


app = FastAPI(
    title="Borek Finance Invoice Automation",
    description="Internal invoice extraction and bank matching",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs" if _IS_LOCAL else None,
    redoc_url=None,
    openapi_url="/openapi.json" if _IS_LOCAL else None,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "message": str(exc.detail)},
    )


@app.exception_handler(ExcelParseError)
async def excel_parse_error_handler(_request: Request, exc: ExcelParseError):
    msg = str(exc).lower()
    if "header" in msg or "column" in msg or "komenti" in msg:
        code = "missing_required_columns"
    elif "no transaction" in msg or "no data" in msg:
        code = "empty_file"
    elif "unsupported" in msg:
        code = "unsupported_file_type"
    else:
        code = "parse_error"
    return JSONResponse(
        status_code=400,
        content={
            "error": code,
            "message": _client_error_message(exc, fallback="Could not parse Excel file."),
        },
    )


@app.exception_handler(ExtractionError)
async def extraction_error_handler(_request: Request, exc: ExtractionError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "extraction_failed",
            "message": _client_error_message(exc, fallback="Extraction failed."),
        },
    )


@app.exception_handler(ExportError)
async def export_error_handler(_request: Request, exc: ExportError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "export_failed",
            "message": _client_error_message(exc, fallback="Export failed."),
        },
    )


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": _client_error_message(
                exc, fallback="An unexpected error occurred."
            ),
        },
    )


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RequestHandlerMiddleware)
setup_cors(app)

app.include_router(health_router.router, prefix="/api")
app.include_router(auth_router.router, prefix="/api")
app.include_router(admin_user_router.router, prefix="/api")
app.include_router(admin_router.router, prefix="/api")
app.include_router(admin_audit_router.router, prefix="/api")
app.include_router(invoice_router.router, prefix="/api")
app.include_router(metrics_router.router, prefix="/api")
app.include_router(document_router.router, prefix="/api")
app.include_router(export_router.router, prefix="/api")
app.include_router(bank_statement_router.router, prefix="/api")
app.include_router(reconciliation_router.router, prefix="/api")
app.include_router(review_router.router, prefix="/api")
