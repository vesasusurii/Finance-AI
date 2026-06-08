"""
Golden reference patterns — locations only, never hardcoded values.
"""

GOLDEN_EXAMPLES = """
## Verified reference extractions (patterns only — never hardcode values)

**Read values from the document you see.** Tables below teach **where to look** and **what shape to expect**, not fixed answers.

| Document type              | invoice_number pattern (where to look) | amount | Key trap to avoid |
|----------------------------|----------------------------------------|--------|-------------------|
| KESCO electricity          | **Nr. Ref.** near bill end (`…1900……B` shape) | Bill amount row | Customer ID ≠ invoice #; debt ≠ amount |
| Regional water bill        | **Full** footer ref above barcode (`^F[0-9]+[A-Z]?$`, 12+ digits) | Bill Amount row | Truncated header / Customer ID / NUI ≠ invoice # |
| Pastrimi / KRM waste       | **Nr.-No.-Br.** in header | **Total Due** / Gjithsej borxhi | Monthly total / Për pagesë ≠ amount when Total Due shown |
| Scanned bilingual services | Labelled invoice ref in header block | Për pagesë row | Sub-total is NOT amount |
| Albanian retail / catering | `FATURA - INVOICE ####` title line | **Vlera me TVSH** / Amount with VAT | Buyer fiscal ≠ invoice #; pa TVSH ≠ amount |
| Freelancer / timesheet     | Title `INVOICE ###` on page 1 (e.g. `007`) | Total Amount Due row | IBAN / account ≠ invoice #; hours × rate ≠ total |
| Trilingual utility bill    | E-payment / platform ref (not header Nr.) | Për pagesë row | Total Due with old debt is NOT amount |
| SaaS / retail / German     | Belegnummer / invoice ref in header block | Grand total on last page | Line items ≠ amount |

### German Rechnung detailed example
Document: SCHMIEDER it-solutions GmbH, Rechnung, Seite 1/2

**Page 1 header block:**
  SCHMIEDER it-solutions GmbH • Carl-Zeiss-Straße 5 • 72124 Pliezhausen
  → name_of_company: "SCHMIEDER it-solutions GmbH"
  → address_of_company: "Carl-Zeiss-Straße 5, 72124 Pliezhausen" (NOT Pforzheim — read it!)

**Page 1 reference block (top-right):**
  Belegnummer: [read from document]  ← invoice_number field
  Datum: [read from document]        ← invoice_date → YYYY-MM-DD
  Kundennr.: 610260       ← customer number, IGNORE
  Fälligkeitsdatum: 02.03.2026 ← due date, NOT invoice_date
  Kontaktperson: Muavi Rexhepi ← client_employee_related

**Page 1 line items (Pos / Menge / Beschreibung / Preis € / Gesamt €):**
  Row 1: 47 × 4,20 = 197,40   ← line item sub-total, NOT the invoice amount
  Row 2:  1 × 9,00 =   9,00   ← line item sub-total, NOT the invoice amount
  Row 3: 57 × 11,65 = 664,05  ← line item sub-total, NOT the invoice amount
  Row 4: 41 × 24,70 = 1.012,70 ← line item sub-total, NOT the invoice amount
  → amount = null (totals are on page 2)

**Page 2 totals block:** (not shown but contains):
  Nettobetrag: …  MwSt 19%: …  Bruttobetrag / Zahlbetrag: [FINAL AMOUNT] ← use this

**Page 2 footer (Bankverbindung):**
  Two banks listed — capture BOTH IBANs with their bank names.
  Read each IBAN digit group with care — do not transpose groups between the two banks.

### KESCO electricity bill — field map (sample layout)
- `document_type`: electricity_kesco
- `name_of_company`: KESCO (fixed issuer)
- `invoice_date`: **Datum / Reading date** in meter/billing block
- `invoice_number`: **Nr. Ref.** on bottom payment strip below barcode (alphanumeric `19……B` shape — read actual text; NOT Customer ID)
- `client_employee_related`: **Emri i konsumatorit / Customer name** line only
- `amount`: **Totali i faturës / Bill amount** row
- `debt`: lines labelled **Borxhi KESCO** / **KESCO + KEK: Borxhi / Debt / Dug**

### Regional water bill — field map (sample layout)
- `document_type`: water_regional
- `name_of_company`: Kompania Rajonale e Ujesjellesit (fixed issuer)
- `invoice_number`: **complete** footer payment ref above barcode (`^F[0-9]+[A-Z]?$`, read twice). NOT short Numri i faturës alone.
- `invoice_date`: reading/billing date in footer
- `client_employee_related`: **Emri i konsumatorit / Customer name** line
- `amount`: **Totali i faturës / Bill Amount** row only
- `debt`: **Borxhi Total / Total Debt / Ukupan Dug** row only

### Albanian bilingual retail invoice — field map (sample layout)
- Buyer block top: **Detajet e blerësit / Buyer detail** (e.g. Borek Solutions) — this is the **client**, NOT `name_of_company`
- `name_of_company`: supplier beside `FATURA - INVOICE` title (e.g. Sarajeva Steak House SH.P.K.)
- `invoice_number`: number on `FATURA - INVOICE ####` line or **Numri i faturës / Invoice number** (NOT Numri Fiskal, NOT bank account)
- `invoice_date`: **Data e faturës / Invoice date**
- `amount`: **Vlera me TVSH / Amount with VAT** or rightmost total in **Gjithësejt vlerat / Total's** row (NOT Vlera pa TVSH)
- `client_employee_related`: **Përshkrimi / Description** contact line if present
- `account_details`: all accounts from **Bankat / Banks** block (TEB, PCB, etc.)

### Pastrimi / KRM waste bill — field map (sample layout)
- `document_type`: waste_pastrimi
- `name_of_company`: Ndermarrja Regjionale e Mbeturinave "Pastrimi" SH.A (fixed issuer)
- `address_of_company`: Rr. Bill Clinton p.n., Prishtinë
- `invoice_number`: **Nr.-No.-Br.** in header (NOT Customer ID near month, NOT NRF/NUI)
- `invoice_date`: **Data-Date-Datum** in header
- `amount`: **Gjithsej borxhi / Total Due** (final payable, includes prior debt)
- `debt`: **Borgji paraprak / Previous due** (informational)
- `account_details`: all banks from Xhirollogaria block
""".strip()

__all__ = ['GOLDEN_EXAMPLES']
