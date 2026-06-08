"""
Per-field extraction rules for all document types.
"""

FIELD_RULES = """
## Per-field extraction rules

### name_of_company  ← ISSUER, never the client
- Take from letterhead / logo area / "From" block at the very top of page 1.
- Use the legal business name exactly as printed (including "SH.P.K.", "LLC", "GmbH", "d.o.o.", "S.R.L.").
- If there is a trade name and a legal name on the same line, prefer the legal name.
- NEVER use: Klienti, Customer, Bill to, Ship to, Blerësi, Klijent — those are the client.
- **Albanian bilingual retail invoices (`FATURA - INVOICE`):** the **buyer** often appears first under **Detajet e blerësit / Buyer detail** (e.g. Borek Solutions). The **issuer/supplier** is the company name beside or below the `FATURA - INVOICE` title (e.g. Sarajeva Steak House SH.P.K.). Use the supplier, never the buyer block.
- For SaaS receipts with only a logo: read the company name from the logo area.

### address_of_company  ← ISSUER address
- Full address of the issuer (same entity as `name_of_company`).
- Include street, city, country if visible.
- Omit client address entirely.
- **CRITICAL — city names:** Read the city name CHARACTER BY CHARACTER from the printed text.
  NEVER infer or guess a city from its postal code. German postal codes are not unique to one city.
  Example trap: "72124 Pliezhausen" — do NOT write "Pforzheim" or any other city. Write exactly "Pliezhausen".
  Example trap: "75173 Pforzheim" — do NOT write "Karlsruhe". Write exactly "Pforzheim".
  If the city is partially visible or uncertain → copy what you can read and set needs_review true.

### invoice_number  ← EXACT reference from document, never a tax/registration ID
- **Output format:** copy **exactly as printed** on the document — keep `/`, `-`, spaces, and letter case if shown (e.g. `1/2026/0048`, `3807F638-0011`, `INV-2024-001`, `INVOICE 007`). Do not strip or reformat separators; matching normalization happens in software later.
- Read the value printed on **this** document — never reuse numbers from examples or prior extractions.
- **Generic invoices:** Invoice Ref, Fatura Nr., Belegnummer, Bill No., etc.
- **Freelancer / timesheet invoices:** Top title line `INVOICE ###` or `Invoice ###` with date beside it — the number **immediately after** INVOICE is the reference (may be short, e.g. `007`). Also check `Invoice No.` / `Nr.` in the header block. Short numeric refs are valid — do not skip them.
- **Albanian bilingual retail (`FATURA - INVOICE ####`):** invoice number is the numeric value on the title line after INVOICE (e.g. `14465`). Also check **Numri i faturës / Invoice number** in the header. NEVER use **Numri Fiskal / Fiscal Number**, **Numri i Biznesit / Business No**, or bank account numbers from the Banks block.
- **KESCO (`electricity_kesco`):** use utility rules — **Nr. Ref.** near bill end (alphanumeric pattern shape `1900……B`, value varies).
- **Water (`water_regional`):** use **CRITICAL water bill rules** — footer payment ref above barcode (`^F[0-9]+[A-Z]?$`, 12+ digits). Never truncated header Bill number.
- **Pastrimi waste (`waste_pastrimi`):** use **Total Due** / **Gjithsej borxhi** for `amount` (includes prior debt) — not Monthly Invoice Total or Për pagesë alone.
- NEVER use as invoice_number: NUI, UNI, NRF, NIPT, VAT No., customer IDs (Shifra e konsumatorit), meter numbers, bank account numbers, IBANs (e.g. `XK05…`).
- If genuinely not found → null (do not invent).

### invoice_date  ← date the invoice was issued
- Output format: YYYY-MM-DD only.
- Accept: DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD, DD-MMM-YY (04-Feb-26 → 2026-02-04), DD MMM YYYY, long month names in any language.
- Use "Invoice date" / "Data" / "Date of issue" — NOT "Due date" / "Data e maturimit" / "Payment date".
- If multiple dates shown: invoice issue date takes priority over due date and supply date.
- If ambiguous or unreadable → null + needs_review true.

### document_type
- Required on every extraction: `electricity_kesco`, `water_regional`, `waste_pastrimi`, or `generic`.
- Detect from logo/header before extracting other fields.

### debt  ← outstanding balance ONLY (separate from amount)
- Prior unpaid balance, Borxhi, Total Debt, KESCO debt, KESCO+KEK debt lines.
- Never add debt into `amount`. Never use debt as amount.
- If no debt line on document → null.

### amount  ← the amount Finance must PAY for this invoice
**If `document_type` is `electricity_kesco`, `water_regional`, or `waste_pastrimi`:** follow utility rules above for amount/debt — do not use this generic tree.

**Decision tree (generic documents only) — follow in order:**
1. Is there a line labelled "Për pagesë" / "For payment" / "Za naplatu" / "Zahlbetrag" / "Zu zahlen"?  
   → Use that value. STOP. (This excludes prior-period debt on utility bills.)
2. Is there a line labelled "Bruttobetrag" / "Gesamtbetrag inkl. MwSt" / "Total Amount Due" / "Amount due" / "Grand total" / "Total invoice" / "Gjithsej me TVSH" / **"Vlera me TVSH" / "Amount with VAT"** / **"Gjithësejt vlerat" / "Total's"** (use the **with-VAT** column)?  
   → Use that value. STOP.
3. Is there a single "Total" / "Gesamtbetrag" line at the bottom of the totals block?  
   → Use that. STOP.
4. Is it a line-item invoice with Nettobetrag + MwSt = Bruttobetrag?  
   → Use the Bruttobetrag (Sub-total + VAT = Grand total). STOP.
5. Still not clear → null + needs_review true. NEVER guess.

**MULTI-PAGE RULE:** If you are on page 1 of a multi-page document and you see ONLY line items
(each row has Qty × Unit price = Line total) but NO summary totals block (Nettobetrag / Bruttobetrag / Grand total),
the totals are on a later page. Set amount to null — do NOT pick the largest line item amount.
Wait until you can read the totals page.

**Do NOT use:**
- Nettobetrag / Sub-total / Nëntotal / Net amount (before VAT) / **Vlera pa TVSH / Amount without VAT**.
- **Vlera e TVSH'së / Amount of VAT** (the VAT component alone).
- "Total Due" / "Gjithsej borgji" when a separate "Për pagesë" line exists — **except** `waste_pastrimi` bills where Total Due **is** the payment amount.
- Individual line item prices (Gesamt € per row — these are per-item totals, NOT the invoice total).
- Any number that appears in the line-items table rows.

**Format:** Return as plain decimal number, no currency symbol. European thousands dots removed, comma decimal → dot: `1.931,78` → `1931.78`.

### currency
- Read the ISO 4217 code as printed: EUR, USD, GBP, CHF, ALL, BAM, RSD, MKD.
- If a symbol is shown without a code: € → EUR, $ → USD, £ → GBP.
- Do NOT default to EUR if the document shows USD or another currency.
- If currency not visible → null.

### account_details
- Capture: IBAN (full, e.g. XK05 1110 3421 7000 0160), bank name, SWIFT/BIC code.
- Format: "IBAN XK051110342170000160 | Bank Name | SWIFT ABCDXKPR"
- If multiple IBANs: list ALL, each on its own segment separated by " || ".
  Example with two banks: "IBAN DE29602501300001599060 | Kreissparkasse Böblingen || IBAN DE14641300230002268827 | Kreissparkasse Tübingen | BIC SOLADEST1UB"
- German invoices commonly show 2–3 bank accounts in the footer — capture every one.
- **IBAN digit accuracy:** Read each 4-digit group independently. IBAN groups must NOT be swapped or merged.
  DE14 6005 0660 1000 5996 60 → "DE14600506601000599660" (remove spaces). Verify group count matches country format.
- SWIFT/BIC is usually listed directly after the IBAN or bank name.
- If no bank details shown → null.

### internal_note_description
- 1–3 sentence summary of what was purchased/provided.
- Include: service type, product names, period covered (e.g. "January 2026"), quantities if relevant.
- Keep concise. Do not copy the full line-item table.
- For SaaS: include plan name and billing period.
- For utilities: include meter readings or consumption period if visible.

### client_employee_related  ← Related person (never leave empty)
- Prefer the **individual contact name** from Kontaktperson / contact person / bill-to (e.g. "Muavi Rexhepi").
- Do NOT use the issuer/supplier name or full legal entity line (e.g. "Borek Solutions Kosovo L.L.C.") unless no person is named.
- If only a company appears in bill-to with no named person, or the field cannot be read: **`Borek Solutions`**.
- If there is no bill-to block or no extractable related person: **`Borek Solutions`**.
- NEVER return null for this field.

### category  ← pick exactly one
| Category              | Use when                                                   |
|-----------------------|------------------------------------------------------------|
| Professional services | Consulting, legal, accounting, auditing, HR, advisory      |
| Utilities             | Electricity, water, gas, telecom, internet, phone bills    |
| Software              | SaaS subscriptions, software licences, cloud services      |
| IT / Hardware         | Computer equipment, peripherals, network gear, repairs     |
| Office                | Office supplies, printing, furniture, cleaning             |
| Travel                | Flights, hotels, car hire, fuel, per diems                 |
| Other                 | Anything that does not fit the above                       |

### confidence_score
- 0.90–1.00: All 4 critical fields extracted cleanly — Finance auto-saves (no immediate review).
- 0.70–0.89: Save but mark for review (set needs_review true).
- Below 0.70: Do not finalise — set needs_review true and score below 0.70.
Critical fields: invoice_number, amount, invoice_date, name_of_company.

### needs_review
- true if ANY of the following: invoice_number is null, amount is null, invoice_date is null, name_of_company is null, confidence_score < 0.90, any critical field_confidences below 0.75, currency is ambiguous, amount vs total is unclear.
- false only when all 4 critical fields are clearly extracted, unambiguous, and confidence_score >= 0.90.

### field_confidences  ← per-field confidence map
Output a JSON object with a confidence score (0.0–1.0) for every field you extracted.
Scores reflect how clearly and unambiguously you read each specific value from the document.
**Water bills (`water_regional`):** if any digit or optional trailing letter in `invoice_number` is uncertain, set `field_confidences.invoice_number` ≤ **0.70** and `invoice_number` to null.
Include ALL of the following keys, even if null (score 0.0 for fields you could not find):

```json
{
  "name_of_company": 0.95,
  "address_of_company": 0.88,
  "invoice_date": 0.97,
  "invoice_number": 0.82,
  "amount": 0.91,
  "currency": 0.99,
  "account_details": 0.74,
  "internal_note_description": 0.85,
  "client_employee_related": 0.92,
  "category": 0.90
}
```

Scoring guidance:
- 0.90–1.00: Value printed clearly and unambiguously; no doubt.
- 0.75–0.89: Value found but image quality or layout required some interpretation.
- 0.50–0.74: Found but partially legible, abbreviation, or uncertain match to the correct label.
- 0.20–0.49: Guessed based on context; low confidence.
- 0.00–0.19: Not found or unreadable; field is null.

### Permanently excluded — NEVER return these keys
paid_at_date, paid_by
""".strip()

__all__ = ['FIELD_RULES']
