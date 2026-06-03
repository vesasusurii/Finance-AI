from __future__ import annotations

import time

from core.cache import cache
from core.debug_logger import get_logger
from core.queue import enqueue_match_bank_transactions
from core.queue_names import TASK_MATCH_BANK_TRANSACTIONS
from core.worker_locks import acquire_transaction_lock
from db.pool import async_session
from repositories.audit_repository import AuditRepository
from repositories.bank_transaction_repository import BankTransactionRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.match_repository import MatchRepository
from repositories.review_repository import ReviewRepository
from services.matching_service import MatchingService
from workers.base_worker import run_async_task

logger = get_logger(__name__)


def match_bank_transactions(
    bank_statement_id: int | None = None,
    owner_user_id: int | None = None,
) -> None:
    lock_scope = bank_statement_id if bank_statement_id is not None else 0

    run_async_task(
        task_name=TASK_MATCH_BANK_TRANSACTIONS,
        args={
            "bank_statement_id": bank_statement_id,
            "owner_user_id": owner_user_id,
            "transaction_id": lock_scope,
        },
        handler=lambda: _match_bank_transactions(bank_statement_id, owner_user_id),
        acquire_lock=lambda owner: acquire_transaction_lock(lock_scope, owner),
        requeue_rate_limited=lambda retry_count, delay_seconds: enqueue_match_bank_transactions(
            bank_statement_id,
            owner_user_id=owner_user_id,
            retry_count=retry_count,
            delay_seconds=delay_seconds,
        ),
    )


async def _match_bank_transactions(
    bank_statement_id: int | None = None,
    owner_user_id: int | None = None,
) -> dict:
    t0 = time.perf_counter()

    async with async_session() as session:
        matching = MatchingService(
            InvoiceRepository(session),
            BankTransactionRepository(session),
            MatchRepository(session),
            ReviewRepository(session),
            AuditRepository(session),
            comment_extractor=None,
        )
        summary = await matching.run(
            bank_statement_id,
            owner_user_id=owner_user_id,
        )
        await session.commit()

    cache.delete_pattern("review:*")
    cache.delete_pattern("bank_tx:*")
    duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    logger.info(
        {
            "task_name": TASK_MATCH_BANK_TRANSACTIONS,
            "bank_statement_id": bank_statement_id,
            "duration_ms": duration_ms,
            "status": "completed",
        }
    )
    return {**summary.model_dump(mode="json"), "duration_ms": duration_ms}
