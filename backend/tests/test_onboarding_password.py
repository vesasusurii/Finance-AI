from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from api.controllers.auth_controller import AuthController
from api.controllers.user_controller import UserController
from middleware.auth import AuthMiddleware
from models.user import User
from schemas.auth import ChangePasswordRequest, LoginRequest, UserContext
from schemas.user import CreateUserRequest, ResetUserPasswordRequest


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _user(
    *,
    user_id: int = 1,
    email: str = "finance@example.com",
    password: str = "changeme",
    must_change_password: bool = True,
    email_verified: bool = False,
    token_version: int = 1,
) -> User:
    user = User(
        id=user_id,
        email=email,
        password_hash=_hash_password(password),
        role="finance",
        is_active=True,
        must_change_password=must_change_password,
        token_version=token_version,
        created_at=datetime.now(timezone.utc),
    )
    if email_verified:
        user.email_verified_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def user_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def auth_controller(user_repo: AsyncMock) -> AuthController:
    return AuthController(user_repo)


@pytest.fixture
def user_controller(user_repo: AsyncMock) -> UserController:
    return UserController(user_repo)


@pytest.mark.asyncio
async def test_create_user_sets_must_change_password(user_controller: UserController, user_repo: AsyncMock):
    user_repo.find_by_email.return_value = None
    created = _user(must_change_password=True, email_verified=False)
    user_repo.create.return_value = created

    result = await user_controller.create_user(
        CreateUserRequest(email="new@example.com", password="temporarypass1")
    )

    user_repo.create.assert_awaited_once()
    assert user_repo.create.await_args.kwargs["must_change_password"] is True
    assert result.email == created.email


@pytest.mark.asyncio
async def test_login_with_must_change_password_skips_verification(
    auth_controller: AuthController,
    user_repo: AsyncMock,
):
    user = _user(must_change_password=True, email_verified=True)
    user_repo.find_by_email.return_value = user
    response = MagicMock()

    with (
        patch("api.controllers.auth_controller.revoke_all_refresh_tokens"),
        patch("api.controllers.auth_controller.set_auth_cookies"),
        patch("api.controllers.auth_controller.send_verification_code") as send_code,
        patch("api.controllers.auth_controller.generate_verification_code") as gen_code,
    ):
        result = await auth_controller.login(
            LoginRequest(email=user.email, password="changeme"),
            response,
        )

    assert result.must_change_password is True
    user_repo.set_email_verification_code.assert_not_awaited()
    gen_code.assert_not_called()
    send_code.assert_not_called()


@pytest.mark.asyncio
async def test_login_without_must_change_password_sends_verification(
    auth_controller: AuthController,
    user_repo: AsyncMock,
):
    user = _user(must_change_password=False, email_verified=True)
    updated = _user(must_change_password=False, email_verified=False)
    user_repo.find_by_email.return_value = user
    user_repo.set_email_verification_code.return_value = updated
    response = MagicMock()

    with (
        patch("api.controllers.auth_controller.revoke_all_refresh_tokens"),
        patch("api.controllers.auth_controller.set_auth_cookies"),
        patch("api.controllers.auth_controller.send_verification_code") as send_code,
        patch("api.controllers.auth_controller.generate_verification_code", return_value="123456"),
    ):
        result = await auth_controller.login(
            LoginRequest(email=user.email, password="changeme"),
            response,
        )

    assert result.must_change_password is False
    user_repo.set_email_verification_code.assert_awaited_once()
    send_code.assert_called_once()


