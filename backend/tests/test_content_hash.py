"""Tests for file-hash deduplication helpers."""

from datetime import date

from utils.content_hash import sha256_hex
from utils.bank_excel_parser import _parse_date


def test_sha256_hex_stable():
    data = b"same invoice bytes"
    assert sha256_hex(data) == sha256_hex(data)
    assert sha256_hex(data) != sha256_hex(b"other")


def test_parse_date_still_works():
    assert _parse_date("26.02.2026") == date(2026, 2, 26)
