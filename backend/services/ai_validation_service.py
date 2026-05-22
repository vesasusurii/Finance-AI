"""Post-extraction validation and normalization (DOCS/8 § Step 4)."""

from __future__ import annotations

import re
from datetime import datetime

from schemas.invoice import ExtractionResult
from utils.normalization import is_tax_or_client_id, normalize_invoice_number

CONFIDENCE_AUTO_OK = 0.90
CONFIDENCE_REVIEW = 0.70

# Common tax / client IDs mistaken for invoice numbers (OCR doc + sample_02–04)
_TAX_ID_PATTERN = re.compile(r"^(811\d{6}|330\d{6,})$")

_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")


class AIValidationService:
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

    def sanitize_and_validate(self, result: ExtractionResult) -> ExtractionResult:
        """Normalize fields and apply code-level review rules after LLM parse."""
        data = result.model_dump()

        data["invoice_number"] = self._clean_invoice_number(data.get("invoice_number"))
        data["amount"] = self._normalize_amount(data.get("amount"))
        data["currency"] = self._normalize_currency(data.get("currency"))
        data["invoice_date"] = self._normalize_date(data.get("invoice_date"))
        data["category"] = self._normalize_category(data.get("category"))
        data["confidence_score"] = self._clamp_confidence(data.get("confidence_score", 0.0))

        if self._invoice_number_is_tax_id(data.get("invoice_number")):
            data["invoice_number"] = None

        data["needs_review"] = bool(data.get("needs_review"))
        data = self._apply_review_rules(data)

        return ExtractionResult.model_validate(data)

    def _clean_invoice_number(self, raw: str | None) -> str | None:
        if not raw:
            return None
        cleaned = _ZERO_WIDTH.sub("", str(raw)).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned:
            return None
        # Reject if normalization says tax/client ID
        if normalize_invoice_number(cleaned) is None and is_tax_or_client_id(
            re.sub(r"[^A-Z0-9]", "", cleaned.upper())
        ):
            return None
        if _TAX_ID_PATTERN.match(re.sub(r"[^0-9]", "", cleaned)):
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
        if isinstance(value, (int, float)):
            amount = float(value)
            return amount if amount > 0 else None

        text = str(value).strip()
        if not text:
            return None

        # Strip currency symbols and whitespace
        text = re.sub(r"[€$£\s]", "", text)
        # European: 1.931,78 or 1 931,78
        if re.search(r",\d{2}$", text):
            text = text.replace(".", "").replace(" ", "").replace(",", ".")
        else:
            text = text.replace(" ", "").replace(",", "")
        try:
            amount = float(text)
        except ValueError:
            return None
        return amount if amount > 0 else None

    def _normalize_currency(self, raw: str | None) -> str | None:
        if not raw:
            return None
        code = re.sub(r"[^A-Za-z]", "", str(raw)).upper()
        if len(code) == 3:
            return code
        aliases = {
            "EURO": "EUR",
            "DOLLAR": "USD",
            "US DOLLAR": "USD",
        }
        return aliases.get(code)

    def _normalize_date(self, raw: str | None) -> str | None:
        if not raw:
            return None
        text = str(raw).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            try:
                datetime.strptime(text, "%Y-%m-%d")
                return text
            except ValueError:
                return None

        formats = (
            "%d.%m.%Y",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d-%b-%y",
            "%d-%b-%Y",
            "%d %b %Y",
            "%d %B %Y",
            "%Y/%m/%d",
        )
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _normalize_category(self, raw: str | None) -> str | None:
        if not raw:
            return None
        allowed = {
            "professional services",
            "utilities",
            "software",
            "it / hardware",
            "it/hardware",
            "office",
            "travel",
            "other",
        }
        key = str(raw).strip().lower()
        mapping = {
            "professional services": "Professional services",
            "utilities": "Utilities",
            "utility": "Utilities",
            "software": "Software",
            "it / hardware": "IT / Hardware",
            "it/hardware": "IT / Hardware",
            "hardware": "IT / Hardware",
            "office": "Office",
            "travel": "Travel",
            "other": "Other",
        }
        if key in mapping:
            return mapping[key]
        for label in allowed:
            if label in key:
                return mapping.get(label, raw.strip())
        return raw.strip() if raw.strip() else None

    def _clamp_confidence(self, value: float) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, score))

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
            if score >= CONFIDENCE_AUTO_OK:
                data["confidence_score"] = min(score, CONFIDENCE_REVIEW - 0.01)
        if data.get("amount") is not None and data["amount"] <= 0:
            data["amount"] = None
            data["needs_review"] = True

        return data
