import {
  formatCurrency,
  formatOriginalCurrencySubtitle,
} from "@/lib/labels";
import type { Invoice } from "@/types/invoice";

export function InvoiceAmountDisplay({
  invoice,
  className = "text-[13px] font-medium text-foreground",
  subtitleClassName = "mt-0.5 text-[11px] text-muted-foreground",
}: {
  invoice: Pick<
    Invoice,
    "amount" | "currency" | "original_amount" | "original_currency"
  >;
  className?: string;
  subtitleClassName?: string;
}) {
  const subtitle = formatOriginalCurrencySubtitle(invoice);

  return (
    <div>
      <div className={`tabular-nums ${className}`}>
        {formatCurrency(
          invoice.amount != null ? Number(invoice.amount) : null,
          invoice.currency ?? "EUR",
        )}
      </div>
      {subtitle ? <p className={subtitleClassName}>{subtitle}</p> : null}
    </div>
  );
}
