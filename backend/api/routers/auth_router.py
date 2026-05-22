from fastapi import APIRouter, Depends, Request, Response

from api.controllers.auth_controller import AuthController
from api.dependencies import get_auth_controller
from schemas.auth import LoginRequest, LoginResponse, UserContext

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


@router.get("/me", response_model=LoginResponse)
async def me(
    request: Request,
    ctrl: AuthController = Depends(get_auth_controller),
):
    user: UserContext | None = getattr(request.state, "user", None)
    if user is None:
        return Response(status_code=204)
    return await ctrl.me(user)
