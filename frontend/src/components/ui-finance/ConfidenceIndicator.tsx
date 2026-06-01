import { cn } from "@/lib/utils";

export function ConfidenceIndicator({ value }: { value: number }) {
  if (!value) return <span className="text-[12px] text-muted-foreground">—</span>;
  const pct = Math.round(value * 100);
  const tone =
    pct >= 90 ? "success" : pct >= 70 ? "warning" : "danger";
  const bar =
    tone === "success" ? "bg-success" :
    tone === "warning" ? "bg-warning" : "bg-destructive";

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-secondary">
        <div className={cn("h-full rounded-full", bar)} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums text-[12px] font-medium text-foreground">{pct}%</span>
    </div>
  );
}
