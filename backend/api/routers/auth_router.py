from fastapi import APIRouter, Depends, Request, Response

from api.controllers.auth_controller import AuthController
from api.dependencies import get_auth_controller, get_current_user
from schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    UserContext,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    ctrl: AuthController = Depends(get_auth_controller),
):
    return await ctrl.login(body, response)


@router.post("/logout")
async def logout(
    response: Response,
    ctrl: AuthController = Depends(get_auth_controller),
):
    return await ctrl.logout(response)


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


@router.post("/verify-email", response_model=LoginResponse)
async def verify_email(
    body: VerifyEmailRequest,
    response: Response,
    user: UserContext = Depends(get_current_user),
    ctrl: AuthController = Depends(get_auth_controller),
):
    return await ctrl.verify_email(user, body, response)


@router.post("/change-password", response_model=LoginResponse)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    user: UserContext = Depends(get_current_user),
    ctrl: AuthController = Depends(get_auth_controller),
):
    return await ctrl.change_password(user, body, response)
