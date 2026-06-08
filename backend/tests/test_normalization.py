import re

import pytest

from utils.normalization import normalize_invoice_number, split_invoice_number

_INVALID_CHARS = re.compile(r"[/\-\s]")


def assert_formatted(value: str | None, expected: str) -> None:
    assert value == expected
    assert value is not None
    assert not _INVALID_CHARS.search(value)


def test_slash_serial_joined():
    assert_formatted(normalize_invoice_number("1/2026/0048"), "120260048")


def test_hyphens_removed():
    assert_formatted(normalize_invoice_number("ABC-2024-001"), "ABC2024001")


def test_whitespace_removed():
    assert_formatted(
        normalize_invoice_number("190053493 260100 B"),
        "190053493260100B",
    )


def test_water_ref_compact():
    assert_formatted(
        normalize_invoice_number("F-0720326-9020645-P"),
        "F07203269020645P",
    )


def test_mixed_separators():
    assert_formatted(normalize_invoice_number("  nr. 5945-698  "), "5945698")


def test_tax_id_rejected():
    assert normalize_invoice_number("811915159") is None


def test_year_rejected():
    assert normalize_invoice_number("2026") is None


def test_empty():
    assert normalize_invoice_number("") is None
    assert normalize_invoice_number(None) is None


def test_split_preserves_display():
    display, normalized = split_invoice_number("1/2026/0048")
    assert display == "1/2026/0048"
    assert normalized == "120260048"


def test_split_hyphenated_display():
    display, normalized = split_invoice_number("3807F638-0011")
    assert display == "3807F638-0011"
    assert normalized == "3807F6380011"


def test_split_plain_alnum_same():
    display, normalized = split_invoice_number("613260192")
    assert display == "613260192"
    assert normalized == "613260192"


def test_split_empty():
    assert split_invoice_number("") == (None, None)
    assert split_invoice_number(None) == (None, None)
