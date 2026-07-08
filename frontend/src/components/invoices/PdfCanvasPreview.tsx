import { useEffect, useRef, useState } from "react";
import {
  AnnotationMode,
  getDocument,
  type PDFDocumentLoadingTask,
  VerbosityLevel,
} from "pdfjs-dist";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import {
  inspectPdfBlob,
  logPdfByteReport,
  normalizePdfBytes,
} from "@/lib/pdfBytes";
import { cn } from "@/lib/utils";
import "@/lib/pdfjs";

export function PdfCanvasPreview({
  blob,
  invoiceId,
  className,
  minHeightClass = "min-h-[400px]",
}: {
  blob: Blob;
  invoiceId?: number;
  className?: string;
  minHeightClass?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const fallbackWrapperRef = useRef<HTMLDivElement>(null);
  const [rendering, setRendering] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nativeUrl, setNativeUrl] = useState<string | null>(null);
  const [fallbackUnavailable, setFallbackUnavailable] = useState(false);
  const nativeUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let loadingTask: PDFDocumentLoadingTask | null = null;
    const container = containerRef.current;
    if (!container) return;

    const revokeNativeUrl = () => {
      if (nativeUrlRef.current) {
        URL.revokeObjectURL(nativeUrlRef.current);
        nativeUrlRef.current = null;
      }
      setNativeUrl(null);
    };

    container.replaceChildren();
    setRendering(true);
    setError(null);
    setFallbackUnavailable(false);
    revokeNativeUrl();

    void (async () => {
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
        if (!cancelled) {
          const name = e instanceof Error ? e.name : "Error";
          const message =
            e instanceof Error ? e.message : "Could not render PDF preview";
          // pdf.js throws named exceptions (InvalidPDFException,
          // PasswordException, UnknownErrorException). Print them inline so the
          // real cause is visible without expanding the console object.
          console.warn(
            `[invoice-file] pdf.js preview failed: ${name} — ${message}`,
            { invoiceId, name, message },
          );
          setError(message);

          const fallbackUrl = URL.createObjectURL(
            blob.type === "application/pdf"
              ? blob
              : new Blob([await blob.arrayBuffer()], { type: "application/pdf" }),
          );
          nativeUrlRef.current = fallbackUrl;
          setNativeUrl(fallbackUrl);
          console.info("[invoice-file] native pdf fallback engaged", {
            invoiceId,
            nativeUrl: fallbackUrl,
            isBlobUrl: fallbackUrl.startsWith("blob:"),
            blobSize: blob.size,
            blobType: blob.type,
          });
        }
      } finally {
        if (!cancelled) setRendering(false);
      }
    })();

    return () => {
      cancelled = true;
      loadingTask?.destroy();
      revokeNativeUrl();
    };
  }, [blob, invoiceId]);

  // Only render the browser viewer when we have a real blob: URL. A raw
  // authenticated API URL must never be used here — it would need cookies the
  // <iframe> cannot guarantee and would leak the endpoint.
  const hasValidBlobUrl = Boolean(nativeUrl && nativeUrl.startsWith("blob:"));
  const showNativeFallback = Boolean(error && hasValidBlobUrl);

  useEffect(() => {
    if (!showNativeFallback) return;
    const el = fallbackWrapperRef.current;
    if (!el) return;
    const width = el.clientWidth;
    const height = el.clientHeight;
    console.info("[invoice-file] native pdf fallback layout", {
      invoiceId,
      nativeUrl,
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
  }, [showNativeFallback, invoiceId, nativeUrl]);

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
            <a
              href={nativeUrl ?? undefined}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[12px] text-primary hover:underline"
            >
              Open in new tab
            </a>
          </div>
          {/* iframe is reliable for blob: PDFs in Chrome; <embed>/<object>
              frequently render blank. CSP allows this via frame-src blob:. */}
          <iframe
            key={nativeUrl ?? "pdf-fallback"}
            src={nativeUrl ?? undefined}
            title="Invoice PDF preview"
            className={cn(
              "w-full flex-1 border-0 bg-background",
              minHeightClass,
            )}
            onLoad={() => {
              setFallbackUnavailable(false);
              console.info("[invoice-file] native pdf iframe rendered", {
                invoiceId,
                nativeUrl,
              });
            }}
            onError={() => setFallbackUnavailable(true)}
          />
          {fallbackUnavailable && (
            <p className="px-4 pb-2 text-center text-[12px] text-destructive">
              The browser could not display this PDF. Use “Open in new tab”
              above to view or download it.
            </p>
          )}
        </div>
      )}
      {error && !showNativeFallback && !rendering && (
        <p className="px-4 py-6 text-center text-[13px] text-muted-foreground">
          {error}
        </p>
      )}
      <div
        ref={containerRef}
        className={rendering || showNativeFallback ? "invisible h-0" : undefined}
      />
    </div>
  );
}
