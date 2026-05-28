"""
Regional waste (Pastrimi / KRM) invoice extraction rules.

Ndërmarrja Regjionale e Mbeturinave "Pastrimi" SH.A — waste collection bills.
"""

PASTRIMI_UTILITY_SECTION = """
### Regional waste — Pastrimi (`document_type`: waste_pastrimi)

Reference layout: trilingual header "FATURA - INVOICE - RACUN", customer block (business name, owner, street), issuer top-right with bank list, line items (Lokali / open area), totals block bottom-right.

| Field | Rule |
|-------|------|
| `name_of_company` | Always **`Ndermarrja Regjionale e Mbeturinave "Pastrimi" SH.A`** — never the customer (Borek Solutions, etc.) |
| `address_of_company` | **`Rr. Bill Clinton p.n., Prishtinë`** (issuer address from header) |
| `category` | **Utilities** |
| `invoice_number` | **Nr.-No.-Br.** / **Nr.** / **Broj** in the **invoice header** (top green block) — numeric reference on this document (length varies). NOT Customer ID beside month, NOT NRF/NRB/NUI/NIPT |
| `invoice_date` | **Data-Date-Datum** / **Date** in header — NOT month label alone |
| `amount` | **`Gjithsej borxhi` / `Total Due` / `Ukupan dug`** ONLY — **final amount Finance must pay** (includes current charges **and** any previous outstanding balance on this bill) |
| `debt` | **`Borgji paraprak` / `Previous due` / `Prethodni dug`** — prior balance line only (informational). `null` if absent |
| `account_details` | **All** bank accounts from **Xhirollogaria / Bank Account / Ziro Racun** block — list every bank + account number (NLB, TEB, BPB, BKT, BE, RBKO, PCB, etc.), joined with ` || ` |
| `client_employee_related` | **Emri i Pronarit / Owner's Name** or contact in customer block; if only business name → **`Borek Solutions`** per default rule |

#### Pastrimi `amount` — CRITICAL (overrides generic "Për pagesë" rule)

Finance pays the **Total Due** on this bill type, not a monthly subtotal alone.

**Use for `amount` (mandatory):**
- **Gjithsej borxhi** / **Total Due** / **Ukupan dug** — bottom totals block, right side

**NEVER use for `amount`:**
- **Vlera mujore e faturës** / **Monthly Invoice Total** / **Mesecna vrednost racuna**
- **Për pagesë** / **For payment** / **Za naplatu** (current-period portion only — wrong when prior debt exists)
- Line-item **Total** / **Shuma** column values (Lokali, TVSH row, etc.)
- **Kamata** / **Interest** alone

When **Total Due** and **Previous due** and **For payment** all appear: `amount` = **Total Due** only; put **Previous due** in `debt`.

#### Pastrimi `invoice_number` — pattern and location

- **Label:** **Nr.-No.-Br.** / **Nr.** at top of invoice (near FATURA / INVOICE title).
- Extract the **invoice reference** on that line — typically numeric (shape varies per bill).
- **FORBIDDEN as `invoice_number`:**
  - Customer / business reference beside **Muaji-Month** (e.g. ID printed near month — payment portal ID, not invoice #)
  - **NRF**, **NRB**, **NUI**, **NIPT**, **Nr. Unik**, **Nr. TVSH** (tax / registration numbers)
  - Line item numbers (1, 2, 3…)
  - e-Kosova payment hint numbers if they duplicate customer ID

**Amount traps (NEVER use as amount):**
- Monthly invoice total row
- For payment row when Total Due is also shown
- VAT (TVSH) or interest (Kamata) lines alone

---
""".strip()

__all__ = ["PASTRIMI_UTILITY_SECTION"]
