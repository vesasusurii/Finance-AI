from core.permissions import PERMISSION_MATRIX, ROLE_DESCRIPTIONS
from core.roles import ROLE_ADMIN, ROLE_FINANCE
from schemas.admin import (
    PermissionCapability,
    PermissionsResponse,
    RoleInfo,
    SettingsResponse,
)
from services.admin_settings_service import AdminSettingsService


class AdminController:
    def __init__(self, settings_service: AdminSettingsService) -> None:
        self._settings = settings_service

    async def permissions(self) -> PermissionsResponse:
        return PermissionsResponse(
            roles=[
                RoleInfo(
                    role=ROLE_FINANCE,
                    label="Finance",
                    description=ROLE_DESCRIPTIONS[ROLE_FINANCE],
                ),
                RoleInfo(
                    role=ROLE_ADMIN,
                    label="Admin",
                    description=ROLE_DESCRIPTIONS[ROLE_ADMIN],
                ),
            ],
            capabilities=[
                PermissionCapability(
                    key=row.key,
                    label=row.label,
                    description=row.description,
                    finance=row.finance,
                    admin=row.admin,
                )
                for row in PERMISSION_MATRIX
            ],
        )

    async def settings(self) -> SettingsResponse:
        return self._settings.get_settings()
