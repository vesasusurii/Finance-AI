from services.document_classifier_service import DocumentClassifierService
from core.document_categories import DocumentCategory


def test_classify_kesco_as_utility():
    text = "KESCO electricity bill Nr. Ref. 190053493260100B Borxhi KESCO"
    assert DocumentClassifierService().classify(text) == DocumentCategory.UTILITY


def test_classify_albanian_retail():
    text = "FATURA - INVOICE 14465 Numri i faturës Vlera me TVSH Detajet e blerësit"
    assert DocumentClassifierService().classify(text) == DocumentCategory.ALBANIAN_RETAIL


def test_classify_freelancer():
    text = "INVOICE 007 Total Hours Worked Hourly Rate Web Development"
    assert DocumentClassifierService().classify(text) == DocumentCategory.FREELANCER


def test_classify_promptcloud_as_saas():
    text = (
        "PromptCloud Inc Billed To Borek Solutions Invoice Number 0012233 "
        "Amount Due (USD) Date of Issue 08/21/2025 Pending amount 1881.88 "
        "Crawl cost for repeat sites Invoice period 20250720 - 20250819"
    )
    assert DocumentClassifierService().classify(text) == DocumentCategory.SAAS


def test_classify_generic_when_no_markers():
    assert DocumentClassifierService().classify("Random document text") == DocumentCategory.GENERIC
