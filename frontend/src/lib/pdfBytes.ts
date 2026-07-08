/** PDF byte inspection for preview diagnostics and normalisation. */

const PDF_MAGIC = [0x25, 0x50, 0x44, 0x46] as const;
const SCAN_LIMIT = 4096;

export type PdfByteReport = {
  size: number;
  sha256: string;
  startsWithPdf: boolean;
  hasEofMarker: boolean;
  pdfStartOffset: number;
  leadingPrefixLen: number;
  first16Hex: string;
  last16Hex: string;
  firstBytesText: string;
};

function toHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function toPrintable(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => (b >= 32 && b <= 126 ? String.fromCharCode(b) : "."))
    .join("");
}

export function findPdfStart(bytes: Uint8Array, scanLimit = SCAN_LIMIT): number {
  const limit = Math.min(bytes.length, scanLimit);
  for (let i = 0; i <= limit - 4; i++) {
    if (
      bytes[i] === PDF_MAGIC[0] &&
      bytes[i + 1] === PDF_MAGIC[1] &&
      bytes[i + 2] === PDF_MAGIC[2] &&
      bytes[i + 3] === PDF_MAGIC[3]
    ) {
      return i;
    }
  }
  return -1;
}

export function bytesLookLikePdfAt(bytes: Uint8Array, offset = 0): boolean {
  return (
    bytes.length >= offset + 4 &&
    bytes[offset] === PDF_MAGIC[0] &&
    bytes[offset + 1] === PDF_MAGIC[1] &&
    bytes[offset + 2] === PDF_MAGIC[2] &&
    bytes[offset + 3] === PDF_MAGIC[3]
  );
}

export function hasPdfEofMarker(bytes: Uint8Array): boolean {
  if (bytes.length === 0) return false;
  const tail = bytes.subarray(Math.max(0, bytes.length - 65536));
  const marker = [0x25, 0x25, 0x45, 0x4f, 0x46]; // %%EOF
  for (let i = 0; i <= tail.length - marker.length; i++) {
    if (marker.every((b, j) => tail[i + j] === b)) {
      return true;
    }
  }
  return false;
}

export function normalizePdfBytes(bytes: Uint8Array): Uint8Array {
  const offset = findPdfStart(bytes);
  if (offset <= 0) {
    return bytes;
  }
  return bytes.subarray(offset);
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function inspectPdfBlob(blob: Blob): Promise<PdfByteReport> {
  const buffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const offset = findPdfStart(bytes);
  const normalized = offset > 0 ? bytes.subarray(offset) : bytes;
  const first = normalized.subarray(0, 16);
  const last =
    normalized.length > 16
      ? normalized.subarray(normalized.length - 16)
      : normalized;

  return {
    size: bytes.length,
    sha256: await sha256Hex(bytes),
    startsWithPdf: bytesLookLikePdfAt(bytes, offset >= 0 ? offset : 0),
    hasEofMarker: hasPdfEofMarker(normalized),
    pdfStartOffset: offset,
    leadingPrefixLen: Math.max(offset, 0),
    first16Hex: toHex(first),
    last16Hex: toHex(last),
    firstBytesText: toPrintable(first),
  };
}

export function logPdfByteReport(
  context: string,
  invoiceId: number,
  report: PdfByteReport,
  extra?: Record<string, unknown>,
): void {
  console.info(`[invoice-file] ${context}`, {
    invoiceId,
    ...report,
    ...extra,
  });
}
