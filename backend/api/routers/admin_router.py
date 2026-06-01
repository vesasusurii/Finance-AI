from fastapi import APIRouter, Depends

from api.controllers.admin_controller import AdminController
from api.dependencies import get_admin_controller, require_admin
from schemas.admin import PermissionsResponse, SettingsResponse
from schemas.auth import UserContext

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/permissions", response_model=PermissionsResponse)
async def get_permissions(
    _admin: UserContext = Depends(require_admin),
    ctrl: AdminController = Depends(get_admin_controller),
) -> PermissionsResponse:
    return await ctrl.permissions()


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    _admin: UserContext = Depends(require_admin),
    ctrl: AdminController = Depends(get_admin_controller),
) -> SettingsResponse:
    return await ctrl.settings()
