import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from core.debug_logger import debug_trace, get_logger
from schemas.auth import UserContext

logger = get_logger(__name__)

PUBLIC_PATHS = frozenset(
    {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/health",
        "/api/ready",
    }
)


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "error": "unauthorized",
            "message": "Authentication required.",
        },
    )


@debug_trace
def _decode_token(token: str) -> UserContext | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
        )
        return UserContext(
            user_id=int(payload["user_id"]),
            email=str(payload.get("email", "")),
            role=str(payload.get("role", "finance")),
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Session probe: no cookie = signed out (204), bad cookie = 401
        if path == "/api/auth/me":
            token = request.cookies.get("access_token")
            if not token:
                request.state.user = None
            else:
                user = _decode_token(token)
                if user is None:
                    return _unauthorized()
                request.state.user = user
            return await call_next(request)

        if path not in PUBLIC_PATHS and path.startswith("/api"):
            token = request.cookies.get("access_token")
            if not token:
                return _unauthorized()
            user = _decode_token(token)
            if user is None:
                return _unauthorized()
            request.state.user = user
        return await call_next(request)


def get_current_user(request: Request) -> UserContext:
    user = getattr(request.state, "user", None)
    if user is None:
        raise RuntimeError("UserContext not set — route requires authentication")
    return user
