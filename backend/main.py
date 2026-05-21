"""
Starter FastAPI app — health endpoints only until full backend (doc 6) is implemented.
Replace/extend this module; keep GET /api/health and GET /api/ready contracts (doc 5).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(
    title="Borek Finance Invoice Automation",
    description="Starter API — see DOCS/6. Backend Architecture 1.md",
    version="0.1.0-starter",
)

_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/ready")
async def ready():
    # Starter: no DB check until SQLAlchemy is wired (doc 6 / doc 12)
    database_url = os.getenv("DATABASE_URL", "")
    db_status = "configured" if database_url else "not_configured"
    return {"status": "ready", "db": db_status}
