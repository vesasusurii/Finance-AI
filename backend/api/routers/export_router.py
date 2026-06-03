from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from api.controllers.export_controller import ExportController
from api.dependencies import get_current_user, get_export_controller
from schemas.auth import UserContext
from schemas.report import PeriodReportResponse

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/period-report", response_model=PeriodReportResponse)
async def period_report(
    period: str = Query(..., pattern="^(day|week|month|year)$"),
    anchor_date: date | None = None,
    user: UserContext = Depends(get_current_user),
    ctrl: ExportController = Depends(get_export_controller),
) -> PeriodReportResponse:
    anchor = anchor_date or date.today()
    return await ctrl.period_report(user, period, anchor)


@router.get("/period-report-excel")
async def period_report_excel(
    period: str = Query(..., pattern="^(day|week|month|year)$"),
    anchor_date: date | None = None,
    user: UserContext = Depends(get_current_user),
    ctrl: ExportController = Depends(get_export_controller),
) -> StreamingResponse:
    anchor = anchor_date or date.today()
    return await ctrl.period_report_excel(user, period, anchor)


@router.get("/monthly-report", response_model=PeriodReportResponse)
async def monthly_report(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    user: UserContext = Depends(get_current_user),
    ctrl: ExportController = Depends(get_export_controller),
) -> PeriodReportResponse:
    return await ctrl.monthly_report(user, year, month)


@router.get("/purchase-invoices-excel")
async def purchase_invoices_excel(
    invoice_date_from: date | None = None,
    invoice_date_to: date | None = None,
    match_status: str | None = None,
    review_status: str | None = None,
    category: str | None = None,
    company: str | None = None,
    user: UserContext = Depends(get_current_user),
    ctrl: ExportController = Depends(get_export_controller),
) -> StreamingResponse:
    return await ctrl.purchase_invoices_excel(
        user,
        invoice_date_from,
        invoice_date_to,
        match_status,
        review_status,
        category,
        company,
    )
