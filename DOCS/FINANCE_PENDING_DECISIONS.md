# Finance pending decisions (human sign-off)

Engineering can implement any row below once Finance chooses an option. Until then, defaults in the product are as listed.

Source: [10. Excel-File-Formats.md](./10. Excel-File-Formats.md) §12 and §Phase 5, [DOCS/README.md](./README.md) audit.

---

## Blocked on Finance

| # | Decision | Options | Current product behaviour |
|---|----------|---------|-------------------------|
| 1 | **Monthly report download format** | Excel only · PDF only · Both | Period report is **Excel** via `/api/export/period-report-excel`; UI on **Reports**. PDF not built. |
| 2 | **Currency in official 12-column export** | Add column · Keep DB-only · Embed in Amount text | **DB-only** (`currency` on `invoices`); export uses amount number without separate currency column. |
| 3 | **Legacy master Excel import** | One-time migration tool (Phase 2) · Manual re-entry · Defer | **Not implemented**; invoices enter via PDF/image upload or email ingest only. |
| 4 | Date format in export cells | `DD.MM.YYYY` · `YYYY-MM-DD` | Confirm with sample workbook |
| 5 | Rows in export when `needs_review` | Include all · Approved only · Toggle | Export filters on **Reports** support `review_status`; default is unfiltered |
| 6 | Extra columns on export | AI confidence · Match status · Review status · Off | **Off** (12 official columns only) |
| 7 | Bank upload file types | `.xlsx` only · `.xls` + `.xlsx` | **Both** supported today |
| 8 | Export sheet name | `Purchase Invoices` · Match legacy tab name | **`Purchase Invoices`** |
| 9 | Multi-currency display in Amount | Separate currency column · Always EUR in amount | Per decision #2 |

---

## Recommended sign-off meeting (30 min)

1. Walk through **Reports** period summary + filtered purchase export (already in app).
2. Decide **#1** (monthly format) and **#2** (currency column) — highest impact on daily Excel workflow.
3. Decide whether **#3** legacy import is worth a Phase 2 budget or is abandoned.
4. Confirm **#4–#9** against a sample Finance workbook.

---

## After sign-off — engineering tickets

| Decision | Likely work |
|----------|-------------|
| Monthly PDF | Report template + `GET /api/export/period-report-pdf` |
| Currency column | Extend `_PURCHASE_INVOICE_HEADERS` in `excel_service.py` + Finance approval of column order |
| Legacy import | One-off script: map legacy sheet columns → `invoices` + validation report |

---

## Not blocked (already shipped or engineering-owned)

- Email ingest via n8n — [PHASE_A_STABILISATION.md](./PHASE_A_STABILISATION.md)
- Documents tabs and filters
- Bank statement import and re-parse
- Partially paid / split payments (matching + Documents debt display)
- Filtered Excel export on **Reports** page
