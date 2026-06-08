"""Post-extraction validation and normalisation (DOCS/8 § Step 4)."""

from __future__ import annotations

import re
from datetime import datetime

from core.debug_logger import debug_trace, get_logger, log_typed_fields
from schemas.invoice import ExtractionResult
from utils.normalization import (
    is_bank_account_number,
    is_date_like_invoice_number,
    is_iban_like,
    is_tax_or_client_id,
    normalize_invoice_number,
)

logger = get_logger(__name__)
# At or above this score with no review flags: auto-save (pending).
CONFIDENCE_AUTO_OK = 0.90
# Below this score: require manual review before finalising.
CONFIDENCE_MANUAL_REVIEW = 0.70
# Per-field score below this is treated as "unclear".
FIELD_UNCLEAR_THRESHOLD = 0.75

# Default when no contact person is extracted from the document
DEFAULT_CLIENT_RELATED = "Borek Solutions"

KESCO_COMPANY_NAME = "KESCO"
WATER_COMPANY_NAME = "Kompania Rajonale e Ujesjellesit"
PASTRIMI_COMPANY_NAME = 'Ndermarrja Regjionale e Mbeturinave "Pastrimi" SH.A'
PASTRIMI_ADDRESS = "Rr. Bill Clinton p.n., Prishtinë"

_DOC_TYPE_KESCO = "electricity_kesco"
_DOC_TYPE_WATER = "water_regional"
_DOC_TYPE_PASTRIMI = "waste_pastrimi"

_RE_PASTRIMI_HEADER_INVOICE = re.compile(r"^\d{6,8}$")

# Pattern shapes for validation only — not fixed invoice numbers
_RE_KESCO_CUSTOMER_ID = re.compile(r"^\d{7,12}$")
_RE_KESCO_NR_REF = re.compile(r"^[0-9]{10,}[A-Z][A-Z0-9]*$", re.IGNORECASE)
_RE_KESCO_DATE_LIKE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
# Water payment ref: ^F[0-9]+[A-Z]?$ with minimum digit length enforced in helpers
_RE_WATER_PAYMENT_REF = re.compile(r"^F\d+[A-Z]?$", re.IGNORECASE)
_WATER_PAYMENT_MIN_DIGITS = 12
_RE_WATER_PURE_NUMERIC = re.compile(r"^\d{3,12}$")
_RE_WATER_METER_LIKE = re.compile(r"^\d{3,6}$")
_RE_NUI_NIPT = re.compile(r"^810\d{6,}$")
_RE_WATER_DATE_LIKE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")

# Tax / registration IDs commonly misread as invoice numbers
_TAX_ID_PATTERN = re.compile(r"^(81[01]\d{6}|330\d{6,})$")
# IBAN-shaped strings (e.g. XK051701010500018287) must not become invoice_number
_RE_IBAN_LIKE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")

