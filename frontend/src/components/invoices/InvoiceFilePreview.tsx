import { useEffect, useState } from "react";
import { ExternalLink, FileText } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { PdfCanvasPreview } from "@/components/invoices/PdfCanvasPreview";
import { fetchInvoiceFile, invoiceFileUrl } from "@/api/invoices";
import { cn } from "@/lib/utils";

function mimeFromName(name: string, fallback: string | null): string | null {
  if (fallback) return fallback;
  const lower = name.toLowerCase();
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  return null;
}

function isPdfMime(mime: string, displayName: string): boolean {
  return (
    mime === "application/pdf" ||
    mime.includes("pdf") ||
    displayName.toLowerCase().endsWith(".pdf")
  );
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
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
  const [previewIsImage, setPreviewIsImage] = useState(false);
  const [previewIsPdf, setPreviewIsPdf] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imgError, setImgError] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    setLoading(true);
    setError(null);
    setImgError(false);
    setPreviewUrl(null);
    setPreviewBlob(null);
    setPreviewIsImage(false);
    setPreviewIsPdf(false);

    void fetchInvoiceFile(invoiceId)
      .then((blob) => {
        if (cancelled) return;
        const resolvedMime =
          blob.type || mimeFromName(displayName, mimeType) || "";
        const image = resolvedMime.startsWith("image/");
        const pdf = isPdfMime(resolvedMime, displayName);

        setPreviewIsImage(image);
        setPreviewIsPdf(pdf);

        if (image) {
          objectUrl = URL.createObjectURL(blob);
          setPreviewUrl(objectUrl);
          return;
        }

        if (pdf) {
          setPreviewBlob(blob);
        }
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
  }, [displayName, invoiceId, mimeType]);

  const resolvedMime = mimeFromName(displayName, mimeType);
  const isImage = previewIsImage && resolvedMime?.startsWith("image/") && !imgError;
  const typeLabel =
    resolvedMime === "application/pdf" || resolvedMime?.includes("pdf")
      ? "PDF"
      : isImage
        ? (resolvedMime?.split("/")[1]?.toUpperCase() ?? "IMAGE")
        : resolvedMime
          ? "FILE"
          : null;
  const canOpen = !loading && !error;
  const showImage = !loading && !error && previewUrl !== null && isImage;
  const showPdf = !loading && !error && previewBlob !== null && previewIsPdf;
  const showImgError =
    !loading && !error && previewIsImage && imgError && previewUrl !== null;
  const showUnsupported =
    !loading &&
    !error &&
    !previewIsImage &&
    !previewIsPdf &&
    previewUrl === null &&
    previewBlob === null;

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
          {canOpen && (
            <a
              href={invoiceFileUrl(invoiceId)}
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

        {showImage && (
          <div className={`h-full ${minHeightClass} overflow-auto p-2`}>
            <img
              src={previewUrl}
              alt={displayName}
              className="mx-auto h-auto max-w-full object-contain"
              onError={() => setImgError(true)}
            />
          </div>
        )}

        {showPdf && (
          <PdfCanvasPreview
            blob={previewBlob}
            minHeightClass={minHeightClass}
            className="h-full"
          />
        )}

        {(showUnsupported || showImgError) && (
          <div
            className={`flex ${minHeightClass} flex-col items-center justify-center gap-2 px-6 text-center`}
          >
            <p className="text-[13px] text-muted-foreground">
              Preview unavailable for this file type.
            </p>
            <a
              href={invoiceFileUrl(invoiceId)}
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
