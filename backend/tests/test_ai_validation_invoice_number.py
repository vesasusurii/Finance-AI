from services.ai_validation_service import AIValidationService
from schemas.invoice import ExtractionResult


def test_sanitize_keeps_short_invoice_number():
    svc = AIValidationService()
    result = ExtractionResult(
        invoice_number="007",
        amount=434.60,
        invoice_date="2026-05-26",
        name_of_company="Engjell Hasani",
        confidence_score=0.95,
        needs_review=False,
    )
    out = svc.sanitize_and_validate(result)
    assert out.invoice_number == "007"


def test_sanitize_catering_invoice_number():
    svc = AIValidationService()
    result = ExtractionResult(
        invoice_number="FATURA - INVOICE 14465",
        amount=900.00,
        invoice_date="2026-05-22",
        name_of_company="Sarajeva Steak House SH.P.K.",
        confidence_score=0.95,
        needs_review=False,
    )
    out = svc.sanitize_and_validate(result)
    assert out.invoice_number == "FATURA - INVOICE 14465"


def test_sanitize_rejects_fiscal_number_as_invoice_number():
    svc = AIValidationService()
    result = ExtractionResult(
        invoice_number="811915159",
        amount=900.00,
        invoice_date="2026-05-22",
        name_of_company="Sarajeva Steak House SH.P.K.",
        confidence_score=0.95,
        needs_review=False,
    )
    out = svc.sanitize_and_validate(result)
    assert out.invoice_number is None
    assert out.needs_review is True


def test_sanitize_rejects_date_as_invoice_number():
    svc = AIValidationService()
    result = ExtractionResult(
        invoice_number="2026-05-22",
        amount=900.00,
        invoice_date="2026-05-22",
        name_of_company="Sarajeva Steak House SH.P.K.",
        confidence_score=0.95,
        needs_review=False,
    )
    out = svc.sanitize_and_validate(result)
    assert out.invoice_number is None


def test_sanitize_rejects_bank_account_as_invoice_number():
    svc = AIValidationService()
    result = ExtractionResult(
        invoice_number="2011000129521812",
        amount=900.00,
        invoice_date="2026-05-22",
        name_of_company="Test Co",
        confidence_score=0.95,
        needs_review=False,
    )
    out = svc.sanitize_and_validate(result)
    assert out.invoice_number is None


def test_sanitize_rejects_iban_as_invoice_number():
    svc = AIValidationService()
    result = ExtractionResult(
        invoice_number="XK051701010500018287",
        amount=434.60,
        invoice_date="2026-05-26",
        name_of_company="Engjell Hasani",
        confidence_score=0.95,
        needs_review=False,
    )
    out = svc.sanitize_and_validate(result)
    assert out.invoice_number is None
    assert out.needs_review is True
