from utils.invoice_number_parser import extract_invoice_numbers


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
