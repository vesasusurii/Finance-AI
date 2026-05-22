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

from api.routers import auth_router, export_router, health_router, invoice_router
from config import settings
from core.exceptions import AppError, ExtractionError, ExportError
from db.pool import engine
from middleware.auth import AuthMiddleware
from middleware.cors import setup_cors
from middleware.request_handler import RequestHandlerMiddleware

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.storage_path, exist_ok=True)
    os.makedirs(os.path.join(settings.storage_path, "invoices"), exist_ok=True)
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    app.state.openai_client = (
        AsyncOpenAI(api_key=settings.openai_api_key)
        if settings.openai_api_key
        else None
    )
    yield
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
app.include_router(invoice_router.router, prefix="/api")
app.include_router(export_router.router, prefix="/api")
