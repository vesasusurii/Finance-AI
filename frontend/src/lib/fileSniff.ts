/** Magic-byte checks for invoice file preview (MIME headers can lie). */

import {
  bytesLookLikePdfAt,
  findPdfStart,
  hasPdfEofMarker,
} from "@/lib/pdfBytes";

export function bytesLookLikePdf(bytes: Uint8Array): boolean {
  return bytesLookLikePdfAt(bytes, findPdfStart(bytes));
}

export function bytesLookLikePng(bytes: Uint8Array): boolean {
  return (
    bytes.length >= 8 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47 &&
    bytes[4] === 0x0d &&
    bytes[5] === 0x0a &&
    bytes[6] === 0x1a &&
    bytes[7] === 0x0a
  );
}

export function bytesLookLikeJpeg(bytes: Uint8Array): boolean {
  return bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xd8;
}

export type SniffedFileKind = "pdf" | "image" | "invalid-pdf" | "unsupported";

const SNIFF_WINDOW = 4096;

export async function sniffInvoiceBlob(
  blob: Blob,
  displayName: string,
  mimeType: string | null,
): Promise<SniffedFileKind> {
  const header = new Uint8Array(
    await blob.slice(0, SNIFF_WINDOW).arrayBuffer(),
  );
  if (bytesLookLikePdf(header)) return "pdf";
  if (bytesLookLikePng(header) || bytesLookLikeJpeg(header)) return "image";

  const lower = displayName.toLowerCase();
  const mime =
    blob.type ||
    mimeType ||
    (lower.endsWith(".pdf")
      ? "application/pdf"
      : lower.endsWith(".png")
        ? "image/png"
        : lower.endsWith(".jpg") || lower.endsWith(".jpeg")
          ? "image/jpeg"
          : "");

  if (mime.startsWith("image/")) return "image";
  if (mime.includes("pdf") || lower.endsWith(".pdf")) {
    const full = new Uint8Array(await blob.arrayBuffer());
    return bytesLookLikePdf(full) ? "pdf" : "invalid-pdf";
  }
  return "unsupported";
}

export { hasPdfEofMarker };
