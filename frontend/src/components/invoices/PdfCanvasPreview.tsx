import { useEffect, useRef, useState } from "react";
import { AnnotationMode, getDocument } from "pdfjs-dist";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { cn } from "@/lib/utils";
import "@/lib/pdfjs";

export function PdfCanvasPreview({
  blob,
  className,
  minHeightClass = "min-h-[400px]",
}: {
  blob: Blob;
  className?: string;
  minHeightClass?: string;
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
          setError(
            e instanceof Error ? e.message : "Could not render PDF preview",
          );
        }
      } finally {
        if (!cancelled) setRendering(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [blob]);

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
      {error && !rendering && (
        <p className="px-4 py-6 text-center text-[13px] text-muted-foreground">
          {error}
        </p>
      )}
      <div ref={containerRef} className={rendering ? "invisible h-0" : undefined} />
    </div>
  );
}
