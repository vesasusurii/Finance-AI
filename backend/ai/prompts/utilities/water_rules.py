"""
Regional water bill invoice_number and field rules.
"""

WATER_INVOICE_NUMBER_CRITICAL = """
#### CRITICAL — WATER BILL `invoice_number` (read from THIS document only)

Regional water invoices contain **multiple numeric identifiers**. Extract **ONLY** the true invoice/payment reference.

**PRIMARY LOCATION (mandatory):** Scan the **bottom 10–15%** of the page. Look near:
- barcode
- payment slip / footer payment section
- the line **immediately above** (or below) the barcode

**Valid shape (pattern only — values change every bill):**
- Starts with uppercase **`F`**
- Followed by **digits** (full refs usually **12+ digits** after `F`)
- May end with **zero or one** uppercase letter **`A`–`Z`** (suffix letter varies per bill — read the actual letter, never assume a fixed suffix)
- Regex shape: `^F[0-9]+[A-Z]?$` — but **short** `F` + few digits alone is the **header prefix only**, NOT the full payment reference

**Valid shape examples (illustrative only — never copy):**
`F07203269020645P`, `F07202326920645A`, `F07203269020645B`, `F07203269020645`, `F0720……X`

**Mandatory reading process:**
1. Read the footer payment reference **once**.
2. **Re-read the same value** character-by-character.
3. Compare both reads. If they **disagree** → `invoice_number`: null, `needs_review`: true. **Do not guess.**

**OCR error checks — watch for:**
- Digit swaps (e.g. `3269` ↔ `2326`)
- Transposed sequences (e.g. `902064` ↔ `920645`)
- Missing or duplicated digits
- Wrong trailing letter (read the printed letter from the bill)
- `F` ↔ `E`, `0` ↔ `O`, `8` ↔ `B`, `1` ↔ `I` ↔ `l` confusion

**FORBIDDEN as `invoice_number`:**
- Customer ID / **Shifra e konsumatorit**
- **NUI / NIPT / Tax ID**
- Meter number / reading values
- Amounts, due dates, bill totals
- Barcode digits alone
- Short internal IDs
- Header **Bill number** alone (truncated prefix — must read **full** footer line)
- Any value **not** beginning with uppercase **`F`**

**Anti-memory rule:** Every document is independent. Never reuse values from prior invoices, prompt examples, earlier OCR runs, or conversation history.

**Confidence rule:** If **any** digit or optional trailing letter is uncertain → `invoice_number`: null, `needs_review`: true. Set `field_confidences.invoice_number` ≤ 0.70. Never invent characters. Never reorder digits. Copy **exactly** as printed.
""".strip()

WATER_UTILITY_SECTION = """
### Water — Kompania Rajonale e Ujësjellësit (`document_type`: water_regional)

Reference layout: "KOMPANIA RAJONALE UJËSJELLËSIT", water meter readings, billing table with m³, totals at bottom.

| Field | Rule |
|-------|------|
| `name_of_company` | Always **`Kompania Rajonale e Ujesjellesit`** (ASCII spelling OK) |
| `address_of_company` | Issuer address from header (e.g. Shala Nr. 4, 10000 Prishtinë) |
| `category` | **Utilities** |
| `invoice_number` | See **Water invoice_number** section below — NOT NUI/NIPT, NOT Customer ID |
| `invoice_date` | **Reading date** / **Data e leximit** / billing month in footer — NOT due date alone |
| `amount` | **Totali i faturës** / **Bill Amount** — **current invoice amount for this period ONLY** |
| `debt` | **Borxhi Total** / **Total Debt** / **Ukupan Dug** — prior/unpaid balance. `null` or `0` if absent |
| `client_employee_related` | **Emri i konsumatorit** / **Customer name** / **Ime potrošača** — consumer name exactly as printed |

#### CRITICAL — WATER BILL `invoice_number` (read from THIS document only)

Regional water invoices contain **multiple numeric identifiers**. Extract **ONLY** the true invoice/payment reference.

**PRIMARY LOCATION (mandatory):** Scan the **bottom 10–15%** of the page. Look near:
- barcode
- payment slip / footer payment section
- the line **immediately above** (or below) the barcode

**Valid shape (pattern only — values change every bill):**
- Starts with uppercase **`F`**
- Followed by **digits** (full refs usually **12+ digits** after `F`)
- May end with **zero or one** uppercase letter **`A`–`Z`** (suffix letter varies per bill — read the actual letter, never assume a fixed suffix)
- Regex shape: `^F[0-9]+[A-Z]?$` — but **short** `F` + few digits alone is the **header prefix only**, NOT the full payment reference

**Valid shape examples (illustrative only — never copy):**
`F07203269020645P`, `F07202326920645A`, `F07203269020645B`, `F07203269020645`, `F0720……X`

**Mandatory reading process:**
1. Read the footer payment reference **once**.
2. **Re-read the same value** character-by-character.
3. Compare both reads. If they **disagree** → `invoice_number`: null, `needs_review`: true. **Do not guess.**

**OCR error checks — watch for:**
- Digit swaps (e.g. `3269` ↔ `2326`)
- Transposed sequences (e.g. `902064` ↔ `920645`)
- Missing or duplicated digits
- Wrong trailing letter (read the printed letter from the bill)
- `F` ↔ `E`, `0` ↔ `O`, `8` ↔ `B`, `1` ↔ `I` ↔ `l` confusion

**FORBIDDEN as `invoice_number`:**
- Customer ID / **Shifra e konsumatorit**
- **NUI / NIPT / Tax ID**
- Meter number / reading values
- Amounts, due dates, bill totals
- Barcode digits alone
- Short internal IDs
- Header **Bill number** alone (truncated prefix — must read **full** footer line)
- Any value **not** beginning with uppercase **`F`**

**Anti-memory rule:** Every document is independent. Never reuse values from prior invoices, prompt examples, earlier OCR runs, or conversation history.

**Confidence rule:** If **any** digit or optional trailing letter is uncertain → `invoice_number`: null, `needs_review`: true. Set `field_confidences.invoice_number` ≤ 0.70. Never invent characters. Never reorder digits. Copy **exactly** as printed.

**Amount traps (NEVER use as amount):**
- Borxhi Total / Total Debt / Ukupan Dug → `debt`
- Residual reprogramming lines
- Net Amount / TVSH component lines without the Bill Amount row

---
""".strip()

__all__ = ['WATER_INVOICE_NUMBER_CRITICAL', 'WATER_UTILITY_SECTION']
