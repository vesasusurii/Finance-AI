"""Post-extraction validation and normalisation (DOCS/8 § Step 4)."""

from __future__ import annotations

import re
from datetime import datetime

from schemas.invoice import ExtractionResult
from utils.normalization import is_tax_or_client_id, normalize_invoice_number

CONFIDENCE_AUTO_OK = 0.90
CONFIDENCE_REVIEW = 0.70

# Tax / registration IDs commonly misread as invoice numbers
_TAX_ID_PATTERN = re.compile(r"^(811\d{6}|330\d{6,})$")
_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")

# Amounts that are suspiciously round and very small (likely a sub-total or tax line)
_SUSPICIOUS_ROUND_AMOUNT = re.compile(r"^\d+\.00$")

VALID_CATEGORIES = {
    "Professional services",
    "Utilities",
    "Software",
    "IT / Hardware",
    "Office",
    "Travel",
    "Other",
}


class AIValidationService:
    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def determine_review_status(self, result: ExtractionResult) -> str:
        if result.confidence_score >= CONFIDENCE_AUTO_OK and not result.needs_review:
            return "pending"
        return "needs_review"

    def validate_required_fields(self, result: ExtractionResult) -> list[str]:
        missing: list[str] = []
        if not result.invoice_number:
            missing.append("invoice_number")
        if result.amount is None:
            missing.append("amount")
        if not result.name_of_company:
            missing.append("name_of_company")
        if not result.invoice_date:
            missing.append("invoice_date")
        return missing

    def detect_suspicious_values(self, result: ExtractionResult) -> list[str]:
        """
        Heuristic checks for values that look plausible but are likely wrong.
        Returns a list of field names that look suspicious.
        """
        issues: list[str] = []

        # Invoice number looks like a year only (e.g. "2026")
        if result.invoice_number and re.fullmatch(r"20\d{2}", result.invoice_number.strip()):
            issues.append("invoice_number_is_year")

        # Amount is zero or negative
        if result.amount is not None and result.amount <= 0:
            issues.append("amount_not_positive")

        # Invoice date is in the future by more than 90 days (likely parsing error)
        if result.invoice_date:
            try:
                dt = datetime.strptime(result.invoice_date, "%Y-%m-%d")
                days_ahead = (dt - datetime.now()).days
                if days_ahead > 90:
                    issues.append("invoice_date_far_future")
            except ValueError:
                issues.append("invoice_date_unparseable")

        # Currency is not a known ISO code
        if result.currency and len(result.currency) != 3:
            issues.append("currency_not_iso")

        # Category is not from the allowed set
        if result.category and result.category not in VALID_CATEGORIES:
            issues.append("category_invalid")

        return issues

    def sanitize_and_validate(self, result: ExtractionResult) -> ExtractionResult:
        """Normalise all fields and apply code-level review rules after LLM parse."""
        data = result.model_dump()

        data["invoice_number"] = self._clean_invoice_number(data.get("invoice_number"))
        data["amount"] = self._normalize_amount(data.get("amount"))
        data["currency"] = self._normalize_currency(data.get("currency"))
        data["invoice_date"] = self._normalize_date(data.get("invoice_date"))
        data["category"] = self._normalize_category(data.get("category"))
        data["confidence_score"] = self._clamp_confidence(data.get("confidence_score", 0.0))
        data["name_of_company"] = self._clean_text(data.get("name_of_company"))
        data["address_of_company"] = self._clean_text(data.get("address_of_company"))
        data["account_details"] = self._clean_text(data.get("account_details"))
        data["internal_note_description"] = self._clean_text(data.get("internal_note_description"))
        data["client_employee_related"] = self._clean_text(data.get("client_employee_related"))

        if self._invoice_number_is_tax_id(data.get("invoice_number")):
            data["invoice_number"] = None

        data["needs_review"] = bool(data.get("needs_review"))
        data = self._apply_review_rules(data)

        return ExtractionResult.model_validate(data)

    # ─────────────────────────────────────────────────────────────────────
    # Field normalisers
    # ─────────────────────────────────────────────────────────────────────

    def _clean_text(self, raw: str | None) -> str | None:
        if not raw:
            return None
        cleaned = _ZERO_WIDTH.sub("", str(raw)).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned if cleaned else None

    def _clean_invoice_number(self, raw: str | None) -> str | None:
        if not raw:
            return None
        cleaned = _ZERO_WIDTH.sub("", str(raw)).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned:
            return None
        # Reject if normalization identifies it as a tax/client ID
        compact = re.sub(r"[^A-Z0-9]", "", cleaned.upper())
        if is_tax_or_client_id(compact):
            return None
        if normalize_invoice_number(cleaned) is None and is_tax_or_client_id(compact):
            return None
        if _TAX_ID_PATTERN.match(re.sub(r"[^0-9]", "", cleaned)):
            return None
        # Reject pure-year values (e.g. "2025", "2026")
        if re.fullmatch(r"20\d{2}", cleaned):
            return None
        return cleaned

    def _invoice_number_is_tax_id(self, invoice_number: str | None) -> bool:
        if not invoice_number:
            return False
        compact = re.sub(r"[^A-Z0-9]", "", invoice_number.upper())
        if is_tax_or_client_id(compact):
            return True
        digits_only = re.sub(r"[^0-9]", "", invoice_number)
        return bool(_TAX_ID_PATTERN.match(digits_only))

    def _normalize_amount(self, value: float | str | int | None) -> float | None:
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            amount = float(value)
            return amount if amount > 0 else None

        text = str(value).strip()
        if not text or text.lower() in ("null", "none", "n/a", "-"):
            return None

        # Strip currency symbols, spaces, and common noise
        text = re.sub(r"[€$£¥₹\s]", "", text)

        # Handle European format: 1.931,78 (thousands dot, decimal comma)
        if re.search(r",\d{2}$", text) and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif re.search(r",\d{2}$", text):
            # Could be European with no thousands separator: 1931,78
            text = text.replace(",", ".")
        else:
            # Remove any remaining commas (US thousands: 1,931.78)
            text = text.replace(",", "")

        try:
            amount = float(text)
        except ValueError:
            return None

        return amount if amount > 0 else None

    def _normalize_currency(self, raw: str | None) -> str | None:
        if not raw:
            return None
        # Strip anything that isn't a letter
        code = re.sub(r"[^A-Za-z]", "", str(raw)).upper()
        if len(code) == 3:
            return code
        aliases: dict[str, str] = {
            "EURO": "EUR",
            "EUROS": "EUR",
            "DOLLAR": "USD",
            "DOLLARS": "USD",
            "USDOLLAR": "USD",
            "POUND": "GBP",
            "POUNDS": "GBP",
            "FRANC": "CHF",
            "LEK": "ALL",
            "LEKE": "ALL",
        }
        return aliases.get(code)

    def _normalize_date(self, raw: str | None) -> str | None:
        if not raw:
            return None
        text = _ZERO_WIDTH.sub("", str(raw)).strip()
        if not text or text.lower() in ("null", "none", "n/a"):
            return None

        # Already ISO
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            try:
                datetime.strptime(text, "%Y-%m-%d")
                return text
            except ValueError:
                return None

        # Try all known date formats
        formats = (
            "%d.%m.%Y",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d-%b-%y",
            "%d-%b-%Y",
            "%d %b %Y",
            "%d %B %Y",
            "%Y/%m/%d",
            "%m/%d/%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d. %B %Y",
            "%d. %b %Y",
        )
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Last resort: try stripping ordinal suffixes (1st, 2nd, 3rd, 4th)
        cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text, flags=re.IGNORECASE)
        if cleaned != text:
            return self._normalize_date(cleaned)

        return None

    def _normalize_category(self, raw: str | None) -> str | None:
        if not raw:
            return None
        key = _ZERO_WIDTH.sub("", str(raw)).strip().lower()

        mapping: dict[str, str] = {
            "professional services": "Professional services",
            "professional service": "Professional services",
            "consulting": "Professional services",
            "legal": "Professional services",
            "accounting": "Professional services",
            "utilities": "Utilities",
            "utility": "Utilities",
            "electricity": "Utilities",
            "water": "Utilities",
            "telecom": "Utilities",
            "internet": "Utilities",
            "software": "Software",
            "saas": "Software",
            "subscription": "Software",
            "licence": "Software",
            "license": "Software",
            "it / hardware": "IT / Hardware",
            "it/hardware": "IT / Hardware",
            "hardware": "IT / Hardware",
            "it hardware": "IT / Hardware",
            "computer": "IT / Hardware",
            "equipment": "IT / Hardware",
            "office": "Office",
            "office supplies": "Office",
            "stationery": "Office",
            "travel": "Travel",
            "hotel": "Travel",
            "flight": "Travel",
            "transport": "Travel",
            "other": "Other",
        }

        # Exact match first
        if key in mapping:
            return mapping[key]

        # Substring match
        for label, canonical in mapping.items():
            if label in key:
                return canonical

        # Check if it's already a valid canonical value
        if raw.strip() in VALID_CATEGORIES:
            return raw.strip()

        return "Other"

    def _clamp_confidence(self, value: float) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, score))

    # ─────────────────────────────────────────────────────────────────────
    # Review rule engine
    # ─────────────────────────────────────────────────────────────────────

    def _apply_review_rules(self, data: dict) -> dict:
        missing = []
        if not data.get("invoice_number"):
            missing.append("invoice_number")
        if data.get("amount") is None:
            missing.append("amount")
        if not data.get("name_of_company"):
            missing.append("name_of_company")
        if not data.get("invoice_date"):
            missing.append("invoice_date")

        score = data.get("confidence_score", 0.0)

        if missing or score < CONFIDENCE_REVIEW:
            data["needs_review"] = True
            # Cap confidence to below auto-ok threshold when critical fields missing
            if score >= CONFIDENCE_AUTO_OK:
                data["confidence_score"] = min(score, CONFIDENCE_REVIEW - 0.01)

        # Zero/negative amounts are invalid
        if data.get("amount") is not None and data["amount"] <= 0:
            data["amount"] = None
            data["needs_review"] = True

        # Category must be from the allowed set
        if data.get("category") and data["category"] not in VALID_CATEGORIES:
            data["category"] = "Other"

        return data
