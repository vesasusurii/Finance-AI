import { Search, SlidersHorizontal } from "lucide-react";
import type { ReactNode } from "react";

export function FilterBar({
  search,
  onSearch,
  placeholder,
  children,
  right,
}: {
  search?: string;
  onSearch?: (v: string) => void;
  placeholder?: string;
  children?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
      <div className="relative w-full sm:w-auto">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          value={search ?? ""}
          onChange={(e) => onSearch?.(e.target.value)}
          placeholder={placeholder ?? "Search…"}
          className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-3 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-ring focus:outline-none sm:w-[280px]"
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {children}
        <button className="flex h-8 items-center gap-1.5 rounded-md border border-input bg-background px-2.5 text-[12px] font-medium text-foreground hover:bg-secondary">
          <SlidersHorizontal className="h-3.5 w-3.5" /> Filters
        </button>
        {right ? <div className="flex items-center gap-2 sm:ml-auto">{right}</div> : null}
      </div>
    </div>
  );
}

export function FilterChip({ label, count, active }: { label: string; count?: number; active?: boolean }) {
  return (
    <button
      className={
        "flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-[12px] font-medium transition-colors " +
        (active
          ? "border-primary bg-accent text-primary"
          : "border-input bg-background text-foreground hover:bg-secondary")
      }
    >
      {label}
      {typeof count === "number" && (
        <span className="rounded bg-secondary px-1 text-[10px] tabular-nums text-muted-foreground">{count}</span>
      )}
    </button>
  );
}
