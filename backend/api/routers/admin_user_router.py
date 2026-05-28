from fastapi import APIRouter, Depends, status

from api.controllers.user_controller import UserController
from api.dependencies import get_user_controller, require_admin
from schemas.auth import UserContext
from schemas.user import CreateUserRequest, UserListResponse, UserSummary

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    _admin: UserContext = Depends(require_admin),
    ctrl: UserController = Depends(get_user_controller),
):
    return await ctrl.list_users()


@router.post("", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    _admin: UserContext = Depends(require_admin),
    ctrl: UserController = Depends(get_user_controller),
):
    return await ctrl.create_user(body)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: int,
    admin: UserContext = Depends(require_admin),
    ctrl: UserController = Depends(get_user_controller),
):
    return await ctrl.delete_user(user_id, admin)
