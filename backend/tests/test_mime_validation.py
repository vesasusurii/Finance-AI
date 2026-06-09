from utils.mime_validation import validate_content_matches_mime


def test_pdf_magic():
    assert validate_content_matches_mime(b"%PDF-1.4 content", "application/pdf")


def test_jpeg_magic():
    assert validate_content_matches_mime(b"\xff\xd8\xff\xe0", "image/jpeg")


def test_png_magic():
    header = b"\x89PNG\r\n\x1a\n"
    assert validate_content_matches_mime(header + b"data", "image/png")


def test_mismatch_rejected():
    assert not validate_content_matches_mime(b"not a pdf", "application/pdf")
