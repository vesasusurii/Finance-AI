import { useEffect, useState } from "react";
import { ExternalLink, FileText } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { fetchInvoiceFile } from "@/api/invoices";
import { cn } from "@/lib/utils";

function mimeFromName(name: string, fallback: string | null): string | null {
  if (fallback) return fallback;
  const lower = name.toLowerCase();
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  return null;
}

export function InvoiceFilePreview({
  invoiceId,
  displayName,
  mimeType = null,
  minHeightClass = "min-h-[420px]",
  className,
}: {
  invoiceId: number;
  displayName: string;
  mimeType?: string | null;
  minHeightClass?: string;
  className?: string;
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imgError, setImgError] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    setLoading(true);
    setError(null);
    setImgError(false);
    setBlobUrl(null);

    void fetchInvoiceFile(invoiceId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(
          e instanceof Error ? e.message : "Could not load invoice file",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [invoiceId]);

  const resolvedMime = mimeFromName(displayName, mimeType);
  const isImage = resolvedMime?.startsWith("image/") && !imgError;
  const typeLabel =
    resolvedMime === "application/pdf" || resolvedMime?.includes("pdf")
      ? "PDF"
      : isImage
        ? (resolvedMime?.split("/")[1]?.toUpperCase() ?? "IMAGE")
        : resolvedMime
          ? "FILE"
          : null;

  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden rounded-lg border border-border bg-card",
        minHeightClass,
        className,
      )}
    >
      <div className="flex shrink-0 items-center gap-2 border-b border-border px-4 py-3">
        <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span
          className="truncate font-mono text-[12px] text-foreground"
          title={displayName}
        >
          {displayName}
        </span>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          {typeLabel && (
            <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
              {typeLabel}
            </span>
          )}
          {blobUrl && (
            <a
              href={blobUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
            >
              Open
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </div>

      <div className="relative min-h-[400px] flex-1 overflow-hidden bg-muted/30">
        {loading && (
          <LoadingSpinner
            centered
            size="lg"
            className="text-muted-foreground"
            label="Loading preview…"
            containerClassName={cn(minHeightClass, "py-0")}
          />
        )}

        {!loading && error && (
          <div
            className={`flex ${minHeightClass} flex-col items-center justify-center gap-2 px-6 text-center`}
          >
            <FileText className="h-10 w-10 text-muted-foreground/40" />
            <p className="max-w-sm text-[13px] text-muted-foreground">
              {error}
            </p>
          </div>
        )}

        {!loading && !error && blobUrl && isImage && (
          <div className={`h-full ${minHeightClass} overflow-auto p-2`}>
            <img
              src={blobUrl}
              alt={displayName}
              className="mx-auto h-auto max-w-full object-contain"
              onError={() => setImgError(true)}
            />
          </div>
        )}

        {!loading && !error && blobUrl && !isImage && (
          <iframe
            src={blobUrl}
            title={displayName}
            className={`h-full min-h-[400px] w-full border-0 ${minHeightClass}`}
          />
        )}

        {!loading && !error && blobUrl && imgError && (
          <div
            className={`flex ${minHeightClass} flex-col items-center justify-center gap-2 px-6 text-center`}
          >
            <p className="text-[13px] text-muted-foreground">
              Preview unavailable for this file type.
            </p>
            <a
              href={blobUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[12px] text-primary hover:underline"
            >
              Open file in new tab
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
