"""
KESCO electricity utility extraction rules.
"""

KESCO_UTILITY_SECTION = """
### Electricity — KESCO (`document_type`: electricity_kesco)

Reference layout: trilingual bill "Fatura - Bill - Račun", KESCO header, customer block top-left, meter table centre, totals lower section.

| Field | Rule |
|-------|------|
| `name_of_company` | Always **`KESCO`** — never the customer name |
| `address_of_company` | KESCO issuer address from header (e.g. Rr. Garibaldi 5, Prishtinë) |
| `category` | **Utilities** |
| `invoice_date` | **Reading date** only: **Data e leximit** / **Reading date** / **Datum**. NOT due date (Data e faturimit / Due date / Rok uplate) |
| `invoice_number` | See **KESCO invoice_number** section below — NOT Customer ID |
| `amount` | **Totali i faturës** / **Bill amount** / **Iznos računa** — **current month charge ONLY** |
| `debt` | **Borxhi KESCO** / **KESCO debt** / **KESCO dug** and/or **KESCO + KEK: Borxhi / Debt / Dug** — outstanding balance only. `null` or `0` if absent |
| `client_employee_related` | **Emri i konsumatorit** / **Customer name** / **Ime potrošača** — read the consumer name on the line directly under those labels |

#### KESCO `invoice_number` — pattern and location (dynamic)
- **Where to look (mandatory):** the **payment slip at the very bottom** of the bill — **below the horizontal barcode**, in the **Pagosa / Payment / Uplata** block. This is the **last** text block on the page. Scroll to the bottom before setting `invoice_number`.
- **Label:** **Nr. Ref.** / **Nr. Ref** / **Nr. Ret.** (common OCR misread) / **Reference** — on the same line as the reference value, **not** on the due-date line (**Afati i pagesës / Due Date**).
- **Format shape (pattern only):** long **alphanumeric** payment reference (often starts with `19`, many digits, often ends with a **letter** such as `B` — shape `Nr. Ref. 19……B`). Length typically **12–20 characters**. Actual value **varies per bill**.
- Extract the **complete string immediately after "Nr. Ref."** (or after the colon) on that bottom line — character by character, including any trailing letter.
- **FORBIDDEN as `invoice_number` (common model errors):**
  - **Shifra e konsumatorit** / **Customer ID** / **Costumer ID** / values with prefix **DPR** (numeric-only, ~8–9 digits)
  - Any **pure numeric** code from the **top-left customer box** (meter table header area)
  - Feeder / route codes, top-right reference numbers, barcode digits alone
  - **Due date** strings (e.g. `2026-02-13`) from **Afati i pagesës / Due Date / Rok uplate**
- If you only find numeric IDs in the header and no bottom **Nr. Ref.** value → set `invoice_number` to **null** and `needs_review` true (do not guess).

**Customer name traps (NEVER use as client_employee_related):**
- KESCO / KESCO sh.a. (issuer)
- Customer ID numbers (numeric-only ID in the customer block)
- Address-only text (Rr. Lorenc Antoni…) without the labelled customer name
- Route / meter technical codes

**Amount traps (NEVER use as amount):**
- Borxhi KESCO / KESCO+KEK debt lines → those go in `debt`
- Neto / TVSH lines alone
- Combined total that includes old debt

---
""".strip()

__all__ = ['KESCO_UTILITY_SECTION']
