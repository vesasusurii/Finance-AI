"""
Multi-language label glossary for invoice field detection.
"""

MULTILINGUAL_LABELS = """
## Multi-language label glossary (Albanian / English / Serbian / German)

| Concept                | Albanian              | English                        | Serbian              | German              |
|------------------------|-----------------------|--------------------------------|----------------------|---------------------|
| Invoice                | Faturë / FATURA       | Invoice / Tax Invoice          | Račun / FAKTURA      | Rechnung            |
| Invoice number         | Fatura Nr. / Nr.      | Invoice No. / Invoice Ref / Bill No. | Br. fakture   | Rechnungsnummer / **Belegnummer** |
| Date                   | Data / Datë           | Date / Issue date              | Datum                | **Datum**           |
| Due date               | Data e maturimit      | Due date / Payment due         | Datum dospeća        | **Fälligkeitsdatum** |
| Client / Bill-to       | Klienti / Blerësi     | Client / Customer / Bill to    | Klijent / Kupac      | Kunde / Rechnungsempfänger |
| Supplier / Issuer      | Furnitori / Lëshuesi  | Supplier / Vendor / From       | Dobavljač / Prodavac | Lieferant / Anbieter |
| Amount due (pay this)  | Për pagesë            | For payment / Amount due / Total payable | Za naplatu | **Zahlbetrag** / Zu zahlen / Gesamtbetrag brutto |
| Sub-total              | Nëntotal              | Sub-total / Net                | Iznos bez PDV-a      | **Nettobetrag** / Summe netto |
| VAT                    | TVSH                  | VAT / Tax                      | PDV                  | **MwSt** / USt / Umsatzsteuer |
| Total (may incl. old debt) | Gjithsej borgji / Total Due | Total due / Balance due  | Ukupno duguje    | Gesamtbetrag        |
| Grand total w/ VAT     | Gjithsej me TVSH / **Vlera me TVSH** / **Gjithësejt vlerat** | Total incl. VAT / **Amount with VAT** / Total's | Ukupno sa PDV-om     | **Bruttobetrag** / Gesamtbetrag inkl. MwSt |
| Sub-total (no VAT)     | **Vlera pa TVSH**     | Amount without VAT             | Iznos bez PDV-a      | Nettobetrag         |
| VAT component only     | **Vlera e TVSH'së**   | Amount of VAT                  | PDV                  | MwSt / USt          |
| Buyer block            | **Detajet e blerësit** / Blerësi | Buyer detail / Bill to   | Kupac                | Rechnungsempfänger  |
| Fiscal / tax ID        | **Numri Fiskal** / NUI / NRF | Fiscal Number / Business No | PIB              | Steuernummer ← NEVER invoice# |
| Bank account / IBAN    | Xhirollogaria / IBAN  | Bank account / IBAN            | Žiro račun / IBAN    | **Bankverbindung** / IBAN |
| Tax ID (never invoice#) | NUI / UNI / NRF / NIPT | VAT No. / EIN / Tax Reg.    | PIB / Matični broj   | **Steuernummer** / USt-IdNr. |
| Payment reference      | Referenca e pagesës   | Payment ref / Reference no.    | Poziv na broj        | Verwendungszweck    |
| Description            | Përshkrimi / Shërbimi | Description / Service          | Opis / Usluga        | **Beschreibung** / Artikelnr. |
| Quantity               | Sasia / Njësi         | Qty / Quantity / Units         | Količina             | **Menge** / Stück   |
| Customer number        | —                     | Customer No.                   | Broj klijenta        | **Kundennr.** ← IGNORE, not invoice# |
| Customer reference     | —                     | Customer Ref.                  | —                    | **Kundenreferenz** ← IGNORE, not invoice# |
| Page indicator         | —                     | Page X of Y                    | —                    | **Seite X/Y** ← signals multi-page doc |
| Reading date           | Data e leximit        | Reading date                   | Datum čitanja        | Ablesedatum         |
| Bill amount (current)  | Totali i faturës      | Bill amount / Iznos računa     | Ukupan račun         | Rechnungsbetrag     |
| Outstanding debt       | Borxhi / Borgji       | Debt / KESCO debt / Total debt | Ukupan dug           | Gesamtschuld        |
| Customer name          | Emri i konsumatorit   | Customer name                  | Ime potrošača        | Kundenname          |
| Customer ID            | Shifra e konsumatorit | Customer ID / Costumer ID      | Šifra potrošača      | — (NOT invoice #)   |
| Payment ref (KESCO)    | Nr. Ref. / Nr. Ref    | Reference / Nr. Ret. (OCR)     | —                    | — (KESCO invoice # ONLY) |
| Bill number (water)    | Numri i faturës       | Bill number / Broj računa      | —                    | Starts with **F** (NOT Customer ID) |
| Payment ref (water)    | —                     | Barcode line above footer      | —                    | Full **`F`+digits+one letter** (suffix letter varies) — NOT short bill # |

### Critical German invoice field mapping
- **Belegnummer** → `invoice_number` (this IS the invoice / document number)
- **Rechnungsnummer** → `invoice_number`
- **Datum** (in the reference block, top-right) → `invoice_date`
- **Fälligkeitsdatum** → due date, NOT `invoice_date`
- **Kundennr.** → customer number, NEVER `invoice_number`
- **Kundenreferenz** → customer's internal reference, NEVER `invoice_number`
- **Nettobetrag / Summe netto** → sub-total BEFORE VAT, NOT `amount`
- **MwSt / USt** → VAT component, NOT `amount`
- **Bruttobetrag / Gesamtbetrag inkl. MwSt / Zahlbetrag** → the final `amount` to pay
""".strip()

__all__ = ['MULTILINGUAL_LABELS']
