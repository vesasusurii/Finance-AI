from utils.invoice_number_parser import extract_invoice_numbers, needs_llm_fallback


# ─────────────────────────────────────────────────────────────────────────────
# Existing happy-path coverage
# ─────────────────────────────────────────────────────────────────────────────


def test_payment_for_invoice():
    assert extract_invoice_numbers("Payment for invoice 26063") == ["26063"]


def test_multiple_invoices():
    nums = extract_invoice_numbers("Payment for invoices 26063, 26060, 260658")
    assert "26063" in nums
    assert "26060" in nums
    assert "260658" in nums


def test_slash_serial():
    assert extract_invoice_numbers("Pagesa fature 1/2026/0048") == ["120260048"]


def test_tax_id_rejected():
    assert extract_invoice_numbers("811915159") == []


def test_empty_comment():
    assert extract_invoice_numbers("") == []
    assert extract_invoice_numbers(None) == []


# ─────────────────────────────────────────────────────────────────────────────
# Real-world false-positive cases (from production bank statements)
# Each docstring describes the failure mode the hardened regex must avoid.
# ─────────────────────────────────────────────────────────────────────────────


def test_card_payment_no_invoice():
    """Card authorisation: APROVAL code, TERM code, date — none are invoices."""
    comment = (
        "APROVAL:503980; TERM:VCQVBGS0; HEYGEN TECHNOLOGY IN 11/02/2026 "
        "13:30:32 HEYGEN TECHNOLOGY INC. HEYGEN.COM US; BOREK KONSTANTIN"
    )
    assert extract_invoice_numbers(comment) == []


def test_iban_not_treated_as_invoice():
    """Comment has 'Inv 26-0103' + a Macedonian IBAN. Only the invoice
    should be returned; IBAN body must not leak as a numeric candidate."""
    comment = (
        "Inv 26-0103, NLB BANKA AD SKOPJE, MK JOB DOO MK JOB DOO;"
        "MK07210701001870650;NLB BANKA AD SKOPJE;"
        "BOREK SOLUTIONS KOSOVO L.L.C.;Inv 26-0103;Inv 26-0103"
    )
    result = extract_invoice_numbers(comment)
    assert result == ["260103"]
    # IBAN must never appear in the output (either raw or digit-stripped).
    assert "MK07210701001870650" not in result
    assert "07210701001870650" not in result


def test_multi_invoice_with_albanian_dhe():
    """'dhe' is Albanian for 'and' — splits multiple invoices in one comment.
    Also tests that the trailing bank account number (15 digits) is rejected."""
    comment = (
        "Pagese per fat. FDP25-00114712 dhe FDP25-00133895, "
        "Uje Rugove SH.P.K. ;118900228600017 6;"
        "Pagese per fat. FDP25-00114712 dhe FDP25-00133895;"
        "BOREK SOLUTIONS KOSOVO L.L.C.;1110343587000119"
    )
    result = extract_invoice_numbers(comment)
    assert sorted(result) == ["FDP2500114712", "FDP2500133895"]
    assert "118900228600017" not in result
    assert "1110343587000119" not in result


def test_bank_fee_with_german_iban_no_invoice():
    """Bank fee comment with a DE IBAN — no invoice number should be extracted."""
    comment = (
        "Commission Fee for Max Fichtner, BANKHAUS C.L. SEELIGER, "
        "Borek Worldwide Solutions GmbH;DE86270325000000013671;"
        "BANKHAUS C.L. SEELIGER;BOREK SOLUTIONS KOSOVO L.L.C.;"
        "Commission Fee for Max Fichtner"
    )
    assert extract_invoice_numbers(comment) == []


def test_date_fragments_rejected():
    """'02/2026' inside a timestamp must not be treated as a slash-serial."""
    comment = "HEYGEN.COM US 11/02/2026 13:30:32"
    assert extract_invoice_numbers(comment) == []


def test_bare_year_rejected():
    """A standalone '2026' must not become a candidate."""
    assert extract_invoice_numbers("Payment 2026") == []


def test_alphanumeric_serial_after_dhe_without_keyword():
    """Second invoice ('FDP25-00133895') is anchored by 'dhe', not by a
    keyword. Tier-3 DASHED_SERIAL must still pick it up."""
    comment = "Pagese per fat. FDP25-00114712 dhe FDP25-00133895"
    assert sorted(extract_invoice_numbers(comment)) == [
        "FDP2500114712",
        "FDP2500133895",
    ]


def test_chained_keywords_pagesa_fature():
    """'Pagesa fature 1/2026/0048' — 'fature' is a chained keyword, must not
    be returned as a candidate token."""
    assert extract_invoice_numbers("Pagesa fature 1/2026/0048") == ["120260048"]
    assert "FATURE" not in extract_invoice_numbers("Pagesa fature 1/2026/0048")


def test_repeated_same_invoice_dedupes():
    """Same invoice mentioned three times in one comment → single entry."""
    comment = "Inv 26-0103, ref; Inv 26-0103; Inv 26-0103"
    assert extract_invoice_numbers(comment) == ["260103"]


# ─────────────────────────────────────────────────────────────────────────────
# `needs_llm_fallback` decision logic
# ─────────────────────────────────────────────────────────────────────────────


def test_llm_fallback_when_keywords_but_no_regex_hit():
    """Comment mentions 'invoice' but our patterns don't match → ask LLM."""
    assert needs_llm_fallback("Invoice XYZ-?+strange-format", []) is True


def test_llm_fallback_not_called_on_clean_comment():
    assert needs_llm_fallback("Payment for invoice 26063", ["26063"]) is False


def test_llm_fallback_not_called_on_card_payment():
    """Card payment has no invoice keywords → never spend an LLM call on it."""
    comment = "APROVAL:503980; TERM:VCQVBGS0; HEYGEN.COM"
    assert needs_llm_fallback(comment, []) is False


def test_llm_fallback_when_too_many_candidates():
    """Noisy comment yielding >3 candidates needs LLM disambiguation."""
    assert (
        needs_llm_fallback(
            "Pagesa fat. A, B, C, D, E", ["A", "B", "C", "D", "E"]
        )
        is True
    )


def test_llm_fallback_on_short_bare_numeric_without_keyword():
    """Tier-4 hit with no keyword anchor and short digits → suspicious."""
    assert needs_llm_fallback("Some random text 12345", ["12345"]) is True


def test_llm_fallback_skipped_when_empty_comment():
    assert needs_llm_fallback("", []) is False
    assert needs_llm_fallback(None, []) is False
