"""SaaS / usage-billing invoice rules (e.g. PromptCloud crawl invoices)."""

SAAS_RULES = """
## SaaS / usage billing invoice (classified)

Typical layout: issuer name and address at **top-left** (logo area), **Billed To** block on the left with the client (e.g. Borek Solutions Kosovo LLC), reference fields in the header, line items in the middle, totals at the bottom.

### Issuer vs client (critical)
- `name_of_company` = **issuer** at the top of page 1 (e.g. **PromptCloud Inc**) — NOT the **Billed To** / Bill to / Customer block.
- `address_of_company` = issuer street address under the logo (e.g. Coastal Highway, Lewes, DE, United States).
- **Billed To** contains the client — use it only for `client_employee_related`, never as `name_of_company`.

### Field mapping
| Field | Where to look |
|-------|----------------|
| `invoice_number` | **Invoice Number** in the header (e.g. `0012233`). Copy exactly as printed. |
| `invoice_date` | **Date of Issue** — NOT **Due Date**. US format `MM/DD/YYYY` → convert to `YYYY-MM-DD` (e.g. `08/21/2025` → `2025-08-21`). |
| `amount` | **Amount Due** / **Amount Due (USD)** — the payable total for **this invoice only**. |
| `currency` | From the Amount Due label or `$` symbol → **USD** (do not default to EUR). |
| `category` | **Software** (SaaS, data crawl, API, subscription, cloud services). |
| `debt` | Usually **null** on SaaS invoices. Do not map account-level balances here. |
| `account_details` | IBAN if shown; otherwise Stripe/card payment note (e.g. `Stripe — https://app.promptcloud.com/my/invoices`) or null. |

### Amount traps (read carefully)
1. **Amount Due (USD)** e.g. `$482.87` → this is `amount`. **STOP.**
2. **Pending amount** e.g. `1881.88` → total outstanding on the **account** across invoices — **NOT** `amount` and **NOT** `debt` unless explicitly labelled as prior invoice debt. **IGNORE for amount.**
3. **Subtotal / Total / Amount Paid** — may repeat the same figure; prefer the line explicitly labelled **Amount Due** when present.
4. Line-item **Line Total** (e.g. crawl cost row `$482.87`) may match Amount Due — acceptable only if Amount Due is missing or identical.
5. Never use **Tax** `0.00` or **Amount Paid** `0.00` as `amount`.

### internal_note_description
Summarise the service (e.g. crawl cost for repeat sites), billing month from Description (e.g. August-2025), and **Invoice period** from Notes if present (e.g. `20250720 - 20250819`). Mention record count or site name when visible.

### client_employee_related
- Named contact in Billed To or **Business Point of contact** email line → use the person or company from Billed To.
- If only a company in Billed To with no person → **Borek Solutions**.
""".strip()

__all__ = ["SAAS_RULES"]
