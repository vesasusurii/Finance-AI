"""Tests for PDF byte inspection helpers."""

from utils.pdf_bytes import (
    find_pdf_start,
    has_pdf_eof_marker,
    inspect_pdf_bytes,
    looks_like_html_or_json,
    normalize_pdf_bytes,
)


def test_find_pdf_start_with_leading_whitespace() -> None:
    data = b"\r\n  %PDF-1.4 body %%EOF"
    assert find_pdf_start(data) == 4
    assert normalize_pdf_bytes(data).startswith(b"%PDF")


def test_inspect_pdf_bytes_reports_eof() -> None:
    data = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    report = inspect_pdf_bytes(data)
    assert report.starts_with_pdf
    assert report.has_eof_marker
    assert report.size == len(data)


def test_inspect_pdf_bytes_detects_missing_eof() -> None:
    data = b"%PDF-1.4 truncated"
    report = inspect_pdf_bytes(data)
    assert report.starts_with_pdf
    assert not report.has_eof_marker
    assert report.likely_truncated


def test_has_pdf_eof_marker_ignores_marker_outside_tail_window() -> None:
    """An %%EOF from an earlier PDF revision (incremental update) sitting deep
    in the file must not mask a truncation that cuts off before the real end."""
    early_eof = b"%PDF-1.4 body %%EOF"
    data = early_eof + b"y" * 50_000
    assert not has_pdf_eof_marker(data)


def test_has_pdf_eof_marker_finds_marker_within_tail_window() -> None:
    padding = b"x" * 100_000
    data = padding + b"%PDF-1.4 body %%EOF"
    assert has_pdf_eof_marker(data)


def test_looks_like_html_or_json() -> None:
    assert looks_like_html_or_json(b'{"error":"nope"}')
    assert looks_like_html_or_json(b"<!DOCTYPE html><html></html>")
    assert not looks_like_html_or_json(b"%PDF-1.4")
