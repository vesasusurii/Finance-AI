"""
Visual scanning order for document OCR.
"""

VISUAL_SCAN_STRATEGY = """
## Visual scanning strategy (follow this order for every document)

1. **Identify document type** — Is it a tax invoice, proforma, utility bill, SaaS receipt, credit note, receipt, or delivery note? This determines where fields appear.
2. **Header zone (top 25%)** — Issuer name, logo, address, contact. This is always `name_of_company` + `address_of_company`.
   On Albanian `FATURA - INVOICE` layouts the buyer block is often at the very top — skip it; read the supplier name from the title area instead.
3. **Reference block** — Usually top-right or below header: invoice number, invoice date, due date.
   On freelancer/timesheet invoices the title line may read `INVOICE 007` with the date beside it — extract the number after INVOICE (short numeric refs like `007` are valid).
4. **Bill-to / client block** — Look for Klienti, Customer, Bill to, Ship to. This block identifies the CLIENT — never use this as `name_of_company`.
5. **Line items table (middle)** — Products/services and their unit prices. Summarise briefly for `internal_note_description`.
6. **Totals block (bottom of line items)** — Sub-total, VAT/TVSH, Grand total, Për pagesë / For payment / Amount due. Extract the FINAL payable amount (see Amount rules).
7. **Payment section (bottom or last page)** — IBAN, bank name, SWIFT/BIC, payment reference. This goes into `account_details`.
8. **Stamps / signatures / footer** — Ignore decorative stamps. If a handwritten amount overrides the printed total, use the handwritten value.
8b. **KESCO electricity bills** — After steps 1–7, scan the **bottom 15%** of the page LAST: payment slip under the **barcode**, label **Nr. Ref.** / **Nr. Ret.** — that value is `invoice_number`. Do not stop at the customer block at the top.
8c. **Regional water bills** — Scan **bottom 10–15%** last. `invoice_number` = **full** payment string above barcode (`^F[0-9]+[A-Z]?$`, usually **12+ digits** after `F`). Read twice; compare reads. Short top-table Bill number is a **prefix only** — never submit it alone.
8d. **Pastrimi / KRM waste bills** — Totals block bottom-right: `amount` = **Gjithsej borxhi / Total Due** (not Monthly Invoice Total or Për pagesë). Capture **all** bank accounts from issuer block.
9. **Multi-page docs** — Check for a page indicator in the top-right corner: "Seite 1/2", "Page 1 of 2", "1/2". If present, the document has multiple pages.
   Page 1 usually has header + invoice number + client block + line items.
   Last page usually has the totals block (Nettobetrag, MwSt, Bruttobetrag) + payment details (IBAN, bank).
   Read ALL pages before finalising `amount` — never use line-item row totals as the invoice amount.
""".strip()

__all__ = ['VISUAL_SCAN_STRATEGY']
