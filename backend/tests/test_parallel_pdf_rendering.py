"""Parallel PDF page rendering — order, fallback, and config."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from config import settings
from services.ocr import pdf_reader


def _mock_pdf_document(page_count: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pdf_reader.pdfium,
        "PdfDocument",
        MagicMock(return_value=MagicMock(__len__=lambda _: page_count)),
    )


def _fake_page(index: int, *, delay: float = 0.0) -> tuple[int, bytes, str]:
    if delay:
        time.sleep(delay)
    return index, f"page-{index}".encode(), "image/jpeg"


def test_parallel_preserves_page_order(monkeypatch: pytest.MonkeyPatch):
    _mock_pdf_document(3, monkeypatch)

    def render_page(content, index, **kwargs):
        # Later pages finish first to prove ordering is by index, not completion.
        delay = 0.02 if index == 0 else 0.0
        return _fake_page(index, delay=delay)

    monkeypatch.setattr(pdf_reader, "_render_page_at_index", render_page)
    result = pdf_reader.render_pdf_pages(
        b"pdf-bytes",
        parallel=True,
        max_workers=3,
    )
    assert result.render_strategy == "parallel"
    assert result.rendered_page_count == 3
    assert [img[0].decode() for img in result.images] == [
        "page-0",
        "page-1",
        "page-2",
    ]
    assert result.render_parallel_ms is not None


def test_parallel_fallback_to_sequential(monkeypatch: pytest.MonkeyPatch):
    _mock_pdf_document(2, monkeypatch)
    sequential_calls: list[int] = []

    def failing_parallel(*args, **kwargs):
        raise RuntimeError("parallel boom")

    def sequential(content, page_indices, **kwargs):
        sequential_calls.append(len(page_indices))
        return [(index, (b"seq", "image/jpeg")) for index in page_indices]

    monkeypatch.setattr(pdf_reader, "_render_parallel_indices", failing_parallel)
    monkeypatch.setattr(pdf_reader, "_render_sequential_indices", sequential)

    result = pdf_reader.render_pdf_pages(b"pdf-bytes", parallel=True)
    assert result.render_strategy == "sequential"
    assert sequential_calls == [2]
    assert len(result.images) == 2
    assert result.page_numbers == [1, 2]
    assert result.render_parallel_ms is None


def test_config_flag_disables_parallel(monkeypatch: pytest.MonkeyPatch):
    _mock_pdf_document(3, monkeypatch)
    monkeypatch.setattr(settings, "openai_parallel_pdf_rendering", False)
    parallel_called = False

    def parallel(*args, **kwargs):
        nonlocal parallel_called
        parallel_called = True
        return [(b"p", "image/jpeg")] * 2, 1.0

    monkeypatch.setattr(pdf_reader, "_render_parallel_indices", parallel)
    monkeypatch.setattr(
        pdf_reader,
        "_render_sequential_indices",
        lambda content, page_indices, **kwargs: [
            (index, (b"s", "image/jpeg")) for index in page_indices
        ],
    )

    result = pdf_reader.render_pdf_pages(b"pdf-bytes")
    assert parallel_called is False
    assert result.render_strategy == "sequential"
    assert result.images[0][0] == b"s"


def test_single_page_uses_sequential(monkeypatch: pytest.MonkeyPatch):
    _mock_pdf_document(1, monkeypatch)
    parallel_called = False

    def parallel(*args, **kwargs):
        nonlocal parallel_called
        parallel_called = True
        return [(b"p", "image/jpeg")], 1.0

    monkeypatch.setattr(pdf_reader, "_render_parallel_indices", parallel)
    monkeypatch.setattr(
        pdf_reader,
        "_render_sequential_indices",
        lambda content, page_indices, **kwargs: [
            (0, (b"one", "image/jpeg")),
        ],
    )

    result = pdf_reader.render_pdf_pages(b"pdf-bytes", parallel=True)
    assert parallel_called is False
    assert result.render_strategy == "sequential"
    assert result.rendered_page_count == 1


def test_selective_page_indices_preserve_order(monkeypatch: pytest.MonkeyPatch):
    _mock_pdf_document(4, monkeypatch)

    def render_page(content, index, **kwargs):
        return index, f"page-{index}".encode(), "image/jpeg"

    monkeypatch.setattr(pdf_reader, "_render_page_at_index", render_page)
    result = pdf_reader.render_pdf_pages(
        b"pdf-bytes",
        page_indices=[0, 2, 3],
        page_scales={1: 1.5, 3: 1.0, 4: 1.5},
        parallel=True,
        max_workers=3,
    )
    assert result.page_numbers == [1, 3, 4]
    assert [img[0].decode() for img in result.images] == ["page-0", "page-2", "page-3"]


def test_render_pdf_pages_as_images_wrapper(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        pdf_reader,
        "render_pdf_pages",
        lambda *args, **kwargs: pdf_reader.PdfRenderResult(
            images=[(b"jpeg", "image/jpeg")],
            page_numbers=[1],
            render_strategy="sequential",
            render_ms=5.0,
            render_parallel_ms=None,
            rendered_page_count=1,
        ),
    )
    images = pdf_reader.render_pdf_pages_as_images(b"pdf")
    assert images == [(b"jpeg", "image/jpeg")]
