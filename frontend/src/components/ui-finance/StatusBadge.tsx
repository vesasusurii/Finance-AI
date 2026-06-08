import { cn } from "@/lib/utils";

type Tone = "neutral" | "info" | "success" | "warning" | "danger" | "primary";

const toneClass: Record<Tone, string> = {
  neutral: "bg-secondary text-muted-foreground border-border",
  info: "bg-accent text-primary border-accent",
  success: "bg-success/15 text-success border-success/30 dark:bg-success/20 dark:border-success/40",
  warning: "bg-warning/15 text-warning border-warning/30 dark:bg-warning/20 dark:border-warning/40",
  danger: "bg-destructive/15 text-destructive border-destructive/30 dark:bg-destructive/20 dark:border-destructive/40",
  primary: "bg-accent text-primary border-accent",
};

const map: Record<string, Tone> = {
  Pending: "neutral",
  pending: "neutral",
  Processing: "info",
  processing: "info",
  Processed: "success",
  processed: "success",
  Failed: "danger",
  failed: "danger",
  "Needs Review": "warning",
  "Needs review": "warning",
  "Manual review required": "danger",
  manual_review: "danger",
  "Requires Immediate Review": "warning",
  needs_review: "warning",
  Approved: "success",
  approved: "success",
  Rejected: "danger",
  rejected: "danger",
  Matched: "success",
  matched: "success",
  "Partially Paid": "info",
  "Partially paid": "info",
  partially_matched: "info",
  suggested: "warning",
  Suggested: "warning",
  Unmatched: "warning",
  unmatched: "warning",
  Multiple: "warning",
  Active: "success",
  Invited: "info",
  Disabled: "neutral",
  Ready: "success",
  Generating: "info",
};

export function StatusBadge({ value, tone }: { value: string; tone?: Tone }) {
  const t = tone ?? map[value] ?? "neutral";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        toneClass[t]
      )}
    >
      <span className={cn(
        "h-1.5 w-1.5 rounded-full",
        t === "success" && "bg-success",
        t === "warning" && "bg-warning",
        t === "danger" && "bg-destructive",
        t === "info" && "bg-primary",
        t === "primary" && "bg-primary",
        t === "neutral" && "bg-muted-foreground/60",
      )} />
      {value}
    </span>
  );
}
