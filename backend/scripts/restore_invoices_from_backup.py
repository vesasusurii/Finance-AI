"""
Restore invoice + uploaded_files rows from a pg_dump SQL backup.

Skips OpenAI re-extraction. Remaps storage_path to PDFs already on disk when
the backup path is missing (matches by original_filename suffix in uploads/).

Run inside backend container:
  docker compose exec backend python scripts/restore_invoices_from_backup.py
  docker compose exec backend python scripts/restore_invoices_from_backup.py /app/../backup_before_rebuild.sql
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

from config import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_BACKUP = BACKEND_DIR.parent / "backup_before_rebuild.sql"
UPLOADS_INVOICES = Path(settings.storage_path) / "invoices"

INVOICE_COPY_MARKER = "COPY public.invoices "
UPLOADED_FILES_COPY_MARKER = "COPY public.uploaded_files "


def _parse_copy_block(lines: list[str]) -> list[list[str | None]]:
    rows: list[list[str | None]] = []
    for line in lines:
        if line == "\\.":
            break
        parts = line.split("\t")
        rows.append([None if p == "\\N" else p for p in parts])
    return rows


def _extract_copy_section(sql_text: str, marker: str) -> list[list[str | None]]:
    normalized = sql_text.replace("\r\n", "\n")
    start = normalized.find(marker)
    if start < 0:
        raise ValueError(f"COPY block not found: {marker!r}")
    header_end = normalized.find(" FROM stdin;\n", start)
    if header_end < 0:
        raise ValueError(f"COPY header end not found for {marker!r}")
    data_start = header_end + len(" FROM stdin;\n")
    chunk = normalized[data_start:]
    end = chunk.find("\n\\.\n")
    if end < 0:
        if chunk.endswith("\n\\."):
            end = len(chunk) - 3
        else:
            raise ValueError("COPY block terminator not found")
    lines = chunk[:end].split("\n")
    return _parse_copy_block(lines)


def _build_filename_index() -> dict[str, str]:
    """Map original_filename -> storage_path (invoices/...) for files on disk."""
    index: dict[str, str] = {}
    if not UPLOADS_INVOICES.is_dir():
        return index
    for name in os.listdir(UPLOADS_INVOICES):
        if "_" in name:
            original = name.split("_", 1)[1]
            index[original] = f"invoices/{name}"
    return index


def _remap_storage_path(backup_path: str, original_filename: str, on_disk: dict[str, str]) -> str:
    full = Path(settings.storage_path) / backup_path
    if full.is_file():
        return backup_path
    mapped = on_disk.get(original_filename)
    if mapped:
        return mapped
    return backup_path


def _read_backup_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    if b"\x00" in raw[:200]:
        return raw.decode("utf-16-le", errors="replace")
    return raw.decode("utf-8", errors="replace")


def main() -> None:
    backup_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BACKUP
    if not backup_path.is_file():
        print(f"Backup not found: {backup_path}")
        sys.exit(1)

    sql_text = _read_backup_text(backup_path)
    invoice_rows = _extract_copy_section(sql_text, INVOICE_COPY_MARKER)
    upload_rows = [
        r
        for r in _extract_copy_section(sql_text, UPLOADED_FILES_COPY_MARKER)
        if r[4] == "invoice"
    ]

    on_disk = _build_filename_index()
    remapped = 0
    for row in upload_rows:
        original = row[1] or ""
        new_path = _remap_storage_path(row[2] or "", original, on_disk)
        if new_path != row[2]:
            remapped += 1
            row[2] = new_path

    sync_url = settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://", 1
    )
    engine = create_engine(sync_url)

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM invoice_payment_matches"))
        conn.execute(text("DELETE FROM review_tasks WHERE invoice_id IS NOT NULL"))
        conn.execute(text("DELETE FROM invoices"))
        conn.execute(text("DELETE FROM uploaded_files WHERE file_kind = 'invoice'"))

        for row in upload_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO uploaded_files (
                        id, original_filename, storage_path, mime_type,
                        file_kind, uploaded_by, uploaded_at, processing_status
                    ) VALUES (
                        :id, :original_filename, :storage_path, :mime_type,
                        :file_kind, :uploaded_by, :uploaded_at, :processing_status
                    )
                    """
                ),
                {
                    "id": int(row[0]),
                    "original_filename": row[1],
                    "storage_path": row[2],
                    "mime_type": row[3],
                    "file_kind": row[4],
                    "uploaded_by": int(row[5]),
                    "uploaded_at": row[6],
                    "processing_status": row[7],
                },
            )

        for row in invoice_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO invoices (
                        id, invoice_date, name_of_company, address_of_company,
                        invoice_number, invoice_number_normalized, amount, currency,
                        account_details, internal_note_description,
                        client_employee_related, paid_at_date, paid_by, fixed_status,
                        category, extraction_confidence, review_status, match_status,
                        source_file_id, created_at, updated_at
                    ) VALUES (
                        :id, :invoice_date, :name_of_company, :address_of_company,
                        :invoice_number, :invoice_number_normalized, :amount, :currency,
                        :account_details, :internal_note_description,
                        :client_employee_related, :paid_at_date, :paid_by, :fixed_status,
                        :category, :extraction_confidence, :review_status, :match_status,
                        :source_file_id, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": int(row[0]),
                    "invoice_date": row[1],
                    "name_of_company": row[2],
                    "address_of_company": row[3],
                    "invoice_number": row[4],
                    "invoice_number_normalized": row[5],
                    "amount": row[6],
                    "currency": row[7],
                    "account_details": row[8],
                    "internal_note_description": row[9],
                    "client_employee_related": row[10],
                    "paid_at_date": row[11],
                    "paid_by": row[12],
                    "fixed_status": row[13],
                    "category": row[14],
                    "extraction_confidence": row[15],
                    "review_status": row[16],
                    "match_status": row[17],
                    "source_file_id": int(row[18]) if row[18] else None,
                    "created_at": row[19],
                    "updated_at": row[20],
                },
            )

        conn.execute(
            text(
                "SELECT setval('invoices_id_seq', COALESCE((SELECT MAX(id) FROM invoices), 1))"
            )
        )
        conn.execute(
            text(
                "SELECT setval("
                "'uploaded_files_id_seq', COALESCE((SELECT MAX(id) FROM uploaded_files), 1)"
                ")"
            )
        )

    missing_files = 0
    for row in upload_rows:
        if not (Path(settings.storage_path) / (row[2] or "")).is_file():
            missing_files += 1

    print(f"Restored {len(upload_rows)} uploaded_files (invoice PDF metadata).")
    print(f"Restored {len(invoice_rows)} invoices from backup.")
    print(f"Remapped {remapped} storage_path values to PDFs on disk.")
    print(f"{missing_files} uploaded_files still have no PDF on disk (list works; preview may fail).")
    print("Done — no OpenAI extraction was run.")


if __name__ == "__main__":
    main()
