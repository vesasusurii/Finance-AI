from pathlib import Path

from services.verification_email_template import (
    LOGO_CID,
    build_verification_email_html,
    build_verification_email_message,
    build_verification_email_plain,
)


def test_verification_email_plain_expires_in_minutes():
    body = build_verification_email_plain("123456", ttl_minutes=10)
    assert "123456" in body
    assert "10 minutes" in body
    assert "days" not in body


def test_verification_email_html_white_theme_and_logo_cid():
    html = build_verification_email_html(
        "654321",
        ttl_minutes=10,
        logo_src=f"cid:{LOGO_CID}",
    )
    assert "6 5 4 3 2 1" in html
    assert "#FFFFFF" in html
    assert "10 minutes" in html
    assert f"cid:{LOGO_CID}" in html


def test_build_verification_email_message_includes_inline_logo():
    msg = build_verification_email_message(
        from_addr="no-reply@borek.com",
        to_addr="user@example.com",
        subject="Test",
        code="112233",
        ttl_minutes=10,
    )
    logo_path = (
        Path(__file__).resolve().parents[1]
        / "assets"
        / "branding"
        / "FinAI.png"
    )
    if not logo_path.is_file():
        return
    parts = list(msg.walk())
    assert any(part.get_content_type() == "image/png" for part in parts)
