from schemas.invoice import ExtractionResult
from services.ai_validation_service import AIValidationService
from utils.normalization import split_invoice_number


def test_sanitize_keeps_display_separators():
    raw = ExtractionResult.model_validate(
        {
            "document_type": "generic",
            "invoice_number": "1/2026/0048",
            "name_of_company": "Example SH.P.K.",
            "amount": 100.0,
            "invoice_date": "2026-01-28",
            "confidence_score": 0.95,
        }
    )
    result = AIValidationService().sanitize_and_validate(raw)
    assert result.invoice_number == "1/2026/0048"


def test_split_after_sanitize():
    display, normalized = split_invoice_number("3807F638-0011")
    assert display == "3807F638-0011"
    assert normalized == "3807F6380011"
