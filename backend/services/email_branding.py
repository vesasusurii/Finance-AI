"""Shared branding assets for transactional emails."""

from __future__ import annotations

from pathlib import Path

LOGO_CID = "brand-logo"
LOGO_FILENAME = "FinAI.png"


def logo_path() -> Path | None:
    here = Path(__file__).resolve().parent
    for candidate in (
        here.parent / "assets" / "branding" / LOGO_FILENAME,
        here.parent.parent / "DOCS" / "branding" / LOGO_FILENAME,
    ):
        if candidate.is_file():
            return candidate
    return None
