import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FileText,
  GitCompareArrows,
  Landmark,
  ClipboardCheck,
  Upload,
} from "lucide-react";
import { listInvoices } from "@/api/invoices";
import type { Invoice } from "@/types/invoice";
import { formatCurrency } from "@/lib/labels";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";

const QUICK_LINKS = [
  { id: "upload", label: "Upload invoices", href: "/", icon: Upload },
  { id: "documents", label: "Documents", href: "/documents", icon: FileText },
  {
    id: "bank",
    label: "Bank statements",
    href: "/bank-statements",
    icon: Landmark,
  },
  { id: "matching", label: "Matching", href: "/matching", icon: GitCompareArrows },
  {
    id: "review",
    label: "Manual review",
    href: "/manual-review",
    icon: ClipboardCheck,
  },
] as const;

type GlobalSearchDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function GlobalSearchDialog({
  open,
  onOpenChange,
}: GlobalSearchDialogProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setInvoices([]);
    }
  }, [open]);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setInvoices([]);
      return;
    }

    const timer = window.setTimeout(() => {
      setSearching(true);
      void listInvoices({ search: trimmed, limit: 8 })
        .then((res) => setInvoices(res.items))
        .catch(() => setInvoices([]))
        .finally(() => setSearching(false));
    }, 250);

    return () => window.clearTimeout(timer);
  }, [query]);

  const go = useCallback(
    (href: string) => {
      onOpenChange(false);
      navigate(href);
    },
    [navigate, onOpenChange],
  );

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput
        placeholder="Search invoices, vendors, invoice numbers…"
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>
          {searching
            ? "Searching…"
            : query.trim().length < 2
              ? "Type at least 2 characters to search invoices"
              : "No invoices found"}
        </CommandEmpty>

        {query.trim().length < 2 ? (
          <CommandGroup heading="Go to">
            {QUICK_LINKS.map((link) => (
              <CommandItem
                key={link.id}
                value={link.label}
                onSelect={() => go(link.href)}
              >
                <link.icon className="h-4 w-4 text-muted-foreground" />
                <span>{link.label}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        ) : null}

        {invoices.length > 0 ? (
          <>
            <CommandSeparator />
            <CommandGroup heading="Invoices">
              {invoices.map((inv) => (
                <CommandItem
                  key={inv.id}
                  value={`${inv.name_of_company ?? ""} ${inv.invoice_number ?? ""} ${inv.id}`}
                  onSelect={() =>
                    go(
                      `/documents?search=${encodeURIComponent(query.trim())}`,
                    )
                  }
                >
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13px] font-medium">
                      {inv.name_of_company ?? "Unknown vendor"}
                    </div>
                    <div className="truncate text-[11px] text-muted-foreground">
                      {inv.invoice_number ?? "No invoice #"} ·{" "}
                      {formatCurrency(
                        inv.amount != null ? Number(inv.amount) : null,
                        inv.currency,
                      )}
                    </div>
                  </div>
                </CommandItem>
              ))}
              <CommandItem
                value="view-all-results"
                onSelect={() =>
                  go(`/documents?search=${encodeURIComponent(query.trim())}`)
                }
              >
                <span className="text-[13px] text-primary">
                  View all results in Documents
                </span>
              </CommandItem>
            </CommandGroup>
          </>
        ) : null}
      </CommandList>
    </CommandDialog>
  );
}
