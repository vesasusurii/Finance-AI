"""Sanitize filenames for Content-Disposition headers."""

from urllib.parse import quote


def sanitize_download_filename(filename: str | None) -> str:
    if not filename:
        return "download"
    cleaned = filename.replace("\r", "").replace("\n", "").replace('"', "")
    return cleaned.strip() or "download"


def content_disposition_inline(filename: str | None) -> dict[str, str]:
    safe = sanitize_download_filename(filename)
    encoded = quote(safe)
    return {
        "Content-Disposition": (
            f'inline; filename="{safe}"; filename*=UTF-8\'\'{encoded}'
        )
    }
