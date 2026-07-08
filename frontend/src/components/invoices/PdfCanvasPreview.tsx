import { useEffect, useRef, useState } from "react";
import {
  AnnotationMode,
  getDocument,
  type PDFDocumentLoadingTask,
  VerbosityLevel,
} from "pdfjs-dist";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import {
  fetchInvoicePreviewPages,
  invoiceFileUrl,
} from "@/api/invoices";
import {
  hasPdfTailMarkers,
  inspectPdfBlob,
  logPdfByteReport,
  normalizePdfBytes,
} from "@/lib/pdfBytes";
import { cn } from "@/lib/utils";
import "@/lib/pdfjs";

type PreviewMode = "canvas" | "server" | "native" | "failed";

export function PdfCanvasPreview({
  blob,
  invoiceId,
  fileUrl,
  className,
  minHeightClass = "min-h-[400px]",
}: {
  blob: Blob;
  invoiceId?: number;
  /**
   * Direct same-origin endpoint for the source file (e.g.
   * /api/invoices/{id}/file). Used only as a last-resort native viewer.
   */
  fileUrl?: string;
  className?: string;
  minHeightClass?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const fallbackWrapperRef = useRef<HTMLDivElement>(null);
  const [rendering, setRendering] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("canvas");
  const [serverPageUrls, setServerPageUrls] = useState<string[]>([]);
  const [likelyCorrupt, setLikelyCorrupt] = useState(false);
  const [fallbackUnavailable, setFallbackUnavailable] = useState(false);
  const objectUrlsRef = useRef<string[]>([]);

  const revokeObjectUrls = () => {
    for (const url of objectUrlsRef.current) {
      URL.revokeObjectURL(url);
    }
    objectUrlsRef.current = [];
    setServerPageUrls([]);
  };

  useEffect(() => {
    let cancelled = false;
    let loadingTask: PDFDocumentLoadingTask | null = null;
    const container = containerRef.current;
    if (!container) return;

    container.replaceChildren();
    setRendering(true);
    setError(null);
    setPreviewMode("canvas");
    setLikelyCorrupt(false);
    setFallbackUnavailable(false);
    revokeObjectUrls();

    void (async () => {
      let hasStandardEof = false;
      try {
        const report = await inspectPdfBlob(blob);
        if (invoiceId != null) {
          logPdfByteReport("preview-bytes", invoiceId, report, {
            blobType: blob.type,
          });
        }

        if (!report.startsWithPdf) {
          throw new Error("Invalid or corrupt PDF file");
        }

        const raw = new Uint8Array(await blob.arrayBuffer());
        const data = normalizePdfBytes(raw);
        hasStandardEof = report.hasEofMarker;

        if (!report.hasEofMarker && !hasPdfTailMarkers(data)) {
          setLikelyCorrupt(true);
        }

        const pdfBytes = new Uint8Array(data);

        loadingTask = getDocument({
          data: pdfBytes,
          length: pdfBytes.length,
          disableRange: true,
          disableStream: true,
          disableAutoFetch: true,
          stopAtErrors: false,
          isEvalSupported: false,
          verbosity: VerbosityLevel.ERRORS,
        });

        const pdf = await loadingTask.promise;
        if (cancelled) return;

        const containerWidth = container.clientWidth || 600;

        for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
          if (cancelled) return;

          const page = await pdf.getPage(pageNum);
          const baseViewport = page.getViewport({ scale: 1 });
          const scale = Math.max(
            0.5,
            (containerWidth - 16) / baseViewport.width,
          );
          const viewport = page.getViewport({ scale });

          const canvas = document.createElement("canvas");
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          canvas.className = "mx-auto mb-2 block max-w-full";

          const context = canvas.getContext("2d");
          if (!context) {
            throw new Error("Canvas rendering is not supported");
          }

          await page.render({
            canvasContext: context,
            viewport,
            annotationMode: AnnotationMode.DISABLE,
          }).promise;
          if (cancelled) return;
          container.appendChild(canvas);
        }
      } catch (e: unknown) {
        if (cancelled) return;

        const name = e instanceof Error ? e.name : "Error";
        const message =
          e instanceof Error ? e.message : "Could not render PDF preview";
        console.warn(
          `[invoice-file] pdf.js preview failed: ${name} — ${message}`,
          { invoiceId, name, message },
        );
        setError(message);

        if (invoiceId != null) {
          try {
            console.info("[invoice-file] trying server pdf preview", {
              invoiceId,
            });
            const pageBlobs = await fetchInvoicePreviewPages(invoiceId);
            if (cancelled) return;
            if (pageBlobs.length > 0) {
              const urls = pageBlobs.map((pageBlob) => {
                const url = URL.createObjectURL(pageBlob);
                objectUrlsRef.current.push(url);
                return url;
              });
              setServerPageUrls(urls);
              setPreviewMode("server");
              console.info("[invoice-file] server pdf preview rendered", {
                invoiceId,
                pageCount: urls.length,
              });
              return;
            }
          } catch (serverErr: unknown) {
            const serverMessage =
              serverErr instanceof Error
                ? serverErr.message
                : "Server preview failed";
            console.warn("[invoice-file] server pdf preview failed", {
              invoiceId,
              message: serverMessage,
            });
          }
        }

        if (fileUrl && hasStandardEof) {
          setPreviewMode("native");
          console.info("[invoice-file] native pdf fallback engaged", {
            invoiceId,
            viewerSrc: fileUrl,
            usingDirectUrl: true,
          });
          return;
        }

        setPreviewMode("failed");
      } finally {
        if (!cancelled) setRendering(false);
      }
    })();

    return () => {
      cancelled = true;
      loadingTask?.destroy();
      revokeObjectUrls();
    };
  }, [blob, fileUrl, invoiceId]);

  const showServerPreview = previewMode === "server" && serverPageUrls.length > 0;
  const showNativeFallback = previewMode === "native" && Boolean(fileUrl);
  const viewerSrc = fileUrl ?? null;

  useEffect(() => {
    if (!showNativeFallback) return;
    const el = fallbackWrapperRef.current;
    if (!el) return;
    const width = el.clientWidth;
    const height = el.clientHeight;
    console.info("[invoice-file] native pdf fallback layout", {
      invoiceId,
      viewerSrc,
      showNativeFallback,
      width,
      height,
    });
    if (height < 50) {
      console.warn(
        "[invoice-file] native pdf fallback has near-zero height — check parent layout",
        { invoiceId, height },
      );
    }
  }, [showNativeFallback, invoiceId, viewerSrc]);

  const openUrl = viewerSrc ?? (invoiceId != null ? invoiceFileUrl(invoiceId) : null);

  return (
    <div
      className={cn(
        "relative overflow-auto p-2",
        minHeightClass,
        className,
      )}
    >
      {rendering && (
        <LoadingSpinner
          centered
          size="lg"
          className="text-muted-foreground"
          label="Rendering PDF…"
          containerClassName={cn(minHeightClass, "py-0")}
        />
      )}

      {showServerPreview && (
        <div className={cn("flex flex-col gap-2", minHeightClass)}>
          <p className="px-4 pt-2 text-center text-[12px] text-muted-foreground">
            Browser preview is unavailable for this PDF. Showing a server-rendered
            copy instead.
          </p>
          {serverPageUrls.map((url, index) => (
            <img
              key={url}
              src={url}
              alt={`Invoice page ${index + 1}`}
              className="mx-auto mb-2 block max-w-full"
            />
          ))}
          {openUrl && (
            <div className="px-4 pb-2 text-center">
              <a
                href={openUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[12px] text-primary hover:underline"
              >
                Open original file
              </a>
            </div>
          )}
        </div>
      )}

      {showNativeFallback && (
        <div
          ref={fallbackWrapperRef}
          className={cn("flex flex-col gap-2", minHeightClass)}
        >
          <div className="flex flex-wrap items-center justify-center gap-2 px-4 pt-2 text-center">
            <p className="text-[12px] text-muted-foreground">
              Inline canvas preview is unavailable for this PDF. Showing the
              browser viewer instead.
            </p>
            {openUrl && (
              <a
                href={openUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[12px] text-primary hover:underline"
              >
                Open in new tab
              </a>
            )}
          </div>
          <iframe
            key={viewerSrc ?? "pdf-fallback"}
            src={viewerSrc ?? undefined}
            title="Invoice PDF preview"
            className={cn(
              "w-full flex-1 border-0 bg-background",
              minHeightClass,
            )}
            onLoad={() => {
              setFallbackUnavailable(false);
              console.info("[invoice-file] native pdf iframe rendered", {
                invoiceId,
                viewerSrc,
              });
            }}
            onError={() => setFallbackUnavailable(true)}
          />
          {fallbackUnavailable && (
            <p className="px-4 pb-2 text-center text-[12px] text-destructive">
              The browser could not display this PDF.
              {likelyCorrupt
                ? " The stored file appears corrupt — re-upload the invoice."
                : " Use “Open in new tab” above to view or download it."}
            </p>
          )}
        </div>
      )}

      {previewMode === "failed" && !rendering && (
        <div className="flex flex-col items-center gap-2 px-4 py-6 text-center">
          <p className="text-[13px] text-muted-foreground">
            {likelyCorrupt
              ? "This PDF appears corrupt or incomplete in storage. Re-upload the invoice to restore preview."
              : (error ?? "Could not render PDF preview.")}
          </p>
          {openUrl && (
            <a
              href={openUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[12px] text-primary hover:underline"
            >
              Open original file
            </a>
          )}
        </div>
      )}

      {error && previewMode === "canvas" && !rendering && (
        <p className="px-4 py-6 text-center text-[13px] text-muted-foreground">
          {error}
        </p>
      )}

      <div
        ref={containerRef}
        className={
          rendering || showServerPreview || showNativeFallback
            ? "invisible h-0"
            : undefined
        }
      />
    </div>
  );
}
