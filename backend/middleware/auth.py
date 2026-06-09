from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.debug_logger import get_logger
from core.token_version_check import token_version_valid
from schemas.auth import UserContext
from services.jwt_service import decode_access_token, get_access_token_version

logger = get_logger(__name__)

PUBLIC_PATHS = frozenset(
    {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/refresh",
        "/api/health",
        "/api/ready",
        "/api/invoices/email-upload",
    }
)

ONBOARDING_PATHS = frozenset(
    {
        "/api/auth/me",
        "/api/auth/logout",
        "/api/auth/refresh",
        "/api/auth/verify-email",
        "/api/auth/change-password",
        "/api/auth/resend-verification-code",
    }
)


def _forbidden(
    *,
    error: str,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": error, "message": message},
    )


def _unauthorized(
    *,
    error: str = "unauthorized",
    message: str = "Authentication required.",
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": error, "message": message},
    )


async def _validate_access_token(
    token: str,
) -> tuple[UserContext | None, str | None]:
    user, err = decode_access_token(token)
    if err or user is None:
        return user, err
    jwt_version = get_access_token_version(token)
    if jwt_version is None:
        return None, "invalid_token"
    if not await token_version_valid(user.user_id, jwt_version):
        return None, "invalid_token"
    return user, None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path == "/api/auth/me":
            token = request.cookies.get("access_token")
            if not token:
                request.state.user = None
            else:
                user, err = await _validate_access_token(token)
                if err == "token_expired":
                    return _unauthorized(
                        error="token_expired",
                        message="Access token expired.",
                    )
                if user is None:
                    return _unauthorized(
                        error="invalid_token",
                        message="Invalid session.",
                    )
                request.state.user = user
            return await call_next(request)

        if path not in PUBLIC_PATHS and path.startswith("/api"):
            token = request.cookies.get("access_token")
            if not token:
                return _unauthorized()
            user, err = await _validate_access_token(token)
            if err == "token_expired":
                return _unauthorized(
                    error="token_expired",
                    message="Access token expired.",
                )
            if user is None:
                return _unauthorized(
                    error="invalid_token",
                    message="Invalid session.",
                )
            request.state.user = user

        user = getattr(request.state, "user", None)
        if (
            user is not None
            and path.startswith("/api")
            and path not in PUBLIC_PATHS
            and path not in ONBOARDING_PATHS
            and (not user.email_verified or user.must_change_password)
        ):
            return _forbidden(
                error="onboarding_required",
                message="Complete email verification and password change before continuing.",
            )

        return await call_next(request)


def get_current_user(request: Request) -> UserContext:
    user = getattr(request.state, "user", None)
    if user is None:
        raise RuntimeError("UserContext not set — route requires authentication")
    return user
