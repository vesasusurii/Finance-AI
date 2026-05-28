import io
from datetime import date, datetime
from decimal import Decimal

from openpyxl import load_workbook

from schemas.invoice import InvoiceResponse
from services.excel_service import HEADERS, ExcelService


def _minimal_invoice(**overrides) -> InvoiceResponse:
    base = {
        "id": 1,
        "invoice_date": None,
        "name_of_company": "Acme SH.P.K.",
        "address_of_company": "Rr. Nëna Terezë 1, Prishtinë",
        "invoice_number": "120260048",
        "amount": None,
        "debt": None,
        "currency": "EUR",
        "account_details": None,
        "internal_note_description": None,
        "client_employee_related": "Borek Solutions",
        "paid_at_date": None,
        "paid_by": None,
        "fixed_status": None,
        "category": None,
        "extraction_confidence": None,
        "field_confidences": None,
        "review_status": "approved",
        "match_status": "unmatched",
        "source_file_id": None,
        "source_filename": None,
        "source_mime_type": None,
        "created_at": datetime(2026, 1, 15, 10, 0, 0),
        "updated_at": datetime(2026, 1, 15, 10, 0, 0),
    }
    base.update(overrides)
    return InvoiceResponse.model_validate(base)


def test_export_headers_and_styling():
    inv = _minimal_invoice(
        invoice_date=date(2026, 1, 28),
        amount=Decimal("1931.78"),
        debt=Decimal("28.60"),
        paid_at_date=date(2026, 2, 25),
    )
    data = ExcelService().write_purchase_invoices_workbook([inv])
    wb = load_workbook(io.BytesIO(data))
    ws = wb.active

    assert [ws.cell(1, c).value for c in range(1, len(HEADERS) + 1)] == HEADERS
    assert ws.cell(1, 1).fill.start_color.rgb.upper().endswith("0D123F")
    assert ws.cell(1, 1).font.bold is True
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == f"A1:M2"

    assert ws.cell(2, 1).number_format == "DD.MM.YYYY"
    assert ws.cell(2, 5).number_format == "#,##0.00"
    assert ws.cell(2, 4).number_format == "@"
    assert ws.cell(2, 4).value == "120260048"


def test_export_empty_sheet_has_headers_only():
    data = ExcelService().write_purchase_invoices_workbook([])
    wb = load_workbook(io.BytesIO(data))
    ws = wb.active
    assert ws.max_row == 1
    assert ws.cell(1, 4).value == "Invoice Number"
