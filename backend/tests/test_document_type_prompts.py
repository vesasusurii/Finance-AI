from ai.prompts.document_types.rules import build_document_type_rules
from core.document_categories import DocumentCategory


def test_utility_rules_include_kesco():
    rules = build_document_type_rules(DocumentCategory.UTILITY)
    assert "electricity_kesco" in rules


def test_albanian_retail_rules_mention_fatura():
    rules = build_document_type_rules(DocumentCategory.ALBANIAN_RETAIL)
    assert "FATURA - INVOICE" in rules


def test_freelancer_rules_mention_hours():
    rules = build_document_type_rules(DocumentCategory.FREELANCER)
    assert "INVOICE" in rules


def test_generic_rules_empty():
    assert build_document_type_rules(DocumentCategory.GENERIC) == ""
