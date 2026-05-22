import { useState } from "react";
import { uploadInvoices } from "../../api/invoices";
import { FileDropzone } from "../../components/FileDropzone";
import { PageHeader } from "../../components/PageHeader";
import { StatusBadge } from "../../components/StatusBadge";
import type { UploadItem } from "../../types/invoice";

export function UploadInvoicesPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [results, setResults] = useState<UploadItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload() {
    if (!files.length) return;
    setUploading(true);
    setError(null);
    try {
      const res = await uploadInvoices(files);
      setResults(res.items);
      setFiles([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="section">
      <div className="container stack-5">
        <PageHeader title="Upload invoices" />
        <FileDropzone onFiles={setFiles} />
        <button
          type="button"
          className="btn btn-accent"
          disabled={!files.length || uploading}
          onClick={handleUpload}
        >
          {uploading ? "Processing…" : "Upload and extract"}
        </button>
        {error && <p className="text-accent">{error}</p>}
        {results.length > 0 && (
          <ul className="card stack-3">
            {results.map((item, i) => (
              <li key={`${item.upload_id}-${i}`} className="stack-2">
                <span className="tok">{item.original_filename}</span>
                <StatusBadge status={item.processing_status} domain="processing" />
                {item.invoice_id && (
                  <span className="text-fg2">Invoice #{item.invoice_id}</span>
                )}
                {item.error && <span className="text-accent">{item.error}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
