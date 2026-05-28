import io
from datetime import date

from openpyxl import Workbook

from core.debug_logger import debug_trace, get_logger
from schemas.invoice import InvoiceResponse

logger = get_logger(__name__)

HEADERS = [
    "Invoice Date",
    "Name of Company",
    "Adress of Company",
    "Invoice Number",
    "Amount",
    "Account Details",
    "Internal Note/Description",
    "Client / Employee Related",
    "paid at (Date)",
    "paid by",
    "Fixed/Not fixed",
    "Category",
]


class ExcelService:
    @debug_trace
    def write_purchase_invoices_workbook(
        self, invoices: list[InvoiceResponse]
    ) -> bytes:
        logger.debug(
            "Excel export: rows=%d (list[InvoiceResponse])", len(invoices)
        )
        wb = Workbook()
        ws = wb.active
        ws.title = "Purchase Invoices"
        ws.append(HEADERS)

        for inv in invoices:
            ws.append(
                [
                    inv.invoice_date.isoformat() if inv.invoice_date else None,
                    inv.name_of_company,
                    inv.address_of_company,
                    inv.invoice_number,
                    float(inv.amount) if inv.amount is not None else None,
                    inv.account_details,
                    inv.internal_note_description,
                    inv.client_employee_related,
                    inv.paid_at_date.isoformat() if inv.paid_at_date else None,
                    inv.paid_by,
                    inv.fixed_status,
                    inv.category,
                ]
            )

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
