from datetime import date

from fastapi import APIRouter, Depends, Query

from api.controllers.audit_controller import AuditController
from api.dependencies import get_audit_controller, require_admin
from schemas.audit_log import AuditLogListResponse
from schemas.auth import UserContext

router = APIRouter(prefix="/admin/audit-logs", tags=["admin-audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    action: str | None = None,
    entity_type: str | None = None,
    user_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    _admin: UserContext = Depends(require_admin),
    ctrl: AuditController = Depends(get_audit_controller),
) -> AuditLogListResponse:
    return await ctrl.list_logs(
        page,
        limit,
        action,
        entity_type,
        user_id,
        date_from,
        date_to,
    )
