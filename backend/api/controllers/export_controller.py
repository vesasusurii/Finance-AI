from datetime import date, datetime, timezone

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from core.debug_logger import debug_trace, get_logger
from core.exceptions import ExportError
from repositories.invoice_repository import InvoiceRepository
from services.excel_service import ExcelService

logger = get_logger(__name__)


class ExportController:
    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        excel_service: ExcelService,
    ) -> None:
        self._invoice_repo = invoice_repo
        self._excel = excel_service

    @debug_trace
    async def export_excel(
        self,
        invoice_date_from: date | None,
        invoice_date_to: date | None,
        match_status: str | None,
        review_status: str | None,
        category: str | None,
    ) -> StreamingResponse:
        filters = {
            k: v
            for k, v in {
                "invoice_date_from": invoice_date_from,
                "invoice_date_to": invoice_date_to,
                "match_status": match_status,
                "review_status": review_status,
                "category": category,
            }.items()
            if v is not None
        }
        try:
            invoices = await self._invoice_repo.list_for_export(filters)
            data = self._excel.write_purchase_invoices_workbook(invoices)
        except Exception as exc:
            raise ExportError(str(exc)) from exc

        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"purchase_invoices_export_{stamp}.xlsx"
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
