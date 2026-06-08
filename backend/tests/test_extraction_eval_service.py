from schemas.invoice import ExtractionResult
from services.extraction_eval_service import (
    build_report,
    compare_extraction,
)


def test_compare_extraction_pass():
    expected = {
        "invoice_number": "007",
        "invoice_date": "2026-05-26",
        "amount": 434.6,
        "name_of_company": "Engjell Hasani",
    }
    actual = ExtractionResult(
        invoice_number="007",
        invoice_date="2026-05-26",
        amount=434.60,
        name_of_company="Engjell Hasani",
        confidence_score=0.95,
    )
    result = compare_extraction(expected, actual, fixture_name="freelancer-007")
    assert result.passed
    assert result.accuracy == 1.0


def test_compare_extraction_fail_on_amount():
    expected = {"invoice_number": "007", "amount": 434.6}
    actual = ExtractionResult(invoice_number="007", amount=400.0, confidence_score=0.9)
    result = compare_extraction(expected, actual, fixture_name="bad")
    assert not result.passed


def test_build_report_fails_below_baseline():
    from services.extraction_eval_service import FixtureResult, FieldComparison

    results = [
        FixtureResult(
            fixture_name="x",
            passed=False,
            field_results=[
                FieldComparison("invoice_number", "007", None, False),
            ],
        )
    ]
    report = build_report(results, baseline_accuracy=1.0)
    assert not report.passed
    assert report.overall_accuracy == 0.0
