import { useCallback, useEffect, useState } from "react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { DataTable, type Column } from "@/components/ui-finance/DataTable";
import { StatusBadge } from "@/components/ui-finance/StatusBadge";
import { listAuditLogs } from "@/api/audit";
import type { AuditLogEntry, AuditLogFilters } from "@/types/audit";
import {
  AUDIT_ACTION_OPTIONS,
  AUDIT_ENTITY_OPTIONS,
} from "@/types/audit";
import { auditActionLabel, formatDate } from "@/lib/labels";

type AuditRow = AuditLogEntry & { id: number };

export function AuditPage() {
  const [items, setItems] = useState<AuditRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<AuditRow | null>(null);
  const [filters, setFilters] = useState<AuditLogFilters>({
    page: 1,
    limit: 50,
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listAuditLogs(filters);
      setItems(res.items.map((row) => ({ ...row, id: row.id })));
      setTotal(res.total);
    } catch (e) {
      setItems([]);
      setTotal(0);
      setError(e instanceof Error ? e.message : "Could not load audit logs");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: Column<AuditRow>[] = [
    {
      key: "time",
      header: "Time",
      cell: (r) => (
        <span className="tabular-nums text-[12px]">
          {formatDate(r.created_at)}
        </span>
      ),
    },
    {
      key: "action",
      header: "Action",
      cell: (r) => (
        <StatusBadge value={auditActionLabel(r.action)} />
      ),
    },
    {
      key: "entity",
      header: "Entity",
      cell: (r) => (
        <span className="font-mono text-[12px]">
          {r.entity_type} #{r.entity_id}
        </span>
      ),
    },
    {
      key: "user",
      header: "User",
      cell: (r) => (
        <span className="text-[12px] text-muted-foreground">
          {r.user_email ?? (r.user_id != null ? `User #${r.user_id}` : "System")}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Site admin"
        title="Audit logs"
        description="Read-only trail of extractions, edits, approvals, and matching events."
      />

      <div className="grid gap-3 rounded-lg border border-border p-4 sm:grid-cols-2 lg:grid-cols-4">
        <FilterSelect
          label="Action"
          value={filters.action ?? ""}
          options={AUDIT_ACTION_OPTIONS}
          onChange={(value) =>
            setFilters((f) => ({ ...f, page: 1, action: value || undefined }))
          }
        />
        <FilterSelect
          label="Entity type"
          value={filters.entity_type ?? ""}
          options={AUDIT_ENTITY_OPTIONS}
          onChange={(value) =>
            setFilters((f) => ({
              ...f,
              page: 1,
              entity_type: value || undefined,
            }))
          }
        />
        <label className="space-y-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            From
          </span>
          <input
            type="date"
            value={filters.date_from ?? ""}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                page: 1,
                date_from: e.target.value || undefined,
              }))
            }
            className="block h-9 w-full rounded-md border border-input bg-background px-2 text-[13px]"
          />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            To
          </span>
          <input
            type="date"
            value={filters.date_to ?? ""}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                page: 1,
                date_to: e.target.value || undefined,
              }))
            }
            className="block h-9 w-full rounded-md border border-input bg-background px-2 text-[13px]"
          />
        </label>
      </div>

      {error && (
        <p className="text-[13px] text-destructive" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <LoadingSpinner
          centered
          size="md"
          className="text-muted-foreground"
          label="Loading audit logs…"
          containerClassName="py-16"
        />
      ) : (
        <>
          <p className="text-[12px] text-muted-foreground tabular-nums">
            {total} event{total === 1 ? "" : "s"}
          </p>

          <DataTable
            columns={columns}
            rows={items}
            onRowClick={setSelected}
            empty="No audit events found."
          />
        </>
      )}

      {selected && (
        <aside className="rounded-lg border border-border bg-surface-muted/40 p-4">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <p className="text-[13px] font-semibold text-foreground">
                Event #{selected.id}
              </p>
              <p className="text-[12px] text-muted-foreground">
                {auditActionLabel(selected.action)} · {selected.entity_type} #
                {selected.entity_id}
              </p>
            </div>
            <button
              type="button"
              className="text-[12px] text-primary hover:underline"
              onClick={() => setSelected(null)}
            >
              Close
            </button>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            <JsonBlock title="Before" value={selected.before} />
            <JsonBlock title="After" value={selected.after} />
          </div>
        </aside>
      )}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-1">
      <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="block h-9 w-full rounded-md border border-input bg-background px-2 text-[13px]"
      >
        {options.map((opt) => (
          <option key={opt.value || "any"} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function JsonBlock({
  title,
  value,
}: {
  title: string;
  value: Record<string, unknown> | null;
}) {
  return (
    <div>
      <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      <pre className="max-h-64 overflow-auto rounded-md border border-border bg-background p-3 text-[11px] text-foreground">
        {value ? JSON.stringify(value, null, 2) : "—"}
      </pre>
    </div>
  );
}
