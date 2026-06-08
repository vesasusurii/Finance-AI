#!/usr/bin/env python3
"""
Evaluate invoice extraction accuracy against fixtures.

Usage (from repo root):
  cd backend && python ../scripts/eval_extraction.py
  cd backend && python ../scripts/eval_extraction.py --baseline 0.95
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow imports from backend package
_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND))

from config import settings  # noqa: E402
from core.document_types import resolve_document_mime  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from services.ai_validation_service import AIValidationService  # noqa: E402
from services.extraction_eval_service import (  # noqa: E402
    FixtureResult,
    build_report,
    compare_extraction,
    load_expected,
)
from services.invoice_extraction_service import InvoiceExtractionService  # noqa: E402

FIXTURES_DIR = _REPO_ROOT / "fixtures" / "invoices"
EXPECTED_DIR = _REPO_ROOT / "fixtures" / "expected"
BASELINE_FILE = _REPO_ROOT / "fixtures" / "baseline.json"


def _load_baseline(override: float | None) -> float:
    if override is not None:
        return override
    if BASELINE_FILE.is_file():
        data = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        return float(data.get("min_accuracy", settings.extraction_eval_baseline_accuracy))
    return settings.extraction_eval_baseline_accuracy


def _discover_fixtures() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for expected_path in sorted(EXPECTED_DIR.glob("*.json")):
        stem = expected_path.stem
        invoice_path: Path | None = None
        for ext in (".pdf", ".PDF", ".png", ".jpg", ".jpeg"):
            candidate = FIXTURES_DIR / f"{stem}{ext}"
            if candidate.is_file():
                invoice_path = candidate
                break
        pairs.append((invoice_path or FIXTURES_DIR / f"{stem}.pdf", expected_path))
    return pairs


async def _run_eval(*, baseline: float, dry_run: bool) -> int:
    pairs = _discover_fixtures()
    if not pairs:
        print("No expected fixtures found in fixtures/expected/")
        return 1

    results = []
    for invoice_path, expected_path in pairs:
        name = expected_path.stem
        expected = load_expected(expected_path)

        if not invoice_path.is_file():
            print(f"  [SKIP] {name}: no invoice file at {invoice_path}")
            continue

        if dry_run:
            print(f"  [DRY] {name}: would extract {invoice_path.name}")
            continue

        if not settings.openai_api_key:
            print("OPENAI_API_KEY is not configured")
            return 1

        content = invoice_path.read_bytes()
        mime = resolve_document_mime(invoice_path.name, None)
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        try:
            service = InvoiceExtractionService(
                upload_repo=None,  # type: ignore[arg-type]
                invoice_repo=None,  # type: ignore[arg-type]
                invoice_access_repo=None,  # type: ignore[arg-type]
                audit_repo=None,  # type: ignore[arg-type]
                ai_validation=AIValidationService(),
                openai_client=client,
            )
            extraction, meta = await service.extract_from_bytes(
                filename=invoice_path.name,
                content=content,
                mime=mime,
            )
            print(f"  extracted {name} model={meta.get('model')} mode={meta.get('extraction_mode')}")
            results.append(compare_extraction(expected, extraction, fixture_name=name))
        except Exception as exc:
            results.append(
                FixtureResult(
                    fixture_name=name,
                    passed=False,
                    error=str(exc),
                )
            )
        finally:
            await client.close()

    if dry_run:
        return 0

    report = build_report(results, baseline_accuracy=baseline)
    for line in report.summary_lines():
        print(line)

    return 0 if report.passed else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate invoice extraction fixtures")
    parser.add_argument(
        "--baseline",
        type=float,
        default=None,
        help="Minimum overall accuracy (default: fixtures/baseline.json or env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List fixtures without calling OpenAI",
    )
    args = parser.parse_args()
    baseline = _load_baseline(args.baseline)
    exit_code = asyncio.run(_run_eval(baseline=baseline, dry_run=args.dry_run))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
