"""Compute inclusive date ranges for finance period reports."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

PeriodKind = Literal["day", "week", "month", "year"]

VALID_PERIODS: frozenset[str] = frozenset({"day", "week", "month", "year"})


def period_range(
    period: PeriodKind,
    anchor: date,
) -> tuple[date, date, str]:
    """Return (start_date, end_date, label) for the period containing anchor."""
    if period == "day":
        label = anchor.strftime("%d %B %Y")
        return anchor, anchor, label

    if period == "week":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
        label = f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"
        return start, end, label

    if period == "month":
        start = date(anchor.year, anchor.month, 1)
        if anchor.month == 12:
            end = date(anchor.year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(anchor.year, anchor.month + 1, 1) - timedelta(days=1)
        label = anchor.strftime("%B %Y")
        return start, end, label

    if period == "year":
        start = date(anchor.year, 1, 1)
        end = date(anchor.year, 12, 31)
        return start, end, str(anchor.year)

    raise ValueError(f"Unsupported period: {period}")
