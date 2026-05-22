from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Response

from config import settings
from repositories.user_repository import UserRepository
from schemas.auth import LoginRequest, LoginResponse, UserContext


class AuthController:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def login(self, request: LoginRequest, response: Response) -> LoginResponse:
        user = await self._user_repo.find_by_email(request.email)
        if not user or not bcrypt.checkpw(
            request.password.encode("utf-8"),
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

        exp = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_expire_minutes
        )
        token = jwt.encode(
            {
                "user_id": user.id,
                "email": user.email,
                "role": user.role,
                "exp": exp,
            },
            settings.jwt_secret,
            algorithm="HS256",
        )
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            max_age=settings.jwt_expire_minutes * 60,
        )
        return LoginResponse(user_id=user.id, email=user.email, role=user.role)

    async def logout(self, response: Response) -> dict:
        response.delete_cookie("access_token")
        return {"message": "Logged out."}

    async def me(self, user: UserContext) -> LoginResponse:
        return LoginResponse(
            user_id=user.user_id, email=user.email, role=user.role
        )
