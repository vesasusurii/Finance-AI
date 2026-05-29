from datetime import date

import pytest

from utils.period_ranges import period_range


def test_period_range_day():
    start, end, label = period_range("day", date(2026, 5, 28))
    assert start == end == date(2026, 5, 28)
    assert "28" in label


def test_period_range_week():
    start, end, label = period_range("week", date(2026, 5, 28))
    assert start == date(2026, 5, 25)
    assert end == date(2026, 5, 31)
    assert "2026" in label


def test_period_range_month():
    start, end, label = period_range("month", date(2026, 2, 15))
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)
    assert label == "February 2026"


def test_period_range_year():
    start, end, label = period_range("year", date(2026, 7, 4))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 12, 31)
    assert label == "2026"
