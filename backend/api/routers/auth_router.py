from fastapi import APIRouter, Depends, Request, Response

from api.controllers.auth_controller import AuthController
from api.dependencies import get_auth_controller, get_current_user
from core.auth_rate_limiter import check_forgot_password_rate_limit, check_login_rate_limit
from schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    ResetPasswordRequest,
    UserContext,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    ctrl: AuthController = Depends(get_auth_controller),
):
    check_login_rate_limit(request)
    return await ctrl.login(body, response)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    ctrl: AuthController = Depends(get_auth_controller),
):
    return await ctrl.logout(request, response)


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    request: Request,
    response: Response,
    ctrl: AuthController = Depends(get_auth_controller),
):
    return await ctrl.refresh(request, response)


@router.get("/me", response_model=LoginResponse)
async def me(
    request: Request,
    ctrl: AuthController = Depends(get_auth_controller),
):
    user: UserContext | None = getattr(request.state, "user", None)
    if user is None:
        return Response(status_code=204)
    return await ctrl.me(user)


@router.post("/change-password", response_model=LoginResponse)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    user: UserContext = Depends(get_current_user),
    ctrl: AuthController = Depends(get_auth_controller),
):
    return await ctrl.change_password(user, body, response)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    ctrl: AuthController = Depends(get_auth_controller),
):
    check_forgot_password_rate_limit(request)
    return await ctrl.forgot_password(body)


@router.post("/reset-password", response_model=LoginResponse)
async def reset_password(
    body: ResetPasswordRequest,
    response: Response,
    ctrl: AuthController = Depends(get_auth_controller),
):
    return await ctrl.reset_password(body, response)
