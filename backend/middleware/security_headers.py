import re

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings

# Same-origin preview iframes (invoice PDF viewer). Blob URLs inherit the SPA CSP
# and break the browser PDF plugin; these routes are loaded via direct URL instead.
_EMBEDDABLE_FILE_PATH = re.compile(r"^/api/invoices/\d+/file$")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if _EMBEDDABLE_FILE_PATH.match(request.url.path):
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
        else:
            response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        if settings.is_production_like:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response
