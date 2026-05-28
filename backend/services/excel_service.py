"""Purchase Invoices Database Excel export (openpyxl)."""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from schemas.invoice import InvoiceResponse

# Borek Finance palette (DOCS/branding/theme.css)
_COLOR_NAVY_HEADER = "0D123F"
_COLOR_HEADER_TEXT = "FFFFFF"
_COLOR_ROW_ALT = "F0F2F8"
_COLOR_ROW_EVEN = "FFFFFF"
_COLOR_TEXT = "1A1F4D"
_COLOR_BORDER = "C8CDDF"

_FMT_DATE = "DD.MM.YYYY"
_FMT_AMOUNT = "#,##0.00"
_FMT_TEXT = "@"

_FONT_HEADER = Font(name="Calibri", bold=True, color=_COLOR_HEADER_TEXT, size=11)
_FONT_BODY = Font(name="Calibri", color=_COLOR_TEXT, size=11)

_FILL_HEADER = PatternFill("solid", fgColor=_COLOR_NAVY_HEADER)
_FILL_ROW_ALT = PatternFill("solid", fgColor=_COLOR_ROW_ALT)
_FILL_ROW_EVEN = PatternFill("solid", fgColor=_COLOR_ROW_EVEN)

_ALIGN_HEADER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_ALIGN_TEXT = Alignment(horizontal="left", vertical="top", wrap_text=True)
_ALIGN_DATE = Alignment(horizontal="center", vertical="center")
_ALIGN_AMOUNT = Alignment(horizontal="right", vertical="center")
_ALIGN_CENTER = Alignment(horizontal="center", vertical="center")

_THIN_BORDER = Border(
    left=Side(style="thin", color=_COLOR_BORDER),
    right=Side(style="thin", color=_COLOR_BORDER),
    top=Side(style="thin", color=_COLOR_BORDER),
    bottom=Side(style="thin", color=_COLOR_BORDER),
)

# Official column order (keep `Adress` spelling for Finance compatibility).
HEADERS = [
    "Invoice Date",
    "Name of Company",
    "Adress of Company",
    "Invoice Number",
    "Amount",
    "Debt",
    "Account Details",
    "Internal Note/Description",
    "Client / Employee Related",
    "paid at (Date)",
    "paid by",
    "Fixed/Not fixed",
    "Category",
]

_COLUMN_WIDTHS = {
    1: 13,
    2: 32,
    3: 34,
    4: 22,
    5: 14,
    6: 12,
    7: 38,
    8: 42,
    9: 24,
    10: 14,
    11: 18,
    12: 16,
    13: 22,
}

_COL_DATES = frozenset({1, 10})
_COL_AMOUNTS = frozenset({5, 6})
_COL_TEXT_IDS = frozenset({4})
_COL_WRAP = frozenset({2, 3, 7, 8, 9, 11, 12, 13})


def _cell_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell_amount(value: Decimal | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _invoice_row(inv: InvoiceResponse) -> list:
    return [
        inv.invoice_date,
        _cell_text(inv.name_of_company),
        _cell_text(inv.address_of_company),
        _cell_text(inv.invoice_number),
        _cell_amount(inv.amount),
        _cell_amount(inv.debt),
        _cell_text(inv.account_details),
        _cell_text(inv.internal_note_description),
        _cell_text(inv.client_employee_related),
        inv.paid_at_date,
        _cell_text(inv.paid_by),
        _cell_text(inv.fixed_status),
        _cell_text(inv.category),
    ]


def _apply_cell_format(cell, *, col_idx: int, is_header: bool, row_fill: PatternFill) -> None:
    cell.border = _THIN_BORDER
    cell.fill = _FILL_HEADER if is_header else row_fill

    if is_header:
        cell.font = _FONT_HEADER
        cell.alignment = _ALIGN_HEADER
        return

    cell.font = _FONT_BODY
    if col_idx in _COL_DATES:
        cell.number_format = _FMT_DATE
        cell.alignment = _ALIGN_DATE
    elif col_idx in _COL_AMOUNTS:
        cell.number_format = _FMT_AMOUNT
        cell.alignment = _ALIGN_AMOUNT
    elif col_idx in _COL_TEXT_IDS:
        cell.number_format = _FMT_TEXT
        cell.alignment = _ALIGN_CENTER
        if cell.value is not None:
            cell.value = str(cell.value)
    elif col_idx in _COL_WRAP:
        cell.alignment = _ALIGN_TEXT
    else:
        cell.alignment = _ALIGN_CENTER


def _style_worksheet(ws: Worksheet, *, last_row: int) -> None:
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"
    if last_row >= 1:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}{last_row}"

    ws.row_dimensions[1].height = 36

    for col_idx, width in _COLUMN_WIDTHS.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    for row_idx in range(1, last_row + 1):
        is_header = row_idx == 1
        row_fill = _FILL_ROW_EVEN if is_header or row_idx % 2 == 0 else _FILL_ROW_ALT
        if not is_header and row_idx > 1:
            ws.row_dimensions[row_idx].height = 18

        for col_idx in range(1, len(HEADERS) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            _apply_cell_format(
                cell,
                col_idx=col_idx,
                is_header=is_header,
                row_fill=row_fill,
            )


class ExcelService:
    def write_purchase_invoices_workbook(
        self, invoices: list[InvoiceResponse]
    ) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "Purchase Invoices"
        ws.append(HEADERS)

        for inv in invoices:
            ws.append(_invoice_row(inv))

        last_row = max(1, len(invoices) + 1)
        _style_worksheet(ws, last_row=last_row)

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
