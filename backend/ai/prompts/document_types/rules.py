"""Typed prompt blocks — only the section relevant to the classified document."""

from core.document_categories import DocumentCategory

from ai.prompts.utilities.utility_rules import build_utility_document_rules

ALBANIAN_RETAIL_RULES = """
## Albanian bilingual retail invoice (classified)

- **Buyer block** at top (Detajet e blerësit / Buyer detail) is the client — NOT `name_of_company`.
- **Issuer** is the supplier beside `FATURA - INVOICE ####` (e.g. Sarajeva Steak House SH.P.K.).
- `invoice_number`: number on `FATURA - INVOICE ####` or **Numri i faturës / Invoice number**.
- NEVER use Numri Fiskal / Fiscal Number / Business No / bank account digits as invoice_number.
- `amount`: **Vlera me TVSH / Amount with VAT** or rightmost total in **Gjithësejt vlerat** — NOT Vlera pa TVSH.
""".strip()

FREELANCER_RULES = """
## Freelancer / timesheet invoice (classified)

- Title line `INVOICE ###` with date — number after INVOICE is `invoice_number` (short refs like `007` are valid).
- `name_of_company`: individual or business in the **From** block (issuer), not the **To** / client.
- `amount`: **Total Amount Due** / final payable total — NOT hours × rate line items alone.
- NEVER use IBAN or bank account as invoice_number.
""".strip()


def build_document_type_rules(category: DocumentCategory) -> str:
    """Return prompt section for the classified category (empty for generic)."""
    if category == DocumentCategory.UTILITY:
        return build_utility_document_rules()
    if category == DocumentCategory.ALBANIAN_RETAIL:
        return ALBANIAN_RETAIL_RULES
    if category == DocumentCategory.FREELANCER:
        return FREELANCER_RULES
    return ""
