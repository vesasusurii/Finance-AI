from datetime import datetime, timezone

from core.debug_logger import debug_trace, get_logger, log_typed_fields
from repositories.audit_repository import AuditRepository
from repositories.bank_transaction_repository import BankTransactionRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.match_repository import MatchRepository
from repositories.review_repository import ReviewRepository
from schemas.reconciliation import ReconciliationSummary
from services.bank_comment_extraction_service import (
    BankCommentExtractionService,
    merge_candidates,
)
from utils.invoice_number_parser import extract_invoice_numbers, needs_llm_fallback
from utils.normalization import normalize_invoice_number

logger = get_logger(__name__)


class MatchingService:
    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        bank_txn_repo: BankTransactionRepository,
        match_repo: MatchRepository,
        review_repo: ReviewRepository,
        audit_repo: AuditRepository,
        comment_extractor: BankCommentExtractionService | None = None,
    ) -> None:
        self._invoice_repo = invoice_repo
        self._bank_txn_repo = bank_txn_repo
        self._match_repo = match_repo
        self._review_repo = review_repo
        self._audit_repo = audit_repo
        self._comment_extractor = comment_extractor

    @debug_trace
    async def run(
        self, bank_statement_id: int | None = None
    ) -> ReconciliationSummary:
        now = datetime.now(timezone.utc)
        summary = ReconciliationSummary(
            matched=0,
            unmatched_invoices=0,
            unmatched_transactions=0,
            review_tasks_created=0,
            run_at=now.isoformat(),
        )
        logger.debug(
            "Matching run start: bank_statement_id=%r (%s) at %s",
            bank_statement_id,
            type(bank_statement_id).__name__,
            now.isoformat(),
        )

        # Re-scan everything not yet fully matched so edits to invoice numbers
        # take effect on later runs (pending + needs_review + partial).
        transactions = await self._bank_txn_repo.list_unresolved(bank_statement_id)
        logger.debug(
            "Loaded unresolved transactions: count=%d (%s)",
            len(transactions),
            type(transactions).__name__,
        )

        # ── Pre-pass: regex extract for every txn, decide LLM-fallback set ──
        regex_results: dict[int, list[str]] = {}
        llm_needed_by_comment: dict[str, list[int]] = {}
        for txn in transactions:
            comment = txn.comment or ""
            candidates = extract_invoice_numbers(comment)
            regex_results[txn.id] = candidates
            if (
                self._comment_extractor is not None
                and needs_llm_fallback(comment, candidates)
            ):
                llm_needed_by_comment.setdefault(comment, []).append(txn.id)

        # ── Single batched LLM call covers every distinct ambiguous comment ──
        llm_extra: dict[int, list[str]] = {}
        if llm_needed_by_comment:
            unique_comments = list(llm_needed_by_comment.keys())
            logger.debug(
                "LLM fallback: %d distinct comments covering %d txns",
                len(unique_comments),
                sum(len(ids) for ids in llm_needed_by_comment.values()),
            )
            llm_results = await self._comment_extractor.extract_many(unique_comments)
            for comment, result in zip(unique_comments, llm_results):
                for txn_id in llm_needed_by_comment[comment]:
                    llm_extra[txn_id] = result.invoice_numbers

        # ── Main matching loop ──
        # Each transaction uses a savepoint so one bad row cannot abort the
        # whole run (Postgres rejects further SQL after any error in-session).
        session = self._bank_txn_repo._session
        for txn in transactions:
            try:
                async with session.begin_nested():
                    await self._process_txn(
                        txn,
                        regex_results.get(txn.id, []),
                        llm_extra.get(txn.id, []),
                        summary,
                        now,
                    )
            except Exception as exc:
                logger.exception(
                    "Matching failed for bank_transaction id=%d: %s",
                    txn.id,
                    exc,
                )
                try:
                    if not await self._review_repo.has_open_bank_task(
                        txn.id, "internal_error"
                    ):
                        await self._review_repo.create_bank_unmatched(
                            txn.id, "", "internal_error"
                        )
                        summary.review_tasks_created += 1
                    await self._bank_txn_repo.update_reconciliation_status(
                        txn.id, "needs_review"
                    )
                    summary.unmatched_transactions += 1
                except Exception:
                    logger.exception(
                        "Could not record internal_error review task for txn %d",
                        txn.id,
                    )

        summary.unmatched_invoices = await self._invoice_repo.count_by_match_status(
            "unmatched"
        )

        log_typed_fields(logger, "Matching run summary", summary)
        return summary

    @debug_trace
    async def _process_txn(
        self,
        txn,
        regex_only: list[str],
        from_llm: list[str],
        summary: ReconciliationSummary,
        now: datetime,
    ) -> None:
        log_typed_fields(logger, f"Matching txn id={txn.id}", txn)
        candidates = merge_candidates(regex_only, from_llm)
        logger.debug(
            "  candidates for txn %d: regex=%r llm=%r merged=%r",
            txn.id, regex_only, from_llm, candidates,
        )
        await self._bank_txn_repo.save_detected_numbers(txn.id, candidates)

        if not candidates:
            if not await self._review_repo.has_open_bank_task(
                txn.id, "no_invoice_numbers_detected"
            ):
                await self._review_repo.create_bank_unmatched(
                    txn.id, "", "no_invoice_numbers_detected"
                )
                summary.review_tasks_created += 1
            summary.unmatched_transactions += 1
            await self._bank_txn_repo.update_reconciliation_status(
                txn.id, "needs_review"
            )
            return

        if not txn.transaction_date:
            if not await self._review_repo.has_open_bank_task(
                txn.id, "missing_transaction_date"
            ):
                await self._review_repo.create_bank_unmatched(
                    txn.id, "", "missing_transaction_date"
                )
                summary.review_tasks_created += 1
            summary.unmatched_transactions += 1
            await self._bank_txn_repo.update_reconciliation_status(
                txn.id, "needs_review"
            )
            return

        matched_any = False
        matched_count = 0
        matched_numbers: list[str] = []
        # Dedupe by invoice_id within the same txn so two candidates that
        # resolve to the same invoice can't trip the (invoice_id, txn_id)
        # unique constraint via two create() calls in one run.
        matched_invoice_ids: set[int] = set()
        for raw in candidates:
            key = normalize_invoice_number(raw) or raw
            logger.debug(
                "    candidate raw=%r (%s) -> normalized key=%r (%s)",
                raw,
                type(raw).__name__,
                key,
                type(key).__name__,
            )
            if not key:
                continue

            invoice, ambiguous = await self._invoice_repo.find_by_number(key)
            if ambiguous:
                logger.debug(
                    "    invoice lookup for %r: AMBIGUOUS (multiple matches in DB)",
                    key,
                )
                if not await self._review_repo.has_open_bank_task(
                    txn.id, "duplicate_invoice_in_db", invoice_number=key
                ):
                    await self._review_repo.create_bank_unmatched(
                        txn.id, key, "duplicate_invoice_in_db"
                    )
                    summary.review_tasks_created += 1
                continue

            logger.debug(
                "    invoice lookup for %r: %s",
                key,
                f"found id={invoice.id}" if invoice else "not found",
            )
            if invoice:
                if invoice.id in matched_invoice_ids:
                    matched_count += 1
                    matched_numbers.append(key)
                    continue
                if await self._match_repo.exists(invoice.id, txn.id):
                    logger.debug(
                        "    match already exists (invoice_id=%d, txn_id=%d) — skip create",
                        invoice.id,
                        txn.id,
                    )
                    matched_any = True
                    matched_count += 1
                    matched_numbers.append(key)
                    matched_invoice_ids.add(invoice.id)
                    continue

                before = {"paid_at_date": None}
                await self._invoice_repo.update_paid_at_date(
                    invoice.id, txn.transaction_date
                )
                await self._invoice_repo.update_match_status(
                    invoice.id, "matched"
                )
                await self._match_repo.create(
                    invoice_id=invoice.id,
                    bank_transaction_id=txn.id,
                    invoice_number=key,
                    match_type="invoice_number",
                    match_confidence=1.0,
                    paid_at_date=txn.transaction_date,
                    status="matched",
                )
                logger.debug(
                    "    MATCH created: invoice_id=%d (int) txn_id=%d (int) "
                    "invoice_number=%r (str) paid_at_date=%s (%s) confidence=1.0 (float)",
                    invoice.id,
                    txn.id,
                    key,
                    txn.transaction_date,
                    type(txn.transaction_date).__name__,
                )
                await self._audit_repo.log(
                    None,
                    "payment_date_set",
                    "invoice",
                    invoice.id,
                    before,
                    {"paid_at_date": str(txn.transaction_date)},
                )
                summary.matched += 1
                matched_any = True
                matched_count += 1
                matched_numbers.append(key)
                matched_invoice_ids.add(invoice.id)
            else:
                if not await self._review_repo.has_open_bank_task(
                    txn.id, "no_invoice_in_db", invoice_number=key
                ):
                    await self._review_repo.create_bank_unmatched(
                        txn.id, key, "no_invoice_in_db"
                    )
                    summary.review_tasks_created += 1
                    logger.debug(
                        "    review task created: txn_id=%d invoice_number=%r reason=no_invoice_in_db",
                        txn.id,
                        key,
                    )

        # Auto-close any open bank_match tasks whose invoice now exists.
        if matched_numbers:
            await self._review_repo.resolve_open_bank_tasks_for_txn(
                txn.id, matched_numbers, now
            )

        if matched_any:
            status = (
                "partial"
                if matched_count < len(candidates)
                else "matched"
            )
            await self._bank_txn_repo.update_reconciliation_status(
                txn.id, status
            )
        else:
            summary.unmatched_transactions += 1
            await self._bank_txn_repo.update_reconciliation_status(
                txn.id, "needs_review"
            )
