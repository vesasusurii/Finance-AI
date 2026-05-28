import { cn } from "@/lib/utils";

type Tone = "neutral" | "info" | "success" | "warning" | "danger" | "primary";

const toneClass: Record<Tone, string> = {
  neutral: "bg-secondary text-muted-foreground border-border",
  info: "bg-accent text-primary border-accent",
  success: "bg-[oklch(0.96_0.05_145)] text-success border-[oklch(0.88_0.08_145)]",
  warning: "bg-[oklch(0.97_0.06_75)] text-[oklch(0.45_0.13_60)] border-[oklch(0.9_0.08_75)]",
  danger: "bg-[oklch(0.97_0.04_27)] text-destructive border-[oklch(0.9_0.07_27)]",
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
  "Requires Immediate Review": "warning",
  needs_review: "warning",
  Approved: "success",
  approved: "success",
  Rejected: "danger",
  rejected: "danger",
  Matched: "success",
  matched: "success",
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
