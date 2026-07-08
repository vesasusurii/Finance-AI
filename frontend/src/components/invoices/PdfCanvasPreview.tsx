import { useEffect, useRef, useState } from "react";
import { AnnotationMode, getDocument } from "pdfjs-dist";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { cn } from "@/lib/utils";
import "@/lib/pdfjs";

async function waitForContainerWidth(
  container: HTMLElement,
  timeoutMs = 4000,
): Promise<number> {
  const start = performance.now();
  while (performance.now() - start < timeoutMs) {
    const width = container.clientWidth;
    if (width > 0) return width;
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => resolve());
    });
  }
  return container.clientWidth || 600;
}

export function PdfCanvasPreview({
  blob,
  className,
  minHeightClass = "min-h-[400px]",
  onError,
}: {
  blob: Blob;
  className?: string;
  minHeightClass?: string;
  onError?: (error: unknown) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [rendering, setRendering] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const container = containerRef.current;
    if (!container) return;

    container.replaceChildren();
    setRendering(true);
    setError(null);

    void (async () => {
      try {
        const data = await blob.arrayBuffer();
        const pdf = await getDocument({
          data,
          // Avoid eval/new Function in the worker (CSP script-src 'self').
          isEvalSupported: false,
        }).promise;
        const containerWidth = await waitForContainerWidth(container);

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

        // Force a layout pass so canvases paint without needing a scroll nudge.
        await new Promise<void>((resolve) => {
          requestAnimationFrame(() => resolve());
        });
      } catch (e: unknown) {
        if (!cancelled) {
          setError(
            e instanceof Error ? e.message : "Could not render PDF preview",
          );
          onError?.(e);
        }
      } finally {
        if (!cancelled) setRendering(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [blob, onError]);

  return (
    <div
      className={cn(
        "relative min-h-0 flex-1 overflow-auto p-2",
        minHeightClass,
        className,
      )}
    >
      {rendering && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-muted/30">
          <LoadingSpinner
            size="lg"
            className="text-muted-foreground"
            label="Rendering PDF…"
          />
        </div>
      )}
      {error && !rendering && (
        <p className="px-4 py-6 text-center text-[13px] text-muted-foreground">
          {error}
        </p>
      )}
      <div ref={containerRef} />
    </div>
  );
}
