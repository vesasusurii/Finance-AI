from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.controllers.export_controller import ExportController
from api.dependencies import get_current_user, get_export_controller
from schemas.auth import UserContext

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/purchase-invoices-excel")
async def export_purchase_invoices_excel(
    invoice_date_from: date | None = None,
    invoice_date_to: date | None = None,
    match_status: str | None = None,
    review_status: str | None = None,
    category: str | None = None,
    user: UserContext = Depends(get_current_user),
    ctrl: ExportController = Depends(get_export_controller),
) -> StreamingResponse:
    return await ctrl.export_excel(
        user,
        invoice_date_from,
        invoice_date_to,
        match_status,
        review_status,
        category,
    )
