from datetime import datetime, timedelta, timezone
from decimal import Decimal

from config import settings
from fastapi import HTTPException
from core.debug_logger import debug_trace, get_logger, log_typed_fields
from core.invoice_access import invoice_owner_user_id
from schemas.auth import UserContext
from schemas.reconciliation import ManualMatchResponse
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
from utils.batch_payment_matching import (
    REASON_BATCH_AMOUNT_SUGGESTED,
    REASON_BATCH_INCOMPLETE,
    find_invoice_amount_combination,
    no_candidates_reason,
    normalize_supplier_key,
    reconcile_batch_status,
)
from utils.invoice_number_parser import extract_invoice_numbers, needs_llm_fallback
from utils.normalization import normalize_invoice_number
from utils.user_display import approver_paid_by

logger = get_logger(__name__)


class MatchingService:
    """
    Match bank transactions to invoices.

    - Regex + optional LLM extraction from bank comments.
    - One transaction may pay multiple invoices when several numbers are present.
    - Amount-combination suggestions when numbers are absent but debit matches
      a sum of unpaid invoices (same supplier, date window) — human approval required.
    """
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
        self,
        bank_statement_id: int | None = None,
        *,
        owner_user_id: int | None = None,
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
        transactions = await self._bank_txn_repo.list_unresolved(
            bank_statement_id,
            owner_user_id=owner_user_id,
        )
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
            txn_id = txn.id
            try:
                async with session.begin_nested():
                    await self._process_txn(
                        txn,
                        regex_results.get(txn_id, []),
                        llm_extra.get(txn_id, []),
                        summary,
                        now,
                        owner_user_id=owner_user_id,
                    )
            except Exception as exc:
                logger.exception(
                    "Matching failed for bank_transaction id=%d: %s",
                    txn_id,
                    exc,
                )
                try:
                    if not await self._review_repo.has_open_bank_task(
                        txn_id, "internal_error"
                    ):
                        await self._review_repo.create_bank_unmatched(
                            txn_id, "", "internal_error"
                        )
                        summary.review_tasks_created += 1
                    await self._bank_txn_repo.update_reconciliation_status(
                        txn_id, "needs_review"
                    )
                    summary.unmatched_transactions += 1
                except Exception:
                    logger.exception(
                        "Could not record internal_error review task for txn %d",
                        txn_id,
                    )

        summary.unmatched_invoices = await self._invoice_repo.count_by_match_status(
            "unmatched",
            owner_user_id=owner_user_id,
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
        *,
        owner_user_id: int | None = None,
    ) -> None:
        log_typed_fields(logger, f"Matching txn id={txn.id}", txn)
        candidates = merge_candidates(regex_only, from_llm)
        logger.debug(
            "  candidates for txn %d: regex=%r llm=%r merged=%r",
            txn.id, regex_only, from_llm, candidates,
        )
        await self._bank_txn_repo.save_detected_numbers(txn.id, candidates)

        if not candidates:
            if txn.transaction_date and await self._try_batch_amount_suggestion(
                txn, summary, owner_user_id=owner_user_id
            ):
                summary.unmatched_transactions += 1
                await self._bank_txn_repo.update_reconciliation_status(
                    txn.id, "needs_review"
                )
                return

            reason = no_candidates_reason(txn.comment)
            if not await self._review_repo.has_open_bank_task(txn.id, reason):
                await self._review_repo.create_bank_unmatched(
                    txn.id, "", reason
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
        not_in_db_count = 0
        ambiguous_count = 0
        matched_numbers: list[str] = []
        # Dedupe by invoice_id within the same txn so two candidates that
        # resolve to the same invoice can't trip the (invoice_id, txn_id)
        # unique constraint via two create() calls in one run.
        matched_invoice_ids: set[int] = set()
        candidate_keys: list[str] = []
        for raw in candidates:
            key = normalize_invoice_number(raw) or raw
            if key and key not in candidate_keys:
                candidate_keys.append(key)

        for key in candidate_keys:
            logger.debug(
                "    candidate key=%r (%s)",
                key,
                type(key).__name__,
            )
            if not key:
                continue

            invoice, ambiguous = await self._invoice_repo.find_by_number(
                key,
                owner_user_id=owner_user_id,
            )
            if ambiguous:
                ambiguous_count += 1
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
                dupes = await self._invoice_repo.list_by_number(
                    key, owner_user_id=owner_user_id
                )
                for dup in dupes:
                    await self._invoice_repo.flag_for_review(
                        dup.id,
                        "multiple_matches",
                        match_status="needs_review",
                    )
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
                txn_amount = txn.debited_amount or txn.credited_amount
                effective_paid = (
                    Decimal(str(txn_amount)) if txn_amount is not None else None
                )
                await self._invoice_repo.update_paid_at_date(
                    invoice.id, txn.transaction_date
                )
                if effective_paid is not None and invoice.amount is not None:
                    remaining = max(
                        Decimal(str(invoice.amount)) - effective_paid, Decimal("0")
                    )
                    await self._invoice_repo.update_debt(invoice.id, remaining)
                    match_status = (
                        "matched" if remaining <= 0 else "partially_matched"
                    )
                else:
                    match_status = "matched"
                await self._invoice_repo.update_match_status(
                    invoice.id, match_status
                )
                await self._match_repo.create(
                    invoice_id=invoice.id,
                    bank_transaction_id=txn.id,
                    invoice_number=key,
                    match_type=(
                        "batch_invoice_number"
                        if len(candidate_keys) > 1
                        else "invoice_number"
                    ),
                    match_confidence=1.0,
                    paid_at_date=txn.transaction_date,
                    status="matched",
                    paid_amount=effective_paid,
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
                not_in_db_count += 1
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
            status, batch_reason = reconcile_batch_status(
                candidate_count=len(candidate_keys),
                matched_invoice_count=len(matched_invoice_ids),
                not_in_db_count=not_in_db_count,
                ambiguous_count=ambiguous_count,
            )
            if batch_reason == REASON_BATCH_INCOMPLETE:
                if not await self._review_repo.has_open_bank_task(
                    txn.id, REASON_BATCH_INCOMPLETE
                ):
                    await self._review_repo.create_bank_unmatched(
                        txn.id, "", REASON_BATCH_INCOMPLETE
                    )
                    summary.review_tasks_created += 1
                for invoice_id in matched_invoice_ids:
                    await self._invoice_repo.flag_for_review(
                        invoice_id,
                        REASON_BATCH_INCOMPLETE,
                    )
            await self._bank_txn_repo.update_reconciliation_status(
                txn.id, status
            )
        else:
            await self._try_batch_amount_suggestion(
                txn, summary, owner_user_id=owner_user_id
            )
            summary.unmatched_transactions += 1
            await self._bank_txn_repo.update_reconciliation_status(
                txn.id, "needs_review"
            )

    @debug_trace
    async def manual_match(
        self,
        invoice_id: int,
        bank_transaction_id: int,
        user: UserContext,
        review_task_id: int | None = None,
        paid_amount: Decimal | None = None,
    ) -> ManualMatchResponse:
        owner = invoice_owner_user_id(user)
        invoice = await self._invoice_repo.get(invoice_id, owner_user_id=owner)
        if not invoice:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )

        txn = await self._bank_txn_repo.get(bank_transaction_id)
        if not txn:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "bank_transaction_not_found",
                    "message": "Bank transaction not found.",
                },
            )

        if not txn.transaction_date:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "missing_transaction_date",
                    "message": "Bank transaction has no date; cannot set paid date.",
                },
            )

        other_invoice_match = await self._match_repo.active_for_transaction(
            bank_transaction_id, exclude_invoice_id=invoice_id
        )
        if other_invoice_match:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "transaction_already_matched",
                    "message": "This bank line is already matched to another invoice.",
                },
            )

        if invoice.debt is not None and invoice.debt <= 0:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "invoice_fully_paid",
                    "message": "This invoice has already been fully paid.",
                },
            )

        invoice_number = (invoice.invoice_number or "").strip() or "MANUAL"
        paid_date = txn.transaction_date
        now = datetime.now(timezone.utc)

        txn_amount = txn.credited_amount or txn.debited_amount
        effective_paid_amount: Decimal | None = paid_amount
        if effective_paid_amount is None and txn_amount is not None:
            effective_paid_amount = Decimal(str(txn_amount))

        existing = await self._match_repo.get_pair(invoice_id, bank_transaction_id)
        if existing:
            if existing.status == "rejected":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "match_rejected",
                        "message": "A rejected match exists for this pair; resolve on the matching screen.",
                    },
                )
            match_id = existing.id
            if existing.status == "matched":
                approved = await self._match_repo.approve(existing.id)
                status = approved.status if approved else "approved"
            else:
                status = existing.status
        else:
            row = await self._match_repo.create(
                invoice_id=invoice_id,
                bank_transaction_id=bank_transaction_id,
                invoice_number=invoice_number,
                match_type="manual",
                match_confidence=1.0,
                paid_at_date=paid_date,
                status="approved",
                paid_amount=effective_paid_amount,
            )
            match_id = row.id
            status = row.status
            await self._audit_repo.log(
                user.user_id,
                "match_created",
                "invoice_payment_match",
                match_id,
                None,
                {
                    "invoice_id": invoice_id,
                    "bank_transaction_id": bank_transaction_id,
                    "match_type": "manual",
                    "paid_amount": str(effective_paid_amount)
                    if effective_paid_amount
                    else None,
                    "status": status,
                },
            )

        before_paid = {
            "paid_at_date": str(invoice.paid_at_date) if invoice.paid_at_date else None
        }
        await self._invoice_repo.update_paid_at_date(invoice_id, paid_date)
        await self._invoice_repo.update_paid_by(invoice_id, approver_paid_by(user))
        if effective_paid_amount is not None and invoice.amount is not None:
            total_paid = await self._match_repo.sum_paid_for_invoice(invoice_id)
            invoice_total = Decimal(str(invoice.amount))
            if total_paid >= invoice_total:
                await self._invoice_repo.settle_invoice_from_transaction(
                    invoice_id, effective_paid_amount
                )
            else:
                remaining = max(invoice_total - total_paid, Decimal("0"))
                await self._invoice_repo.update_debt(invoice_id, remaining)
                await self._invoice_repo.update_match_status(
                    invoice_id, "partially_matched"
                )
        else:
            await self._invoice_repo.update_match_status(invoice_id, "matched")
        await self._audit_repo.log(
            user.user_id,
            "payment_date_set",
            "invoice",
            invoice_id,
            before_paid,
            {"paid_at_date": str(paid_date), "via": "manual_match"},
        )

        await self._bank_txn_repo.update_reconciliation_status(
            bank_transaction_id, "matched"
        )

        if review_task_id is not None:
            task = await self._review_repo.get(review_task_id)
            if task and task.status == "open":
                await self._review_repo.resolve(review_task_id, "approved", now)
                await self._audit_repo.log(
                    user.user_id,
                    "review_approved",
                    "review_task",
                    review_task_id,
                    {"status": "open"},
                    {"status": "approved", "via": "manual_match"},
                )

        await self._review_repo.resolve_open_bank_tasks_for_txn(
            bank_transaction_id, [invoice_number], now
        )

        return ManualMatchResponse(
            match_id=match_id,
            status=status,
            invoice_id=invoice_id,
            bank_transaction_id=bank_transaction_id,
            review_task_id=review_task_id,
        )

    async def _try_batch_amount_suggestion(
        self,
        txn,
        summary: ReconciliationSummary,
        *,
        owner_user_id: int | None,
    ) -> bool:
        """Suggest invoices whose amounts sum to the debit — requires human approval."""
        if not settings.batch_amount_matching_enabled:
            return False
        if txn.debited_amount is None or txn.transaction_date is None:
            return False

        debit = Decimal(str(txn.debited_amount))
        if debit <= 0:
            return False

        if await self._review_repo.has_open_bank_task(
            txn.id, REASON_BATCH_AMOUNT_SUGGESTED
        ):
            return True

        window = settings.batch_amount_date_window_days
        date_from = txn.transaction_date - timedelta(days=window)

        rows = await self._invoice_repo.list_unpaid_for_amount_matching(
            owner_user_id=owner_user_id,
            invoice_date_from=date_from,
            invoice_date_to=txn.transaction_date,
        )
        if not rows:
            return False

        tolerance = Decimal(str(settings.match_amount_tolerance_eur))
        by_supplier: dict[str, list[tuple[int, Decimal, str]]] = {}
        for row in rows:
            supplier = normalize_supplier_key(row.name_of_company) or "__unknown__"
            by_supplier.setdefault(supplier, []).append(
                (
                    row.id,
                    Decimal(str(row.amount)),
                    row.invoice_number or str(row.id),
                )
            )

        best_ids: list[int] | None = None
        best_supplier = ""
        for supplier, group in by_supplier.items():
            combo = find_invoice_amount_combination(group, debit, tolerance)
            if combo and (best_ids is None or len(combo) < len(best_ids)):
                best_ids = combo
                best_supplier = supplier

        if not best_ids:
            return False

        invoice_details: list[dict] = []
        for inv_id in best_ids:
            inv = await self._invoice_repo.get(inv_id, owner_user_id=owner_user_id)
            if inv is None:
                continue
            if await self._match_repo.exists(inv_id, txn.id):
                continue
            await self._match_repo.create(
                invoice_id=inv_id,
                bank_transaction_id=txn.id,
                invoice_number=inv.invoice_number or str(inv_id),
                match_type="batch_amount",
                match_confidence=0.95,
                paid_at_date=txn.transaction_date,
                status="suggested",
            )
            invoice_details.append(
                {
                    "invoice_id": inv_id,
                    "invoice_number": inv.invoice_number,
                }
            )

        if not invoice_details:
            return False

        await self._review_repo.create_bank_unmatched(
            txn.id,
            "",
            REASON_BATCH_AMOUNT_SUGGESTED,
            payload={
                "invoice_ids": [d["invoice_id"] for d in invoice_details],
                "invoices": invoice_details,
                "debited_amount": str(debit),
                "supplier": (
                    best_supplier if best_supplier != "__unknown__" else None
                ),
            },
        )
        summary.review_tasks_created += 1
        logger.debug(
            "    batch amount suggestion: txn_id=%d invoices=%s debit=%s",
            txn.id,
            [d["invoice_id"] for d in invoice_details],
            debit,
        )
        return True
