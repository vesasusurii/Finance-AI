"""Benchmark local invoice extraction latency for one or more files.

Usage:
    python scripts/benchmark_invoice_extraction.py invoice1.pdf invoice2.jpg
    python scripts/benchmark_invoice_extraction.py fixtures/*.pdf --expected expected.json --json-out results.json
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from core.document_types import resolve_document_mime  # noqa: E402
from services.ai_validation_service import AIValidationService  # noqa: E402
from services.extraction_eval_service import compare_extraction, load_expected  # noqa: E402
from services.invoice_extraction_service import InvoiceExtractionService  # noqa: E402


def _expected_for(path: Path, expected: dict[str, Any]) -> dict[str, Any] | None:
    return expected.get(path.name) or expected.get(str(path)) or expected.get(path.stem)


def _flatten_result(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("meta") or {}
    return {
        "file": row["file"],
        "ok": row["ok"],
        "error": row.get("error"),
        "total_ms": row.get("total_ms"),
        "model": row.get("model"),
        "extraction_mode": meta.get("extraction_mode"),
        "queue_wait_ms": meta.get("queue_wait_ms"),
        "storage_download_ms": meta.get("storage_download_ms"),
        "text_extraction_ms": meta.get("text_extraction_ms"),
        "text_llm_ms": meta.get("text_llm_ms"),
        "render_ms": meta.get("render_ms"),
        "render_strategy": meta.get("render_strategy"),
        "render_parallel_ms": meta.get("render_parallel_ms"),
        "rendered_page_count": meta.get("rendered_page_count"),
        "rendered_image_bytes": meta.get("rendered_image_bytes"),
        "ocr_ms": meta.get("ocr_ms"),
        "openai_total_ms": meta.get("openai_total_ms"),
        "openai_call_count": meta.get("openai_call_count"),
        "merge_ms": meta.get("merge_ms"),
        "merge_strategy": meta.get("merge_strategy"),
        "prompt_strategy": meta.get("prompt_strategy"),
        "image_detail_strategy": meta.get("image_detail_strategy"),
        "pages_processed": meta.get("pages_processed"),
        "total_pdf_pages": meta.get("total_pdf_pages"),
        "accuracy": row.get("accuracy"),
    }


async def _run(files: list[Path], expected: dict[str, Any]) -> list[dict[str, Any]]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    service = InvoiceExtractionService(
        upload_repo=None,  # type: ignore[arg-type]
        invoice_repo=None,  # type: ignore[arg-type]
        invoice_access_repo=None,  # type: ignore[arg-type]
        audit_repo=None,  # type: ignore[arg-type]
        ai_validation=AIValidationService(),
        openai_client=client,
    )
    rows: list[dict[str, Any]] = []
    try:
        for path in files:
            started = time.perf_counter()
            row: dict[str, Any] = {"file": str(path), "ok": False}
            try:
                content = path.read_bytes()
                mime = resolve_document_mime(path.name, None)
                service._openai_timings = []  # noqa: SLF001
                service._last_merge_ms = None  # noqa: SLF001
                result, model, meta = await service.extract_from_bytes(
                    filename=path.name,
                    content=content,
                    mime=mime,
                )
                total_ms = round((time.perf_counter() - started) * 1000, 1)
                openai_calls = service._openai_timings  # noqa: SLF001
                meta = {
                    **meta,
                    "total_ms": meta.get("total_ms", total_ms),
                    "openai_total_ms": meta.get(
                        "openai_total_ms",
                        round(
                            sum(
                                float(call.get("openai_ms", 0.0))
                                for call in openai_calls
                            ),
                            1,
                        ),
                    ),
                    "openai_call_count": meta.get(
                        "openai_call_count", len(openai_calls)
                    ),
                    "openai_calls": openai_calls,
                }
                row.update(
                    {
                        "ok": True,
                        "total_ms": total_ms,
                        "model": model,
                        "meta": meta,
                        "result": result.model_dump(),
                    }
                )
                expected_fields = _expected_for(path, expected)
                if expected_fields:
                    comparison = compare_extraction(
                        expected_fields,
                        result,
                        fixture_name=path.name,
                    )
                    row["accuracy"] = comparison.accuracy
                    row["passed"] = comparison.passed
                    row["field_results"] = [
                        {
                            "field": field.field,
                            "expected": field.expected,
                            "actual": field.actual,
                            "passed": field.passed,
                        }
                        for field in comparison.field_results
                    ]
            except Exception as exc:
                row["total_ms"] = round((time.perf_counter() - started) * 1000, 1)
                row["error"] = str(exc)
            rows.append(row)
    finally:
        await client.close()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--expected", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--csv-out", type=Path)
    args = parser.parse_args()

    expected = load_expected(args.expected) if args.expected else {}
    rows = asyncio.run(_run(args.files, expected))

    output = json.dumps(rows, indent=2, default=str)
    print(output)
    if args.json_out:
        args.json_out.write_text(output + "\n", encoding="utf-8")
    if args.csv_out:
        with args.csv_out.open("w", newline="", encoding="utf-8") as handle:
            flattened = [_flatten_result(row) for row in rows]
            writer = csv.DictWriter(handle, fieldnames=list(flattened[0].keys()))
            writer.writeheader()
            writer.writerows(flattened)


if __name__ == "__main__":
    main()
