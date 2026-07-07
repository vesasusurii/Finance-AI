"""Unit tests for invoice_repository.count_by_tabs filter wiring."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from repositories.invoice_repository import InvoiceRepository


@pytest.mark.asyncio
async def test_count_by_tabs_applies_owner_scope_and_search():
    session = AsyncMock()
    row = MagicMock()
    row.all_count = 10
    row.needs_review_count = 2
    row.unmatched_count = 3
    execute_result = MagicMock()
    execute_result.one.return_value = row
    session.execute.return_value = execute_result

    repo = InvoiceRepository(session)
    result = await repo.count_by_tabs(
        {"search": "  borek  "},
        owner_user_id=5,
    )

    assert result == {
        "all": 10,
        "needs_review": 2,
        "unmatched": 3,
    }
    session.execute.assert_awaited_once()
