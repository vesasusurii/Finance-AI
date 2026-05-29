import pytest

from core.document_types import validate_document_file, is_ocr_ready
from utils.file_storage import build_user_storage_path


def test_build_user_storage_path_scopes_by_user():
    path = build_user_storage_path(42, "invoice.pdf")
    assert path.startswith("users/42/")
    assert path.endswith("_invoice.pdf")


def test_validate_document_rejects_unknown_extension():
    with pytest.raises(ValueError, match="Unsupported"):
        validate_document_file("file.exe", "application/octet-stream", 100)


def test_validate_document_accepts_docx():
    mime = validate_document_file(
        "notes.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        1024,
    )
    assert not is_ocr_ready(mime)


def test_validate_document_accepts_pdf():
    mime = validate_document_file("scan.pdf", "application/pdf", 1024)
    assert is_ocr_ready(mime)
