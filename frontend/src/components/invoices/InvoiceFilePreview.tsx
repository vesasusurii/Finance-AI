import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, FileText } from "lucide-react";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { PdfCanvasPreview } from "@/components/invoices/PdfCanvasPreview";
import {
  fetchInvoiceFile,
  fetchInvoicePdfPreviewPage,
  invoiceFileUrl,
} from "@/api/invoices";
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

type ServerPreviewPage = {
  pageNumber: number;
  url: string;
};

function ServerPdfPreview({
  invoiceId,
  displayName,
}: {
  invoiceId: number;
  displayName: string;
  minHeightClass?: string;
}) {
  const [pages, setPages] = useState<ServerPreviewPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const objectUrlsRef = useRef<string[]>([]);

  useEffect(() => {
    let cancelled = false;

    const revokeObjectUrls = () => {
      objectUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
      objectUrlsRef.current = [];
    };

    setPages([]);
    setLoading(true);
    setError(null);
    revokeObjectUrls();

    void (async () => {
      try {
        console.info("[invoice-file] trying server pdf preview", { invoiceId });
        const first = await fetchInvoicePdfPreviewPage(invoiceId, 1);
        const nextPages: ServerPreviewPage[] = [];

        const addPage = (page: typeof first) => {
          const url = URL.createObjectURL(page.blob);
          objectUrlsRef.current.push(url);
          nextPages.push({ pageNumber: page.pageNumber, url });
          if (!cancelled) setPages([...nextPages]);
        };

        addPage(first);
        for (let pageNumber = 2; pageNumber <= first.pageCount; pageNumber++) {
          if (cancelled) return;
          addPage(await fetchInvoicePdfPreviewPage(invoiceId, pageNumber));
        }

        if (!cancelled) {
          console.info("[invoice-file] server pdf preview rendered", {
            invoiceId,
            pageCount: first.pageCount,
          });
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setError(
            e instanceof Error ? e.message : "Could not render PDF preview",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      revokeObjectUrls();
    };
  }, [invoiceId]);

  if (loading && pages.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center bg-muted/30">
        <LoadingSpinner
          centered
          size="lg"
          className="text-muted-foreground"
          label="Rendering PDF preview..."
          containerClassName="py-8"
        />
      </div>
    );
  }

  if (error && pages.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
        <p className="text-[13px] text-muted-foreground">{error}</p>
        <a
          href={invoiceFileUrl(invoiceId)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[12px] text-primary hover:underline"
        >
          Open file in new tab
        </a>
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-auto p-2">
      {pages.map((page) => (
        <img
          key={page.pageNumber}
          src={page.url}
          alt={`${displayName} page ${page.pageNumber}`}
          className="mx-auto mb-2 block h-auto max-w-full bg-background"
        />
      ))}
      {loading && pages.length > 0 && (
        <LoadingSpinner
          centered
          size="sm"
          className="py-4 text-muted-foreground"
          label="Rendering pages..."
        />
      )}
    </div>
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
  const [pdfCanvasError, setPdfCanvasError] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    setLoading(true);
    setError(null);
    setImgError(false);
    setPdfCanvasError(false);
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

  const handlePdfCanvasError = useCallback(
    (e: unknown) => {
      console.warn("[invoice-file] pdf.js preview failed", {
        invoiceId,
        name: e instanceof Error ? e.name : undefined,
        message: e instanceof Error ? e.message : String(e),
      });
      setPdfCanvasError(true);
    },
    [invoiceId],
  );

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
  const showPdf =
    !loading &&
    !error &&
    previewBlob !== null &&
    previewIsPdf &&
    !pdfCanvasError;
  const showServerPdf =
    !loading &&
    !error &&
    previewIsPdf &&
    pdfCanvasError;
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
        "flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-card",
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

      <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-muted/30">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-muted/30">
            <LoadingSpinner
              size="lg"
              className="text-muted-foreground"
              label="Loading preview…"
            />
          </div>
        )}

        {!loading && error && (
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
            <FileText className="h-10 w-10 text-muted-foreground/40" />
            <p className="max-w-sm text-[13px] text-muted-foreground">
              {error}
            </p>
          </div>
        )}

        {showImage && (
          <div className="min-h-0 flex-1 overflow-auto p-2">
            <img
              src={previewUrl}
              alt={displayName}
              className="mx-auto block h-auto max-w-full object-contain"
              onError={() => setImgError(true)}
            />
          </div>
        )}

        {showPdf && previewBlob && (
          <PdfCanvasPreview
            blob={previewBlob}
            className="min-h-0"
            onError={handlePdfCanvasError}
          />
        )}

        {showServerPdf && (
          <ServerPdfPreview
            invoiceId={invoiceId}
            displayName={displayName}
          />
        )}

        {(showUnsupported || showImgError) && (
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
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
