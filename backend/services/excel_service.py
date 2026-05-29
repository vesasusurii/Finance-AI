"""Period report Excel export (openpyxl)."""

from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from core.debug_logger import debug_trace, get_logger
from schemas.report import PeriodReportResponse

logger = get_logger(__name__)

_COLOR_NAVY_HEADER = "0D123F"
_COLOR_HEADER_TEXT = "FFFFFF"
_COLOR_ROW_ALT = "F0F2F8"
_COLOR_ROW_EVEN = "FFFFFF"
_COLOR_TEXT = "1A1F4D"
_COLOR_BORDER = "C8CDDF"

_FMT_DATE = "DD.MM.YYYY"
_FMT_AMOUNT = "#,##0.00"

_FONT_HEADER = Font(name="Calibri", bold=True, color=_COLOR_HEADER_TEXT, size=11)
_FONT_BODY = Font(name="Calibri", color=_COLOR_TEXT, size=11)

_FILL_HEADER = PatternFill("solid", fgColor=_COLOR_NAVY_HEADER)
_FILL_ROW_ALT = PatternFill("solid", fgColor=_COLOR_ROW_ALT)
_FILL_ROW_EVEN = PatternFill("solid", fgColor=_COLOR_ROW_EVEN)

_ALIGN_HEADER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_ALIGN_DATE = Alignment(horizontal="center", vertical="center")
_ALIGN_AMOUNT = Alignment(horizontal="right", vertical="center")
_ALIGN_CENTER = Alignment(horizontal="center", vertical="center")

_THIN_BORDER = Border(
    left=Side(style="thin", color=_COLOR_BORDER),
    right=Side(style="thin", color=_COLOR_BORDER),
    top=Side(style="thin", color=_COLOR_BORDER),
    bottom=Side(style="thin", color=_COLOR_BORDER),
)

_COL_DATES = frozenset({2, 3})
_COL_AMOUNTS = frozenset({2, 3})


def _apply_cell_format(cell, *, is_header: bool, row_fill: PatternFill) -> None:
    cell.border = _THIN_BORDER
    cell.fill = _FILL_HEADER if is_header else row_fill
    cell.font = _FONT_HEADER if is_header else _FONT_BODY
    cell.alignment = _ALIGN_HEADER if is_header else _ALIGN_CENTER


class ExcelService:
    @debug_trace
    def write_period_report_workbook(self, report: PeriodReportResponse) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "Summary"

        summary_rows = [
            ("Period", report.period_label),
            ("Start date", report.start_date),
            ("End date", report.end_date),
            ("Total invoices", report.total_invoices),
            ("Total amount", float(report.total_amount)),
            ("Paid invoices", report.paid_invoices),
            ("Unpaid invoices", report.unpaid_invoices),
            ("Total paid amount", float(report.total_paid_amount)),
            ("Matched invoices", report.matched_invoices),
            ("Unmatched invoices", report.unmatched_invoices),
            ("Needs review (invoices)", report.needs_review),
            ("Bank transactions", report.bank_transactions),
            ("Bank matched", report.bank_matched),
            ("Bank needs review", report.bank_needs_review),
        ]

        ws.append(["Metric", "Value"])
        for label, value in summary_rows:
            ws.append([label, value])

        cat_ws = wb.create_sheet("By category")
        cat_ws.append(["Category", "Count", "Total amount"])
        for row in report.by_category:
            cat_ws.append([row.category, row.count, float(row.total_amount)])

        for sheet in (ws, cat_ws):
            sheet.sheet_view.showGridLines = False
            sheet.column_dimensions["A"].width = 28
            sheet.column_dimensions["B"].width = 18
            if sheet.title == "By category":
                sheet.column_dimensions["C"].width = 16
            for row_idx in range(1, sheet.max_row + 1):
                is_header = row_idx == 1
                row_fill = (
                    _FILL_ROW_EVEN if is_header or row_idx % 2 == 0 else _FILL_ROW_ALT
                )
                for col_idx in range(1, sheet.max_column + 1):
                    cell = sheet.cell(row=row_idx, column=col_idx)
                    _apply_cell_format(
                        cell,
                        is_header=is_header,
                        row_fill=row_fill,
                    )
                    if not is_header and col_idx in _COL_DATES and isinstance(
                        cell.value, date
                    ):
                        cell.number_format = _FMT_DATE
                        cell.alignment = _ALIGN_DATE
                    if not is_header and col_idx in _COL_AMOUNTS and isinstance(
                        cell.value, (int, float)
                    ):
                        cell.number_format = _FMT_AMOUNT
                        cell.alignment = _ALIGN_AMOUNT

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
