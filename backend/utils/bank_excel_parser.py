"""Parse ProCredit-style bank statement Excel files (doc 10)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any

from core.exceptions import ExcelParseError
from utils.invoice_number_parser import extract_invoice_numbers

STOP_MARKERS = ("përmbledhje", "summary", "fsdk", "deposit insurance")
HEADER_SCAN_ROWS = 15

REQUIRED_HEADERS = {
    "date": ("data", "date"),
    "comment": ("komenti", "comment"),
}


@dataclass
class ParsedBankRow:
    transaction_date: date | None
    debited_amount: Decimal | None
    credited_amount: Decimal | None
    transaction_type: str | None
    comment: str | None
    detected_invoice_numbers: list[str]


def _normalize_header(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _cell_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _parse_amount(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _is_summary_or_footer(row_values: list[Any]) -> bool:
    combined = " ".join(_normalize_header(v) for v in row_values if v is not None)
    return any(marker in combined for marker in STOP_MARKERS)


def _is_empty_transaction(row: dict[str, Any]) -> bool:
    return (
        row.get("transaction_date") is None
        and row.get("debited_amount") is None
        and row.get("credited_amount") is None
        and not row.get("comment")
    )


def _map_columns(header_row: list[Any]) -> dict[str, int]:
    col_map: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        h = _normalize_header(cell)
        if not h:
            continue
        if any(k in h for k in REQUIRED_HEADERS["date"]) and "date" not in col_map:
            col_map["date"] = idx
        if any(k in h for k in REQUIRED_HEADERS["comment"]) and "comment" not in col_map:
            col_map["comment"] = idx
        if "debit" in h and "debited" not in col_map:
            col_map["debited"] = idx
        if "credit" in h and "credited" not in col_map:
            col_map["credited"] = idx
        if ("tipi" in h or "type" in h) and "transaction_type" not in col_map:
            col_map["transaction_type"] = idx
    return col_map


def _find_header_row(rows: list[list[Any]]) -> tuple[int, dict[str, int]]:
    limit = min(HEADER_SCAN_ROWS, len(rows))
    for i in range(limit):
        row = rows[i]
        col_map = _map_columns(row)
        if "date" in col_map and "comment" in col_map:
            return i, col_map
    raise ExcelParseError(
        "Could not find bank statement headers (Data / Date, Komenti / Comment)."
    )


def _parse_row(row: list[Any], col_map: dict[str, int]) -> dict[str, Any]:
    def get(key: str) -> Any:
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    comment = _cell_str(get("comment"))
    return {
        "transaction_date": _parse_date(get("date")),
        "debited_amount": _parse_amount(get("debited")),
        "credited_amount": _parse_amount(get("credited")),
        "transaction_type": _cell_str(get("transaction_type")),
        "comment": comment,
        "detected_invoice_numbers": extract_invoice_numbers(comment),
    }


def _load_rows_xlsx(data: bytes) -> list[list[Any]]:
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        wb.close()
        raise ExcelParseError("Excel workbook has no active sheet.")
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    return rows


def _load_rows_xls(data: bytes) -> list[list[Any]]:
    import xlrd

    book = xlrd.open_workbook(file_contents=data)
    sheet = book.sheet_by_index(0)
    return [list(sheet.row_values(r)) for r in range(sheet.nrows)]


def parse_bank_statement_excel(
    data: bytes,
    filename: str,
) -> list[ParsedBankRow]:
    ext = Path(filename).suffix.lower()
    if ext == ".xls":
        rows = _load_rows_xls(data)
    elif ext in (".xlsx", ".xlsm"):
        rows = _load_rows_xlsx(data)
    else:
        raise ExcelParseError("Unsupported file type. Upload .xlsx or .xls.")

    if not rows:
        raise ExcelParseError("No data rows found in the file.")

    header_idx, col_map = _find_header_row(rows)
    parsed: list[ParsedBankRow] = []

    for row in rows[header_idx + 1 :]:
        if _is_summary_or_footer(row):
            break
        row_dict = _parse_row(row, col_map)
        if _is_empty_transaction(row_dict):
            continue
        parsed.append(
            ParsedBankRow(
                transaction_date=row_dict["transaction_date"],
                debited_amount=row_dict["debited_amount"],
                credited_amount=row_dict["credited_amount"],
                transaction_type=row_dict["transaction_type"],
                comment=row_dict["comment"],
                detected_invoice_numbers=row_dict["detected_invoice_numbers"],
            )
        )

    if not parsed:
        raise ExcelParseError("No transaction rows found.")

    return parsed