@pytest.mark.asyncio
async def test_change_password_clears_flag_and_sends_verification(
    auth_controller: AuthController,
    user_repo: AsyncMock,
):
    user = _user(must_change_password=True)
    cleared = _user(must_change_password=False, email_verified=False)
    after_verify_setup = _user(must_change_password=False, email_verified=False)
    user_repo.get.side_effect = [user, cleared]
    user_repo.update_password.return_value = cleared
    user_repo.set_email_verification_code.return_value = after_verify_setup
    response = MagicMock()
    user_ctx = UserContext(
        user_id=user.id,
        email=user.email,
        role="finance",
        email_verified=False,
        must_change_password=True,
    )

    with (
        patch("api.controllers.auth_controller.revoke_all_refresh_tokens"),
        patch("api.controllers.auth_controller.set_auth_cookies"),
        patch("api.controllers.auth_controller.send_verification_code") as send_code,
        patch("api.controllers.auth_controller.generate_verification_code", return_value="123456"),
    ):
        result = await auth_controller.change_password(
            user_ctx,
            ChangePasswordRequest(
                current_password="changeme",
                new_password="newpassword12",
            ),
            response,
        )

    user_repo.update_password.assert_awaited_once()
    user_repo.bump_token_version.assert_awaited_once_with(user.id)
    user_repo.set_email_verification_code.assert_awaited_once()
    send_code.assert_called_once()
    assert result.must_change_password is False


@pytest.mark.asyncio
async def test_reset_user_password_sets_flag_and_bumps_token_version(
    user_controller: UserController,
    user_repo: AsyncMock,
):
    target = _user(user_id=2, must_change_password=False, email_verified=True)
    reset = _user(user_id=2, must_change_password=True, email_verified=True)
    admin = UserContext(
        user_id=1,
        email="admin@example.com",
        role="admin",
        email_verified=True,
        must_change_password=False,
    )
    user_repo.get.side_effect = [target, reset]
    user_repo.reset_password.return_value = reset
    user_repo.bump_token_version.return_value = 2

    with patch("api.controllers.user_controller.revoke_all_refresh_tokens") as revoke:
        result = await user_controller.reset_user_password(
            2,
            ResetUserPasswordRequest(password="temporarypass1"),
            admin,
        )

    user_repo.reset_password.assert_awaited_once()
    user_repo.bump_token_version.assert_awaited_once_with(2)
    revoke.assert_called_once_with(2)
    assert result.id == 2


@pytest.mark.asyncio
async def test_reset_user_password_rejects_self_reset(
    user_controller: UserController,
):
    admin = UserContext(
        user_id=1,
        email="admin@example.com",
        role="admin",
        email_verified=True,
        must_change_password=False,
    )

    with pytest.raises(HTTPException) as exc:
        await user_controller.reset_user_password(
            1,
            ResetUserPasswordRequest(password="temporarypass1"),
            admin,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "cannot_reset_own_password"


@pytest.mark.asyncio
async def test_middleware_blocks_protected_route_when_must_change_password():
    middleware = AuthMiddleware(app=MagicMock())
    user = UserContext(
        user_id=1,
        email="finance@example.com",
        role="finance",
        email_verified=True,
        must_change_password=True,
    )

    async def call_next(request: Request) -> Response:
        return Response("ok", status_code=200)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/invoices",
        "headers": [(b"cookie", b"access_token=test-token")],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "scheme": "http",
        "http_version": "1.1",
    }
    request = Request(scope)

    with patch(
        "middleware.auth._validate_access_token",
        new=AsyncMock(return_value=(user, None)),
    ):
        response = await middleware.dispatch(request, call_next)

    assert response.status_code == 403
    body = response.body.decode()
    assert "onboarding_required" in body


@pytest.mark.asyncio
async def test_middleware_allows_change_password_during_onboarding():
    middleware = AuthMiddleware(app=MagicMock())
    user = UserContext(
        user_id=1,
        email="finance@example.com",
        role="finance",
        email_verified=False,
        must_change_password=True,
    )

    async def call_next(request: Request) -> Response:
        return Response("ok", status_code=200)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/auth/change-password",
        "headers": [(b"cookie", b"access_token=test-token")],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "scheme": "http",
        "http_version": "1.1",
    }
    request = Request(scope)

    with patch(
        "middleware.auth._validate_access_token",
        new=AsyncMock(return_value=(user, None)),
    ):
        response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    assert response.body == b"ok"
