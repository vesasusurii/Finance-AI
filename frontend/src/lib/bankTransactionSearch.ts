import type { BankTransaction } from "@/types/bank";
import { formatDate } from "@/lib/labels";
import type { Invoice } from "@/types/invoice";

function normalise(s: string | null | undefined): string {
  return (s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
}

function amountClose(a: number, b: number, tolerance = 0.02): boolean {
  return Math.abs(Math.abs(Number(a)) - Math.abs(Number(b))) <= tolerance;
}

/** Significant words: skip short legal suffixes that rarely appear in bank comments. */
const NOISE_WORDS = new Set(["llc", "ltd", "inc", "gmbh", "shpk", "srl", "bv", "nv", "ag", "sa", "spa"]);

function companyTokens(company: string): string[] {
  return normalise(company)
    .split(" ")
    .filter((t) => t.length >= 3 && !NOISE_WORDS.has(t));
}

function companyMatches(txn: BankTransaction, company: string): boolean {
  const needle = normalise(company);
  if (!needle) return true;
  const haystack = normalise(
    [txn.comment, txn.transaction_type].filter(Boolean).join(" "),
  );
  if (haystack.includes(needle)) return true;
  const tokens = companyTokens(company);
  // Match if ANY significant token from the company name appears in the bank text.
  return tokens.length > 0 && tokens.some((tok) => haystack.includes(tok));
}

function amountMatches(txn: BankTransaction, amount: number): boolean {
  return (
    (txn.debited_amount != null && amountClose(txn.debited_amount, amount)) ||
    (txn.credited_amount != null && amountClose(txn.credited_amount, amount))
  );
}

function invoiceNumberMatches(
  txn: BankTransaction,
  display: string | null,
  normalized: string | null,
): boolean {
  const matchKey = normalise(normalized ?? display ?? "");
  if (matchKey) {
    const inDetected = txn.detected_invoice_numbers.some(
      (n) => normalise(n) === matchKey,
    );
    if (inDetected) return true;
  }
  const displayNeedle = normalise(display ?? "");
  if (!displayNeedle && !matchKey) return true;
  if (displayNeedle && normalise(txn.comment).includes(displayNeedle)) return true;
  return Boolean(matchKey && normalise(txn.comment).includes(matchKey));
}

function freeTextMatches(txn: BankTransaction, query: string): boolean {
  const q = normalise(query);
  if (!q) return true;
  const blob = [
    String(txn.id),
    txn.comment,
    txn.transaction_type,
    txn.transaction_date,
    txn.transaction_date ? formatDate(txn.transaction_date) : null,
    txn.reconciliation_status,
    ...txn.detected_invoice_numbers,
    txn.debited_amount != null ? String(txn.debited_amount) : null,
    txn.credited_amount != null ? String(txn.credited_amount) : null,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return blob.includes(q);
}

export type AutoSearchHints = {
  company: string | null;
  amount: number | null;
  invoiceNumber: string | null;
  invoiceNumberNormalized: string | null;
};

export function hintsFromInvoice(invoice: Invoice): AutoSearchHints {
  const rawAmount = invoice.amount;
  const amount = rawAmount != null ? Number(rawAmount) : null;
  return {
    company: invoice.name_of_company?.trim() || null,
    amount: amount != null && !isNaN(amount) ? amount : null,
    invoiceNumber: invoice.invoice_number?.trim() || null,
    invoiceNumberNormalized:
      invoice.invoice_number_normalized?.trim() ||
      invoice.invoice_number?.trim() ||
      null,
  };
}

/** Returns 0–3: one point per hint that matches. */
export function scoreHints(txn: BankTransaction, hints: AutoSearchHints): number {
  let score = 0;
  if (hints.company && companyMatches(txn, hints.company)) score++;
  if (hints.amount != null && amountMatches(txn, hints.amount)) score++;
  if (
    (hints.invoiceNumber || hints.invoiceNumberNormalized) &&
    invoiceNumberMatches(
      txn,
      hints.invoiceNumber,
      hints.invoiceNumberNormalized,
    )
  ) {
    score++;
  }
  return score;
}

/** Returns true when the transaction matches at least one non-null hint (OR logic). */
export function matchesHints(txn: BankTransaction, hints: AutoSearchHints): boolean {
  const hasAnyHint =
    hints.company ||
    hints.amount != null ||
    hints.invoiceNumber ||
    hints.invoiceNumberNormalized;
  if (!hasAnyHint) return true;
  return scoreHints(txn, hints) > 0;
}

export function matchesFreeText(txn: BankTransaction, query: string): boolean {
  return freeTextMatches(txn, query);
}

export function hintsLabel(hints: AutoSearchHints): string {
  return [
    hints.company,
    hints.invoiceNumber,
    hints.amount != null ? String(hints.amount) : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

/**
 * Returns the list of lowercase strings to highlight inside bank transaction
 * fields when the search bar is auto-filled from an invoice.
 */
export function getHighlightTerms(hints: AutoSearchHints): string[] {
  const terms: string[] = [];

  if (hints.company) {
    terms.push(...companyTokens(hints.company));
  }

  if (hints.invoiceNumber) {
    const n = normalise(hints.invoiceNumber);
    if (n) terms.push(n);
  }
  if (hints.invoiceNumberNormalized) {
    const n = normalise(hints.invoiceNumberNormalized);
    if (n && !terms.includes(n)) terms.push(n);
  }

  if (hints.amount != null) {
    const num = Number(hints.amount);
    if (!isNaN(num)) {
      const plain = num.toFixed(2);                  // "499.99"
      const comma = plain.replace(".", ",");         // "499,99"
      terms.push(plain, comma);
    }
  }

  return [...new Set(terms.filter(Boolean))];
}
