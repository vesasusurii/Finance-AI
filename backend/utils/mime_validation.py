"""Magic-byte validation for uploaded invoice documents."""

_PDF_MAGIC = b"%PDF"
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def validate_content_matches_mime(content: bytes, mime: str) -> bool:
    if not content:
        return False
    if mime == "application/pdf":
        return content[:4] == _PDF_MAGIC
    if mime in ("image/jpeg", "image/jpg"):
        return content[:3] == _JPEG_MAGIC
    if mime == "image/png":
        return content[:8] == _PNG_MAGIC
    return False


def mime_validation_error(mime: str) -> str:
    return (
        f"File content does not match declared type ({mime}). "
        "Upload a valid PDF, JPEG, or PNG."
    )
