"""Tests for `utils.bank_excel_parser._parse_date`.

These guard the parsing fix for the issue where ProCredit / Kreissparkasse
Excel exports stored every `transaction_date` as NULL because the date column
contained either Excel serial numbers or unsupported string formats.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from core.exceptions import ExcelParseError
from utils.bank_excel_parser import (
    ParsedBankRow,
    _parse_date,
    _excel_serial_to_date,
    dedupe_parsed_rows,
    extract_statement_date,
    statement_id_from_date,
)


# ── Pass-through for native datetime/date objects ─────────────────────────────


def test_datetime_passthrough():
    assert _parse_date(datetime(2026, 2, 25, 14, 30)) == date(2026, 2, 25)


def test_date_passthrough():
    assert _parse_date(date(2026, 2, 25)) == date(2026, 2, 25)


# ── String formats: every shape we've seen in real exports ────────────────────


@pytest.mark.parametrize(
    "value,expected",
    [
        ("25.02.2026", date(2026, 2, 25)),
        ("25/02/2026", date(2026, 2, 25)),
        ("2026-02-25", date(2026, 2, 25)),
        ("25-02-2026", date(2026, 2, 25)),  # dashed EU
        ("25.02.26", date(2026, 2, 25)),    # 2-digit year
        ("25/02/26", date(2026, 2, 25)),
        ("2026/02/25", date(2026, 2, 25)),
        ("25.02.2026 12:30", date(2026, 2, 25)),       # date+time
        ("25.02.2026 12:30:45", date(2026, 2, 25)),
        ("2026-02-25 12:30:45", date(2026, 2, 25)),
        ("2026-02-25T12:30:45", date(2026, 2, 25)),    # ISO 8601
        ("25.02.2026 Mo", date(2026, 2, 25)),          # trailing weekday — falls back to head-split
        ("'26.02.2026", date(2026, 2, 26)),           # Excel text-date leading apostrophe
        ("26,02,2026", date(2026, 2, 26)),             # comma separators
        ("46078", date(2026, 2, 25)),                  # serial as text (General column)
    ],
)
def test_string_formats(value, expected):
    assert _parse_date(value) == expected


# ── Excel serial numbers (what you get when the cell is formatted "General") ──


def test_excel_serial_int():
    # 25 Feb 2026 in Excel serial = 46078 (days since 1899-12-30).
    assert _parse_date(46078) == date(2026, 2, 25)


def test_excel_serial_float():
    assert _parse_date(46078.5) == date(2026, 2, 25)


def test_excel_serial_known_anchor():
    # 1 Jan 1900 → serial 2 (Lotus 1900 leap-year bug compatibility).
    assert _excel_serial_to_date(2) == date(1900, 1, 1)


# ── Defensive: invalid / blank / nonsense returns None instead of crashing ────


@pytest.mark.parametrize("value", [None, "", "   ", "not a date", 0, -1, True, False])
def test_invalid_returns_none(value):
    assert _parse_date(value) is None


def test_out_of_range_serial_returns_none():
    # Far-future serial (year > 4000) is almost certainly bad input, not data.
    assert _parse_date(999999) is None


def _sample_row(
    *,
    txn_date: date | None = date(2026, 2, 25),
    debited: str | None = "100.00",
    credited: str | None = None,
    comment: str = "Invoice 123",
    txn_type: str | None = "Transfer",
) -> ParsedBankRow:
    return ParsedBankRow(
        transaction_date=txn_date,
        debited_amount=Decimal(debited) if debited else None,
        credited_amount=Decimal(credited) if credited else None,
        transaction_type=txn_type,
        comment=comment,
        detected_invoice_numbers=["123"],
    )


def test_dedupe_parsed_rows_removes_duplicates():
    rows = [
        _sample_row(),
        _sample_row(),
        _sample_row(comment="Different"),
    ]
    unique, skipped = dedupe_parsed_rows(rows)
    assert len(unique) == 2
    assert skipped == 1


def test_extract_statement_date_from_filename():
    rows = [_sample_row(txn_date=date(2026, 2, 1))]
    assert extract_statement_date("statement_20260228.xlsx", rows) == date(2026, 2, 28)


def test_extract_statement_date_from_transactions_when_filename_has_no_date():
    rows = [
        _sample_row(txn_date=date(2026, 2, 10)),
        _sample_row(txn_date=date(2026, 2, 28)),
    ]
    assert extract_statement_date("procredit_export.xlsx", rows) == date(2026, 2, 28)


def test_extract_statement_date_raises_when_unknown():
    with pytest.raises(ExcelParseError):
        extract_statement_date("export.xlsx", [_sample_row(txn_date=None)])


def test_statement_id_from_date():
    assert statement_id_from_date(date(2026, 2, 28)) == 20260228
