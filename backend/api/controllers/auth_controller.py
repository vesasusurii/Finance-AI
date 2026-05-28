from __future__ import annotations

import bcrypt
from fastapi import HTTPException, Request, Response, status

from config import settings
from core.debug_logger import debug_trace, get_logger
from core.roles import is_valid_role
from models.user import User
from repositories.user_repository import UserRepository
from schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UserContext,
    VerifyEmailRequest,
)
from services.email_verification_service import (
    generate_verification_code,
    hash_verification_code,
    send_verification_code,
    verification_expires_at,
    verify_code,
)
from services.jwt_service import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)


def _cookie_params() -> dict:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
    }


def _user_auth_flags(user: User) -> tuple[bool, bool]:
    return user.email_verified_at is not None, user.must_change_password


def _login_response(user: User) -> LoginResponse:
    email_verified, must_change_password = _user_auth_flags(user)
    return LoginResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,
        email_verified=email_verified,
        must_change_password=must_change_password,
    )


def set_auth_cookies(response: Response, *, user: User) -> None:
    email_verified, must_change_password = _user_auth_flags(user)
    access = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        email_verified=email_verified,
        must_change_password=must_change_password,
    )
    refresh = create_refresh_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        email_verified=email_verified,
        must_change_password=must_change_password,
    )
    params = _cookie_params()
    response.set_cookie(
        key="access_token",
        value=access,
        max_age=settings.jwt_access_expire_minutes * 60,
        **params,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        max_age=settings.jwt_refresh_expire_days * 24 * 60 * 60,
        **params,
    )


def clear_auth_cookies(response: Response) -> None:
    params = _cookie_params()
    response.delete_cookie(key="access_token", **params)
    response.delete_cookie(key="refresh_token", **params)

logger = get_logger(__name__)


class AuthController:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def _authenticate(self, email: str, password: str) -> User:
        user = await self._user_repo.find_by_email(email)
        if not user or not bcrypt.checkpw(
            password.encode("utf-8"),
            user.password_hash.encode("utf-8"),
        ):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_credentials",
                    "message": "Wrong email or password.",
                },
            )
        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "account_disabled",
                    "message": "This account has been disabled.",
                },
            )
        if not is_valid_role(user.role):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "invalid_role",
                    "message": "User account has an invalid role.",
                },
            )
        return user

    async def login(self, request: LoginRequest, response: Response) -> LoginResponse:
        user = await self._authenticate(request.email, request.password)
        set_auth_cookies(response, user=user)
        return _login_response(user)

    async def refresh(self, request: Request, response: Response) -> LoginResponse:
        token = request.cookies.get("refresh_token")
        if not token:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "refresh_required",
                    "message": "Session expired. Please sign in again.",
                },
            )

        ctx = decode_refresh_token(token)
        if ctx is None:
            clear_auth_cookies(response)
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_refresh",
                    "message": "Session expired. Please sign in again.",
                },
            )

        user = await self._user_repo.get(ctx.user_id)
        if not user or not user.is_active or not is_valid_role(user.role):
            clear_auth_cookies(response)
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_refresh",
                    "message": "Session expired. Please sign in again.",
                },
            )

        set_auth_cookies(response, user=user)
        return _login_response(user)

    @debug_trace
    async def logout(self, response: Response) -> dict:
        clear_auth_cookies(response)
        return {"message": "Logged out."}

    @debug_trace
    async def me(self, user: UserContext) -> LoginResponse:
        db_user = await self._user_repo.get(user.user_id)
        if db_user is None or not db_user.is_active:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_session",
                    "message": "Session expired. Please sign in again.",
                },
            )
        return _login_response(db_user)

    async def verify_email(
        self,
        user_ctx: UserContext,
        body: VerifyEmailRequest,
        response: Response,
    ) -> LoginResponse:
        user = await self._user_repo.get(user_ctx.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_session",
                    "message": "Session expired. Please sign in again.",
                },
            )
        if user.email_verified_at is not None:
            return _login_response(user)
        if user.must_change_password:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "password_change_required",
                    "message": "Change your password before verifying your email.",
                },
            )

        if not verify_code(user, body.code):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_verification_code",
                    "message": "Invalid or expired verification code.",
                },
            )

        user = await self._user_repo.mark_email_verified(user)
        set_auth_cookies(response, user=user)
        return _login_response(user)

    async def change_password(
        self,
        user_ctx: UserContext,
        body: ChangePasswordRequest,
        response: Response,
    ) -> LoginResponse:
        user = await self._user_repo.get(user_ctx.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_session",
                    "message": "Session expired. Please sign in again.",
                },
            )
        if not user.must_change_password:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "password_change_not_required",
                    "message": "Password change is not required for this account.",
                },
            )
        if not bcrypt.checkpw(
            body.current_password.encode("utf-8"),
            user.password_hash.encode("utf-8"),
        ):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_current_password",
                    "message": "Current password is incorrect.",
                },
            )
        if body.current_password == body.new_password:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "same_password",
                    "message": "New password must be different from the current password.",
                },
            )

        password_hash = bcrypt.hashpw(
            body.new_password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")
        user = await self._user_repo.update_password(user, password_hash)
        verification_code = generate_verification_code()
        user = await self._user_repo.set_email_verification_code(
            user,
            code_hash=hash_verification_code(verification_code),
            expires_at=verification_expires_at(),
        )
        send_verification_code(user.email, verification_code)
        set_auth_cookies(response, user=user)
        return _login_response(user)
