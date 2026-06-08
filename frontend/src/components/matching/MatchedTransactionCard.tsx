import { useEffect, useRef, useState, type ReactNode } from "react";
import { Check, ChevronDown, X } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import {
  formatCurrency,
  formatDate,
  matchStatusLabel,
  reconciliationStatusLabel,
} from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { MatchedTransactionItem } from "./matchedTransactionTypes";

/** Muted action tones aligned with StatusBadge success / danger. */
const approveActionClass =
  "border border-success/30 bg-success/15 text-success hover:bg-success/25";
const rejectActionClass =
  "border border-destructive/30 bg-destructive/15 text-destructive hover:bg-destructive/25";
const neutralActionClass =
  "border border-border bg-secondary text-muted-foreground hover:bg-secondary/80 hover:text-foreground";

function IconActionButton({
  label,
  onClick,
  disabled,
  className,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={cn(
        "inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-colors",
        "focus:outline-none focus:ring-2 focus:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
    >
      {children}
    </button>
  );
}

function DetailField({
  label,
  children,
  mono = false,
}: {
  label: string;
  children: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
        {label}
      </span>
      <span
        className={cn(
          "text-[13px] leading-snug text-foreground",
          mono && "font-mono text-[12px]",
        )}
      >
        {children}
      </span>
    </div>
  );
}

/** ~4 lines at text-[12px] leading-relaxed (0.75rem × 1.625 × 4). */
const COMMENT_CLAMP_PX = 78;

const commentTextClass =
  "whitespace-pre-wrap text-[12px] leading-relaxed text-muted-foreground [overflow-wrap:anywhere]";

function ExpandableComment({
  comment,
  active,
}: {
  comment: string | null;
  /** When false (card collapsed), skip measure — parent is height-clamped. */
  active: boolean;
}) {
  const text = comment?.trim() ?? "";
  const [showFull, setShowFull] = useState(false);
  const [isTruncated, setIsTruncated] = useState(false);
  const measureRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (!active || showFull || !text) {
      setIsTruncated(false);
      return;
    }

    const measure = () => {
      const el = measureRef.current;
      if (!el) return;
      setIsTruncated(el.scrollHeight > COMMENT_CLAMP_PX + 1);
    };

    const raf = requestAnimationFrame(measure);
    const afterExpand = window.setTimeout(measure, 350);
    const el = measureRef.current;
    if (!el) {
      return () => {
        cancelAnimationFrame(raf);
        clearTimeout(afterExpand);
      };
    }

    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(afterExpand);
      observer.disconnect();
    };
  }, [text, showFull, active]);

  useEffect(() => {
    if (!active) setShowFull(false);
  }, [active]);

  if (!text) return <>—</>;

  const clamped = !showFull && isTruncated;

  return (
    <div className="relative">
      <p
        ref={measureRef}
        aria-hidden
        className={cn(
          commentTextClass,
          "pointer-events-none invisible absolute inset-x-0 top-0 -z-10 h-auto w-full",
        )}
      >
        {text}
      </p>
      <p
        className={cn(
          commentTextClass,
          clamped && "max-h-[4.875rem] overflow-hidden",
        )}
      >
        {text}
      </p>
      {clamped ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setShowFull(true);
          }}
          className="mt-0.5 text-[12px] font-medium text-primary hover:underline"
          aria-label="Show full comment"
        >
          ...
        </button>
      ) : null}
      {showFull ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setShowFull(false);
          }}
          className="mt-1 text-[11px] font-medium text-muted-foreground hover:text-foreground hover:underline"
        >
          Show less
        </button>
      ) : null}
    </div>
  );
}

function approvalBadgeLabel(status: MatchedTransactionItem["approvalStatus"]) {
  if (status === "approved") return "Approved";
  if (status === "rejected") return "Rejected";
  return "Pending";
}

