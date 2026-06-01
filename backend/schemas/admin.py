from pydantic import BaseModel, Field

from schemas.auth import UserRole


class PermissionCapability(BaseModel):
    key: str
    label: str
    description: str
    finance: bool
    admin: bool


class RoleInfo(BaseModel):
    role: UserRole
    label: str
    description: str


class PermissionsResponse(BaseModel):
    roles: list[RoleInfo]
    capabilities: list[PermissionCapability]


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


class SettingItem(BaseModel):
    key: str
    label: str
    value: str
    group: str


class SettingsResponse(BaseModel):
    items: list[SettingItem]
    note: str = Field(
        default=(
            "Secrets and connection strings are configured via environment "
            "variables and are not shown here."
        )
    )
