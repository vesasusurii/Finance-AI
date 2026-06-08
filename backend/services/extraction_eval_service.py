"""Accuracy measurement for invoice extraction fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from schemas.invoice import ExtractionResult

CRITICAL_EVAL_FIELDS = (
    "invoice_number",
    "invoice_date",
    "amount",
    "name_of_company",
)


@dataclass
class FieldComparison:
    field: str
    expected: object
    actual: object
    passed: bool


@dataclass
class FixtureResult:
    fixture_name: str
    passed: bool
    field_results: list[FieldComparison] = field(default_factory=list)
    error: str | None = None

    @property
    def accuracy(self) -> float:
        if not self.field_results:
            return 0.0
        return sum(1 for f in self.field_results if f.passed) / len(self.field_results)


@dataclass
class EvalReport:
    results: list[FixtureResult]
    baseline_accuracy: float

    @property
    def overall_accuracy(self) -> float:
        total = sum(len(r.field_results) for r in self.results if r.field_results)
        if total == 0:
            return 0.0
        passed = sum(
            sum(1 for f in r.field_results if f.passed)
            for r in self.results
            if r.field_results
        )
        return passed / total

    @property
    def passed(self) -> bool:
        return self.overall_accuracy >= self.baseline_accuracy

    def summary_lines(self) -> list[str]:
        lines = [
            f"Overall accuracy: {self.overall_accuracy:.1%} "
            f"(baseline: {self.baseline_accuracy:.1%})",
            f"Status: {'PASS' if self.passed else 'FAIL'}",
            "",
        ]
        for result in self.results:
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"  [{status}] {result.fixture_name}")
            if result.error:
                lines.append(f"         error: {result.error}")
                continue
            for fr in result.field_results:
                mark = "ok" if fr.passed else "MISS"
                lines.append(
                    f"         {mark} {fr.field}: expected={fr.expected!r} "
                    f"actual={fr.actual!r}"
                )
        return lines


def load_expected(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _normalise_amount(value: object) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def compare_extraction(
    expected: dict,
    actual: ExtractionResult,
    *,
    fixture_name: str,
) -> FixtureResult:
    field_results: list[FieldComparison] = []
    actual_data = actual.model_dump()

    for field_name in CRITICAL_EVAL_FIELDS:
        exp = expected.get(field_name)
        act = actual_data.get(field_name)

        if field_name == "amount":
            exp_norm = _normalise_amount(exp)
            act_norm = _normalise_amount(act)
            passed = exp_norm == act_norm
        elif field_name == "invoice_date" and exp and act:
            passed = str(exp)[:10] == str(act)[:10]
        else:
            passed = (exp or None) == (act or None)

        field_results.append(
            FieldComparison(
                field=field_name,
                expected=exp,
                actual=act,
                passed=passed,
            )
        )

    return FixtureResult(
        fixture_name=fixture_name,
        passed=all(f.passed for f in field_results),
        field_results=field_results,
    )


def build_report(
    results: list[FixtureResult],
    *,
    baseline_accuracy: float,
) -> EvalReport:
    return EvalReport(results=results, baseline_accuracy=baseline_accuracy)