export function MatchedTransactionCard({
  item,
  expanded: expandedProp,
  defaultExpanded = false,
  busy = false,
  onExpandedChange,
  onApprove,
  onReject,
}: {
  item: MatchedTransactionItem;
  expanded?: boolean;
  defaultExpanded?: boolean;
  busy?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
  onApprove?: (id: number) => void;
  onReject?: (id: number) => void;
}) {
  const [internalExpanded, setInternalExpanded] = useState(defaultExpanded);
  const expanded = expandedProp ?? internalExpanded;
  const isPending = item.approvalStatus === "pending";

  const setExpanded = (next: boolean) => {
    if (expandedProp === undefined) setInternalExpanded(next);
    onExpandedChange?.(next);
  };

  const toggleExpanded = () => setExpanded(!expanded);

  const invoiceAmountLabel =
    item.invoiceAmount != null
      ? formatCurrency(item.invoiceAmount, item.invoiceCurrency)
      : "—";

  const transactionAmountLabel =
    item.transactionAmount != null
      ? formatCurrency(item.transactionAmount, null)
      : "—";

  return (
    <article
      className={cn(
        "flex h-fit w-full flex-col self-start overflow-hidden rounded-xl border bg-card shadow-sm transition-shadow",
        isPending
          ? "border-border hover:shadow-md"
          : "border-border/60 opacity-90",
      )}
    >
      <header className="flex items-center gap-3 border-b border-border/60 px-4 py-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[14px] font-semibold leading-tight text-foreground">
            {item.companyName}
          </h3>
          {!expanded && (
            <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
              {item.invoiceNumber ?? "—"} · {invoiceAmountLabel}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {isPending ? (
            <>
              <IconActionButton
                label="Approve match"
                disabled={busy}
                onClick={() => onApprove?.(item.id)}
                className={approveActionClass}
              >
                {busy ? (
                  <LoadingSpinner size="sm" />
                ) : (
                  <Check className="h-3.5 w-3.5" />
                )}
              </IconActionButton>
              <IconActionButton
                label="Reject match"
                disabled={busy}
                onClick={() => onReject?.(item.id)}
                className={rejectActionClass}
              >
                <X className="h-3.5 w-3.5" />
              </IconActionButton>
            </>
          ) : (
            <StatusBadge value={approvalBadgeLabel(item.approvalStatus)} />
          )}
          <IconActionButton
            label={expanded ? "Collapse details" : "Expand details"}
            onClick={toggleExpanded}
            className={neutralActionClass}
          >
            <ChevronDown
              className={cn(
                "h-3.5 w-3.5 transition-transform duration-300",
                expanded && "rotate-180",
              )}
            />
          </IconActionButton>
        </div>
      </header>

      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-300 ease-in-out",
          expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="overflow-hidden">
          <div className="border-t border-border/40 bg-surface-muted/30 px-4 py-4">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <StatusBadge
                value={matchStatusLabel(item.matchStatus)}
                tone="success"
              />
              {item.matchStatus === "needs_review" && (
                <StatusBadge
                  value={reconciliationStatusLabel("needs_review")}
                  tone="warning"
                />
              )}
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              <section className="space-y-3">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">
                  Invoice
                </h4>
                <div className="grid gap-3 sm:grid-cols-2">
                  <DetailField label="Invoice #" mono>
                    {item.invoiceNumber ?? "—"}
                  </DetailField>
                  <DetailField label="Amount">{invoiceAmountLabel}</DetailField>
                  <DetailField label="Paid at">
                    <span className="tabular-nums">
                      {formatDate(item.invoiceDate)}
                    </span>
                  </DetailField>
                  <DetailField label="Company">{item.companyName}</DetailField>
                </div>
              </section>

              <section className="space-y-3 md:border-l md:border-border/60 md:pl-6">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">
                  Transaction
                </h4>
                <div className="grid gap-3 sm:grid-cols-2">
                  <DetailField label="Detected invoice #" mono>
                    {item.detectedInvoiceNumbers.length > 0
                      ? item.detectedInvoiceNumbers.join(", ")
                      : "—"}
                  </DetailField>
                  <DetailField label="Amount">
                    {transactionAmountLabel}
                  </DetailField>
                  <DetailField label="Date">
                    <span className="tabular-nums">
                      {formatDate(item.transactionDate)}
                    </span>
                  </DetailField>
                  <DetailField label="Comment">
                    <ExpandableComment
                      comment={item.transactionComment}
                      active={expanded}
                    />
                  </DetailField>
                </div>
              </section>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}
