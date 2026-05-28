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
    admin_user_router,
    auth_router,
    bank_statement_router,
    export_router,
    health_router,
    invoice_router,
    reconciliation_router,
    review_router,
)
from config import settings
from core.debug_logger import get_logger, setup_debug_logging
from core.exceptions import AppError, ExcelParseError, ExtractionError, ExportError
from db.pool import engine
from middleware.auth import AuthMiddleware
from middleware.cors import setup_cors
from middleware.request_handler import RequestHandlerMiddleware

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
setup_debug_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting Borek Finance backend (debug=%s, log_dir=%s)",
        settings.debug,
        settings.debug_log_dir,
    )
    os.makedirs(settings.storage_path, exist_ok=True)
    os.makedirs(os.path.join(settings.storage_path, "invoices"), exist_ok=True)
    os.makedirs(os.path.join(settings.storage_path, "bank_statements"), exist_ok=True)
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
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
        content={"error": code, "message": str(exc)},
    )


@app.exception_handler(ExtractionError)
async def extraction_error_handler(_request: Request, exc: ExtractionError):
    return JSONResponse(
        status_code=422,
        content={"error": "extraction_failed", "message": str(exc)},
    )


@app.exception_handler(ExportError)
async def export_error_handler(_request: Request, exc: ExportError):
    return JSONResponse(
        status_code=500,
        content={"error": "export_failed", "message": str(exc)},
    )


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError):
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": str(exc)},
    )


app.add_middleware(AuthMiddleware)
app.add_middleware(RequestHandlerMiddleware)
setup_cors(app)

app.include_router(health_router.router, prefix="/api")
app.include_router(auth_router.router, prefix="/api")
app.include_router(admin_user_router.router, prefix="/api")
app.include_router(invoice_router.router, prefix="/api")
app.include_router(export_router.router, prefix="/api")
app.include_router(bank_statement_router.router, prefix="/api")
app.include_router(reconciliation_router.router, prefix="/api")
app.include_router(review_router.router, prefix="/api")