# Short numeric refs (007, 42) are valid on invoices; bank comments keep min length 4
_EXTRACTED_INVOICE_MIN_DIGITS = 1

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

    @debug_trace
    def determine_review_status(self, result: ExtractionResult) -> str:
        """
        Route invoices by confidence tier (DOCS/8).

        - Score >= 90% and no review flags -> pending (auto-save).
        - Score 70–89%, or flagged with score >= 70% -> needs_review.
        - Score < 70% -> manual_review (do not finalise until reviewed).
        """
        score = result.confidence_score
        if score >= CONFIDENCE_AUTO_OK and not result.needs_review:
            return "pending"
        if score < CONFIDENCE_MANUAL_REVIEW:
            return "manual_review"
        return "needs_review"

    @debug_trace
    def collect_review_reasons(self, data: dict) -> list[str]:
        """Structured reasons for Needs Review / Manual Review UI."""
        reasons: list[str] = []
        if not data.get("invoice_number"):
            reasons.append("missing_invoice_number")
        if data.get("amount") is None:
            reasons.append("missing_amount")
        if not data.get("name_of_company"):
            reasons.append("missing_company_name")
        elif self._field_unclear(data.get("field_confidences") or {}, "name_of_company"):
            reasons.append("unclear_company_name")
        if not data.get("invoice_date"):
            reasons.append("missing_invoice_date")
        elif self._field_unclear(data.get("field_confidences") or {}, "invoice_date"):
            reasons.append("unclear_invoice_date")

        score = float(data.get("confidence_score") or 0.0)
        if score < CONFIDENCE_MANUAL_REVIEW:
            reasons.append("low_ai_confidence")

        return reasons

    @staticmethod
    def _field_unclear(field_confidences: dict, field: str) -> bool:
        raw = field_confidences.get(field)
        if raw is None:
            return False
        try:
            return float(raw) < FIELD_UNCLEAR_THRESHOLD
        except (TypeError, ValueError):
            return False

    @debug_trace
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

    @debug_trace
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

        doc_type = getattr(result, "document_type", None)
        if result.invoice_number:
            inv = re.sub(r"\s", "", result.invoice_number)
            inv_upper = inv.upper()
            if doc_type == _DOC_TYPE_KESCO:
                if _RE_KESCO_CUSTOMER_ID.fullmatch(inv) or _RE_KESCO_DATE_LIKE.fullmatch(inv):
                    issues.append("kesco_invoice_number_not_nr_ref")
            elif doc_type == _DOC_TYPE_WATER:
                if (
                    _RE_NUI_NIPT.fullmatch(inv_upper)
                    or _RE_WATER_PURE_NUMERIC.fullmatch(inv)
                    or _RE_WATER_DATE_LIKE.fullmatch(inv)
                    or self._water_invoice_is_truncated(inv_upper)
                    or not self._water_payment_ref_valid(inv_upper)
                ):
                    issues.append("water_invoice_number_invalid")

        return issues

    @debug_trace
    def sanitize_and_validate(self, result: ExtractionResult) -> ExtractionResult:
        """Normalise all fields and apply code-level review rules after LLM parse."""
        data = result.model_dump()
        log_typed_fields(logger, "sanitize: incoming", data)

        data["invoice_number"] = self._clean_invoice_number(data.get("invoice_number"))
        data["amount"] = self._normalize_amount(data.get("amount"))
        data["debt"] = self._normalize_amount(data.get("debt"))
        data["currency"] = self._normalize_currency(data.get("currency"))
        data["invoice_date"] = self._normalize_date(data.get("invoice_date"))
        data["category"] = self._normalize_category(data.get("category"))
        data["confidence_score"] = self._clamp_confidence(data.get("confidence_score", 0.0))
        data["name_of_company"] = self._clean_text(data.get("name_of_company"))
        data["address_of_company"] = self._clean_text(data.get("address_of_company"))
        data["account_details"] = self._clean_text(data.get("account_details"))
        data["internal_note_description"] = self._clean_text(data.get("internal_note_description"))
        data["client_employee_related"] = self._default_client_related(
            data.get("client_employee_related")
        )

        if self._invoice_number_is_tax_id(data.get("invoice_number")):
            logger.debug(
                "Discarded invoice_number %r — looks like a tax/client ID",
                data.get("invoice_number"),
            )
            data["invoice_number"] = None

        data["needs_review"] = bool(data.get("needs_review"))
        data = self._apply_utility_document_rules(data)
        data = self._apply_review_rules(data)
        data["review_reasons"] = self.collect_review_reasons(data)
        log_typed_fields(logger, "sanitize: outgoing", data)
        return ExtractionResult.model_validate(data)

    # ─────────────────────────────────────────────────────────────────────
    # Field normalisers
    # ─────────────────────────────────────────────────────────────────────

    @debug_trace
    def _clean_text(self, raw: str | None) -> str | None:
        if not raw:
            return None
        cleaned = _ZERO_WIDTH.sub("", str(raw)).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned if cleaned else None

    def _default_client_related(self, raw: str | None) -> str:
        """Use Borek Solutions when the model returns no related person."""
        cleaned = self._clean_text(raw)
        if not cleaned:
            return DEFAULT_CLIENT_RELATED
        lowered = cleaned.lower()
        if lowered in ("null", "none", "n/a", "-", "unknown"):
            return DEFAULT_CLIENT_RELATED
        return cleaned

    def _clean_invoice_number(self, raw: str | None) -> str | None:
        if not raw:
            return None
        cleaned = _ZERO_WIDTH.sub("", str(raw)).strip()
        if not cleaned:
            return None
        formatted = normalize_invoice_number(
            cleaned,
            min_digit_length=_EXTRACTED_INVOICE_MIN_DIGITS,
        )
        if formatted is None:
            return None
        if is_iban_like(formatted) or _RE_IBAN_LIKE.fullmatch(formatted):
            return None
        if is_bank_account_number(formatted):
            return None
        if is_date_like_invoice_number(formatted):
            return None
        if _TAX_ID_PATTERN.match(re.sub(r"[^0-9]", "", formatted)):
            return None
        return cleaned

    @debug_trace
    def _invoice_number_is_tax_id(self, invoice_number: str | None) -> bool:
        if not invoice_number:
            return False
        compact = re.sub(r"[^A-Z0-9]", "", invoice_number.upper())
        if is_tax_or_client_id(compact):
            return True
        digits_only = re.sub(r"[^0-9]", "", invoice_number)
        return bool(_TAX_ID_PATTERN.match(digits_only))

    @debug_trace
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

    @debug_trace
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

    @debug_trace
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

    @debug_trace
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

    @debug_trace
    def _clamp_confidence(self, value: float) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, score))

    # ─────────────────────────────────────────────────────────────────────
    # Utility document rules (KESCO / regional water)
    # ─────────────────────────────────────────────────────────────────────

    def _detect_document_type(self, data: dict) -> str | None:
        declared = (data.get("document_type") or "").strip().lower()
        if declared in (_DOC_TYPE_KESCO, _DOC_TYPE_WATER, _DOC_TYPE_PASTRIMI, "generic"):
            return declared if declared != "generic" else None

        blob = " ".join(
            str(v) for v in (
                data.get("name_of_company"),
                data.get("address_of_company"),
                data.get("internal_note_description"),
                data.get("invoice_number"),
            )
            if v
        ).lower()
        blob_ascii = (
            blob.replace("ë", "e")
            .replace("ç", "c")
            .replace("ü", "u")
            .replace("š", "s")
        )

        if "kesco" in blob_ascii or ("borxhi kesco" in blob_ascii):
            return _DOC_TYPE_KESCO
        if (
            "ujesjelles" in blob_ascii
            or "regional water" in blob_ascii
            or "ujesjell" in blob_ascii
        ):
            return _DOC_TYPE_WATER
        if (
            "pastrimi" in blob_ascii
            or "mbeturinave" in blob_ascii
            or "krm" in blob_ascii
            or "gjithsej borxhi" in blob_ascii
        ):
            return _DOC_TYPE_PASTRIMI
        return None

    def _apply_utility_document_rules(self, data: dict) -> dict:
        doc_type = self._detect_document_type(data)
        if not doc_type:
            data["document_type"] = data.get("document_type") or "generic"
            return data

        data["document_type"] = doc_type
        data["category"] = "Utilities"
        if not data.get("currency"):
            data["currency"] = "EUR"

        if doc_type == _DOC_TYPE_KESCO:
            data["name_of_company"] = KESCO_COMPANY_NAME
            data = self._apply_kesco_rules(data)
        elif doc_type == _DOC_TYPE_WATER:
            data["name_of_company"] = WATER_COMPANY_NAME
            data = self._apply_water_rules(data)
        elif doc_type == _DOC_TYPE_PASTRIMI:
            data["name_of_company"] = PASTRIMI_COMPANY_NAME
            data = self._apply_pastrimi_rules(data)

        return data

    def _apply_kesco_rules(self, data: dict) -> dict:
        client = data.get("client_employee_related") or ""
        if self._utility_customer_name_invalid(client, issuer=KESCO_COMPANY_NAME):
            data["needs_review"] = True

        data = self._validate_kesco_invoice_number(data)

        data["internal_note_description"] = self._ensure_utility_description(
            data.get("internal_note_description"),
            "KESCO electricity bill",
        )
        return data

    def _apply_water_rules(self, data: dict) -> dict:
        client = data.get("client_employee_related") or ""
        if self._utility_customer_name_invalid(client, issuer=WATER_COMPANY_NAME):
            data["needs_review"] = True

        data = self._validate_water_invoice_number(data)
        data = self._apply_water_invoice_confidence(data)

        data["internal_note_description"] = self._ensure_utility_description(
            data.get("internal_note_description"),
            "Regional water bill",
        )
        return data

    def _apply_pastrimi_rules(self, data: dict) -> dict:
        if not data.get("address_of_company"):
            data["address_of_company"] = PASTRIMI_ADDRESS

        data = self._validate_pastrimi_invoice_number(data)
        data = self._validate_pastrimi_amount(data)

        data["internal_note_description"] = self._ensure_utility_description(
            data.get("internal_note_description"),
            "Pastrimi regional waste bill",
        )
        return data

    def _validate_pastrimi_invoice_number(self, data: dict) -> dict:
        inv = re.sub(r"\s", "", (data.get("invoice_number") or ""))
        if not inv:
            data["needs_review"] = True
            return data
        if is_tax_or_client_id(inv) or _TAX_ID_PATTERN.match(inv) or _RE_NUI_NIPT.fullmatch(
            inv
        ):
            data["invoice_number"] = None
            data["needs_review"] = True
            return data
        if _RE_PASTRIMI_HEADER_INVOICE.fullmatch(inv):
            return data
        data["needs_review"] = True
        return data

    def _validate_pastrimi_amount(self, data: dict) -> dict:
        """
        Flag likely use of monthly/for-payment line instead of Total Due.
        When prior debt exists, amount should exceed previous-due alone.
        """
        amount = data.get("amount")
        debt = data.get("debt")
        if amount is None or debt is None:
            return data
        try:
            amt = float(amount)
            prior = float(debt)
        except (TypeError, ValueError):
            return data
        if prior > 0 and amt <= prior:
            data["needs_review"] = True
        return data

    def _apply_water_invoice_confidence(self, data: dict) -> dict:
        """Low per-field confidence on invoice_number → clear value and require review."""
        confidences = data.get("field_confidences") or {}
        raw_score = confidences.get("invoice_number")
        if raw_score is None:
            return data
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            return data
        if score <= 0.70:
            if data.get("invoice_number"):
                data["invoice_number"] = None
            data["needs_review"] = True
        return data

    def _validate_kesco_invoice_number(self, data: dict) -> dict:
        """Reject Customer ID / due-date confusion; accept bottom Nr. Ref. alphanumeric values."""
        inv = re.sub(r"\s", "", (data.get("invoice_number") or ""))
        if not inv:
            data["needs_review"] = True
            return data
        inv_upper = inv.upper()
        if _RE_KESCO_DATE_LIKE.fullmatch(inv):
            data["invoice_number"] = None
            data["needs_review"] = True
            return data
        if _RE_KESCO_NR_REF.fullmatch(inv_upper):
            return data
        # Pure numeric short values = Shifra e konsumatorit / Customer ID, not Nr. Ref.
        if _RE_KESCO_CUSTOMER_ID.fullmatch(inv) or re.fullmatch(r"\d{7,11}", inv):
            data["invoice_number"] = None
            data["needs_review"] = True
            return data
        # Alphanumeric but too short or missing letter suffix typical of Nr. Ref.
        if not re.search(r"[A-Z]", inv_upper) or len(inv_upper) < 12:
            data["invoice_number"] = None
            data["needs_review"] = True
        else:
            data["needs_review"] = True
        return data

    def _restore_water_invoice_number(self, raw: str) -> str | None:
        """
        Rebuild F-prefixed refs when Vision drops the leading F (common on water bills).
        Pattern-based only — no fixed invoice values.
        """
        inv_upper = re.sub(r"\s", "", raw).upper()
        if not inv_upper:
            return None
        if self._water_payment_ref_valid(inv_upper):
            return inv_upper
        # Footer line: digit run + optional suffix letter, missing leading F
        if re.fullmatch(r"\d{12,22}[A-Z]?", inv_upper):
            candidate = f"F{inv_upper}"
            if self._water_payment_ref_valid(candidate):
                return candidate
        return None

    def _water_ref_digit_count(self, inv_upper: str) -> int | None:
        match = re.match(r"^F(\d+)", inv_upper, re.IGNORECASE)
        return len(match.group(1)) if match else None

    def _water_payment_ref_valid(self, inv_upper: str) -> bool:
        if not _RE_WATER_PAYMENT_REF.fullmatch(inv_upper):
            return False
        count = self._water_ref_digit_count(inv_upper)
        return count is not None and count >= _WATER_PAYMENT_MIN_DIGITS

    def _water_invoice_is_truncated(self, inv_upper: str) -> bool:
        """True when only the short header bill-number prefix was captured."""
        if not inv_upper.startswith("F"):
            return False
        count = self._water_ref_digit_count(inv_upper)
        return count is not None and count < _WATER_PAYMENT_MIN_DIGITS

    def _validate_water_invoice_number(self, data: dict) -> dict:
        """Require full footer payment ref (F + digits + letter); reject truncated header-only values."""
        inv = re.sub(r"\s", "", (data.get("invoice_number") or ""))
        if not inv:
            data["needs_review"] = True
            return data
        inv_upper = inv.upper()
        if (
            _RE_WATER_DATE_LIKE.fullmatch(inv)
            or is_tax_or_client_id(inv_upper)
            or _RE_NUI_NIPT.fullmatch(inv_upper)
        ):
            data["invoice_number"] = None
            data["needs_review"] = True
            return data
        if self._water_payment_ref_valid(inv_upper):
            return data
        if self._water_invoice_is_truncated(inv_upper):
            data["invoice_number"] = None
            data["needs_review"] = True
            return data
        restored = self._restore_water_invoice_number(inv_upper)
        if restored:
            data["invoice_number"] = restored
            data["needs_review"] = True
            return data
        # Short numeric = Customer ID; longer numeric without restore = NUI/meter/guess
        if _RE_WATER_METER_LIKE.fullmatch(inv) or _RE_WATER_PURE_NUMERIC.fullmatch(inv):
            data["invoice_number"] = None
            data["needs_review"] = True
            return data
        # F-prefixed but missing trailing letter or wrong shape (incomplete footer read)
        if inv_upper.startswith("F"):
            data["invoice_number"] = None
        data["needs_review"] = True
        return data

    def _utility_customer_name_invalid(self, client: str, *, issuer: str) -> bool:
        if not client or client == DEFAULT_CLIENT_RELATED:
            return False
        lowered = client.lower()
        if issuer.lower() in lowered:
            return True
        compact = re.sub(r"[^A-Z0-9]", "", client.upper())
        if compact.isdigit() and len(compact) >= 7:
            return True
        if re.fullmatch(r"\d[\d\s]{6,}", client.replace(" ", "")):
            return True
        return False

    def _ensure_utility_description(
        self, existing: str | None, prefix: str
    ) -> str | None:
        if existing and prefix.lower() not in existing.lower():
            return f"{prefix}; {existing}"
        return existing or prefix

    # ─────────────────────────────────────────────────────────────────────
    # Review rule engine
    # ─────────────────────────────────────────────────────────────────────

    @debug_trace
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

        if missing:
            data["needs_review"] = True
            data["confidence_score"] = min(score, CONFIDENCE_MANUAL_REVIEW - 0.01)
        elif score < CONFIDENCE_AUTO_OK:
            data["needs_review"] = True
        elif score < CONFIDENCE_MANUAL_REVIEW:
            data["needs_review"] = True

        # Zero/negative amounts are invalid
        if data.get("amount") is not None and data["amount"] <= 0:
            data["amount"] = None
            data["needs_review"] = True

        # Category must be from the allowed set
        if data.get("category") and data["category"] not in VALID_CATEGORIES:
            data["category"] = "Other"

        return data
