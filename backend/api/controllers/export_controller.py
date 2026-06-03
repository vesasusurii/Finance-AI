from datetime import date

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from core.debug_logger import debug_trace, get_logger
from core.exceptions import ExportError
from core.invoice_access import invoice_owner_user_id
from repositories.invoice_repository import InvoiceRepository
from schemas.auth import UserContext
from schemas.report import PeriodReportResponse
from services.excel_service import ExcelService
from services.export_service import ExportService

logger = get_logger(__name__)


class ExportController:
    def __init__(
        self,
        excel_service: ExcelService,
        export_service: ExportService,
        invoice_repo: InvoiceRepository,
    ) -> None:
        self._excel = excel_service
        self._export = export_service
        self._invoice_repo = invoice_repo

    @debug_trace
    async def period_report(
        self,
        user: UserContext,
        period: str,
        anchor_date: date,
    ) -> PeriodReportResponse:
        try:
            return await self._export.period_report(period, anchor_date, user)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_period", "message": str(exc)},
            ) from exc

    @debug_trace
    async def period_report_excel(
        self,
        user: UserContext,
        period: str,
        anchor_date: date,
    ) -> StreamingResponse:
        report = await self.period_report(user, period, anchor_date)
        try:
            data = self._excel.write_period_report_workbook(report)
        except Exception as exc:
            raise ExportError(str(exc)) from exc

        stamp = anchor_date.isoformat()
        filename = f"finance_report_{period}_{stamp}.xlsx"
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @debug_trace
    async def monthly_report(
        self,
        user: UserContext,
        year: int,
        month: int,
    ) -> PeriodReportResponse:
        if month < 1 or month > 12:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_month",
                    "message": "Month must be between 1 and 12.",
                },
            )
        anchor = date(year, month, 1)
        return await self.period_report(user, "month", anchor)

    @debug_trace
    async def purchase_invoices_excel(
        self,
        user: UserContext,
        invoice_date_from: date | None,
        invoice_date_to: date | None,
        match_status: str | None,
        review_status: str | None,
        category: str | None,
        company: str | None,
    ) -> StreamingResponse:
        filters = {
            k: v
            for k, v in {
                "invoice_date_from": invoice_date_from,
                "invoice_date_to": invoice_date_to,
                "match_status": match_status,
                "review_status": review_status,
                "category": category,
                "company": company,
            }.items()
            if v is not None
        }
        invoices = await self._invoice_repo.list_invoices_for_export(
            filters,
            owner_user_id=invoice_owner_user_id(user),
        )
        try:
            data = self._excel.write_purchase_invoices_workbook(invoices)
        except Exception as exc:
            raise ExportError(str(exc)) from exc

        stamp = date.today().isoformat()
        filename = f"purchase_invoices_export_{stamp}.xlsx"
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
