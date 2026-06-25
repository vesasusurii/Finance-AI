"""Branded HTML + plain-text templates for password reset (Borek Finance)."""

from __future__ import annotations

from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from services.verification_email_template import LOGO_CID, LOGO_FILENAME, _logo_path

_BG = "#FFFFFF"
_SURFACE = "#F4F5F8"
_BORDER = "#E4E7EE"
_TEXT = "#0D123F"
_TEXT_MUTED = "#5C6378"
_TEXT_SOFT = "#8B92A5"
_ACCENT = "#DB3714"


def _expiry_label(ttl_minutes: int) -> str:
    if ttl_minutes == 1:
        return "1 minute"
    return f"{ttl_minutes} minutes"


def build_password_reset_email_plain(
    reset_url: str,
    *,
    ttl_minutes: int = 60,
) -> str:
    expiry = _expiry_label(ttl_minutes)
    return "\n".join(
        [
            "Borek Finance",
            "",
            "Reset your password",
            "",
            f"Open this link to choose a new password: {reset_url}",
            "",
            f"This link expires in {expiry}.",
            "",
            "If you did not request this, you can ignore this email.",
        ]
    )


def build_password_reset_email_html(
    reset_url: str,
    *,
    ttl_minutes: int = 60,
    logo_src: str | None = None,
) -> str:
    expiry = _expiry_label(ttl_minutes)
    if logo_src:
        logo_block = f"""<img src="{logo_src}" alt="Borek Finance" width="168"
                   style="display:block;height:auto;max-width:168px;border:0;margin:0 auto;" />"""
    else:
        logo_block = f"""<p style="margin:0;font-family:Arial,Helvetica,sans-serif;
                        font-size:18px;font-weight:700;color:{_TEXT};">
                Borek Finance
              </p>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light" />
  <title>Reset your Borek Finance password</title>
</head>
<body style="margin:0;padding:0;background-color:{_BG};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
         style="background-color:{_BG};border-collapse:collapse;">
    <tr>
      <td align="center" style="padding:40px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
               style="max-width:520px;border-collapse:collapse;">
          <tr>
            <td align="center" style="padding:0 0 28px 0;">
              {logo_block}
            </td>
          </tr>
          <tr>
            <td style="background-color:{_SURFACE};border:1px solid {_BORDER};
                       border-radius:16px;padding:36px 32px;">
              <p style="margin:0 0 8px 0;font-family:Arial,Helvetica,sans-serif;
                        font-size:11px;font-weight:800;letter-spacing:0.12em;
                        text-transform:uppercase;color:{_ACCENT};text-align:center;">
                Password reset
              </p>
              <h1 style="margin:0 0 12px 0;font-family:Arial,Helvetica,sans-serif;
                         font-size:24px;font-weight:700;line-height:1.3;
                         letter-spacing:-0.01em;color:{_TEXT};text-align:center;">
                Reset your password
              </h1>
              <p style="margin:0 0 28px 0;font-family:Arial,Helvetica,sans-serif;
                        font-size:15px;line-height:1.6;color:{_TEXT_MUTED};text-align:center;">
                Use the button below to choose a new password for your Borek Finance account.
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                     style="border-collapse:collapse;">
                <tr>
                  <td align="center" style="padding:0 0 24px 0;">
                    <a href="{reset_url}"
                       style="display:inline-block;padding:14px 28px;background-color:{_ACCENT};
                              color:#FFFFFF;font-family:Arial,Helvetica,sans-serif;
                              font-size:15px;font-weight:700;text-decoration:none;
                              border-radius:9999px;">
                      Reset password
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 8px 0;font-family:Arial,Helvetica,sans-serif;
                        font-size:14px;line-height:1.55;color:{_TEXT_MUTED};text-align:center;">
                This link expires in <strong style="color:{_TEXT};">{expiry}</strong>.
              </p>
              <p style="margin:0 0 24px 0;font-family:Arial,Helvetica,sans-serif;
                        font-size:13px;line-height:1.55;color:{_TEXT_SOFT};text-align:center;">
                For your security, do not share this link with anyone.
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
                     style="border-collapse:collapse;">
                <tr>
                  <td style="border-top:1px solid {_BORDER};padding-top:20px;">
                    <p style="margin:0;font-family:Arial,Helvetica,sans-serif;
                              font-size:12px;line-height:1.55;color:{_TEXT_SOFT};text-align:center;">
                      If you did not request a password reset, you can ignore this email.
                      Your password will remain unchanged.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 8px 0;text-align:center;">
              <p style="margin:0;font-family:Arial,Helvetica,sans-serif;
                        font-size:11px;line-height:1.5;color:{_TEXT_SOFT};">
                Borek Solutions Group
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_password_reset_email_message(
    *,
    from_addr: str,
    to_addr: str,
    subject: str,
    reset_url: str,
    ttl_minutes: int,
) -> MIMEMultipart:
    plain = build_password_reset_email_plain(reset_url, ttl_minutes=ttl_minutes)
    logo_path = _logo_path()
    logo_src = f"cid:{LOGO_CID}" if logo_path is not None else None
    html = build_password_reset_email_html(
        reset_url, ttl_minutes=ttl_minutes, logo_src=logo_src
    )

    root = MIMEMultipart("related")
    root["Subject"] = subject
    root["From"] = from_addr
    root["To"] = to_addr

    alternative = MIMEMultipart("alternative")
    root.attach(alternative)
    alternative.attach(MIMEText(plain, "plain", "utf-8"))
    alternative.attach(MIMEText(html, "html", "utf-8"))

    if logo_path is not None:
        with logo_path.open("rb") as logo_file:
            image = MIMEImage(logo_file.read(), _subtype="png")
        image.add_header("Content-ID", f"<{LOGO_CID}>")
        image.add_header("Content-Disposition", "inline", filename=LOGO_FILENAME)
        root.attach(image)

    return root
