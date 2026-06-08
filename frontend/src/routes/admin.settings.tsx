import { useCallback, useEffect, useMemo, useState } from "react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { PageHeader } from "@/components/ui-finance/PageHeader";
import { getSettings } from "@/api/admin";
import type { SettingItem } from "@/types/admin";

export function SettingsPage() {
  const [items, setItems] = useState<SettingItem[]>([]);
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getSettings();
      setItems(res.items);
      setNote(res.note);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const groups = useMemo(() => {
    const map = new Map<string, SettingItem[]>();
    for (const item of items) {
      const list = map.get(item.group) ?? [];
      list.push(item);
      map.set(item.group, list);
    }
    return Array.from(map.entries());
  }, [items]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Site admin"
        title="Settings"
        description="Read-only view of runtime configuration. Secrets are managed via environment variables."
      />

      {error && (
        <p className="text-[13px] text-destructive" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <LoadingSpinner centered className="text-muted-foreground" />
      ) : (
        <>
          <p className="text-[12px] text-muted-foreground">{note}</p>
          <div className="space-y-6">
            {groups.map(([group, groupItems]) => (
              <section key={group} className="space-y-3">
                <h2 className="text-[14px] font-semibold text-foreground">
                  {group}
                </h2>
                <div className="overflow-hidden rounded-lg border border-border">
                  <table className="w-full text-[13px]">
                    <tbody>
                      {groupItems.map((item) => (
                        <tr
                          key={item.key}
                          className="border-b border-border last:border-0"
                        >
                          <td className="w-[40%] px-4 py-3 text-muted-foreground">
                            {item.label}
                          </td>
                          <td className="px-4 py-3 font-medium text-foreground">
                            {item.value}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
