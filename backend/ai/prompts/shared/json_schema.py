"""
JSON keys, output schema instructions, and example JSON shape.
"""

JSON_KEYS = """
document_type, invoice_date, name_of_company, address_of_company, invoice_number, amount, debt, currency, account_details, internal_note_description, client_employee_related, category, confidence_score, needs_review, field_confidences
""".strip()


def build_json_schema() -> str:
    """Schema block with key list interpolated (matches legacy f-string)."""
    return f"""
## Output — ONE JSON object, keys in this exact order:

```
{{{JSON_KEYS}}}
```

- String values: trimmed. **`invoice_number`:** exact text as printed on the document (preserve `/`, `-`, spaces, and case).
- Numeric values: unquoted floats (amount, confidence_score).
- Boolean values: unquoted true/false (needs_review).
- Missing/not-found fields: null (unquoted).
- No extra keys. No markdown. No explanation outside the JSON object.
""".strip()


OUTPUT_EXAMPLE = """
## Example (shape only — values must come from the actual document):

{
  "document_type": "generic",
  "invoice_date": "2026-01-28",
  "name_of_company": "Example Consulting SH.P.K.",
  "address_of_company": "Str. Garibaldi 12, Prishtina, Kosovo",
  "invoice_number": "1/2026/0048",
  "amount": 1931.78,
  "debt": null,
  "currency": "EUR",
  "account_details": "IBAN XK051110342170000160 | ProCredit Bank | SWIFT MBKOXKPR",
  "internal_note_description": "Compliance consulting and administrative services, January 2026",
  "client_employee_related": "Lum Meta",
  "category": "Professional services",
  "confidence_score": 0.94,
  "needs_review": false,
  "field_confidences": {
    "name_of_company": 0.97,
    "address_of_company": 0.91,
    "invoice_date": 0.98,
    "invoice_number": 0.95,
    "amount": 0.93,
    "debt": 0.90,
    "currency": 0.99,
    "account_details": 0.88,
    "internal_note_description": 0.85,
    "client_employee_related": 0.92,
    "category": 0.90
  }
}
""".strip()

__all__ = ["JSON_KEYS", "build_json_schema", "OUTPUT_EXAMPLE"]
