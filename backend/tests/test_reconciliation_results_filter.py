"""Tests for reconciliation results list filtering (Option B routing)."""

from repositories.match_repository import MatchRepository


def test_confirmed_match_statuses_include_matched_and_approved():
    statuses = MatchRepository._CONFIRMED_MATCH_STATUSES
    assert "matched" in statuses
    assert "approved" in statuses
    assert "suggested" not in statuses
