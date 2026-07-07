from decimal import Decimal
import asyncio

from fastapi import HTTPException

from core.cache import cache
from core.debug_logger import debug_trace, get_logger
from core.invoice_access import invoice_owner_user_id, upload_owner_user_id
from models.invoice_payment_match import InvoicePaymentMatch
from repositories.audit_repository import AuditRepository
from repositories.bank_statement_repository import BankStatementRepository
from repositories.bank_transaction_repository import BankTransactionRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.match_repository import MatchRepository
from schemas.auth import UserContext
from schemas.reconciliation import (
    ApproveMatchRequest,
    ManualMatchRequest,
    ManualMatchResponse,
    MatchActionResponse,
    MatchListResponse,
    MatchingTabCountsResponse,
    ReconciliationRunRequest,
    ReconciliationSummary,
    RejectMatchRequest,
)
from services.matching_service import MatchingService
from utils.user_display import approver_paid_by

logger = get_logger(__name__)

_MATCH_NOT_FOUND = HTTPException(
    status_code=404,
    detail={
        "error": "match_not_found",
        "message": "Match not found.",
    },
)


_TAB_COUNTS_TTL_SECONDS = 30


def _invalidate_matching_tab_counts() -> None:
    cache.delete_pattern("matching_tab_counts:*")
    cache.delete_pattern("invoice_tab_counts:*")


class ReconciliationController:
    def __init__(
        self,
        matching_service: MatchingService,
        match_repo: MatchRepository,
        invoice_repo: InvoiceRepository,
        statement_repo: BankStatementRepository,
        bank_txn_repo: BankTransactionRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._matching = matching_service
        self._match_repo = match_repo
        self._invoice_repo = invoice_repo
        self._statement_repo = statement_repo
        self._bank_txn_repo = bank_txn_repo
        self._audit_repo = audit_repo

    async def _require_owned_match(
        self, match_id: int, user: UserContext
    ) -> InvoicePaymentMatch:
        row = await self._match_repo.get(match_id)
        if not row:
            raise _MATCH_NOT_FOUND
        owner = invoice_owner_user_id(user)
        invoice = await self._invoice_repo.get_owned_row(
            row.invoice_id,
            owner_user_id=owner,
        )
        if not invoice:
            raise _MATCH_NOT_FOUND
        return row

    async def _ensure_match_paid_amount(self, row: InvoicePaymentMatch) -> None:
        if row.paid_amount is not None:
            return
        txn = await self._bank_txn_repo.get(row.bank_transaction_id)
        if txn is None:
            return
        txn_amount = txn.credited_amount or txn.debited_amount
        if txn_amount is None:
            return
        await self._match_repo.set_paid_amount_if_missing(
            row.id, Decimal(str(txn_amount))
        )

    async def _recalculate_invoice_payment(
        self, invoice_id: int, user: UserContext
    ) -> str:
        owner = invoice_owner_user_id(user)
        invoice = await self._invoice_repo.get_owned_row(
            invoice_id, owner_user_id=owner
        )
        if invoice is None or invoice.amount is None:
            await self._invoice_repo.update_match_status(invoice_id, "matched")
            return "matched"

        total_paid = await self._match_repo.sum_paid_for_invoice(invoice_id)
        remaining = max(Decimal(str(invoice.amount)) - total_paid, Decimal("0"))
        await self._invoice_repo.update_debt(invoice_id, remaining)
        new_status = "matched" if remaining <= 0 else "partially_matched"
        await self._invoice_repo.update_match_status(invoice_id, new_status)
        return new_status

    async def _reset_bank_transaction_if_unmatched(
        self, bank_transaction_id: int
    ) -> None:
        if await self._match_repo.active_for_transaction(bank_transaction_id):
            return
        await self._bank_txn_repo.update_reconciliation_status(
            bank_transaction_id, "needs_review"
        )

    @debug_trace
    async def run(
        self, request: ReconciliationRunRequest, user: UserContext
    ) -> ReconciliationSummary:
        owner = upload_owner_user_id(user)
        if request.bank_statement_id is not None and owner is not None:
            stmt = await self._statement_repo.get(
                request.bank_statement_id,
                owner_user_id=owner,
            )
            if stmt is None:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "bank_statement_not_found",
                        "message": "Bank statement not found.",
                    },
                )
        return await self._matching.run(
            request.bank_statement_id,
            owner_user_id=invoice_owner_user_id(user),
        )

    @debug_trace
    async def results(
        self,
        user: UserContext,
        status: str | None,
        bank_statement_id: int | None,
        page: int,
        limit: int,
        *,
        confirmed_only: bool = False,
    ) -> MatchListResponse:
        items, total = await self._match_repo.list_matches(
            status,
            bank_statement_id,
            page,
            limit,
            owner_user_id=invoice_owner_user_id(user),
            confirmed_only=confirmed_only,
        )
        return MatchListResponse(
            items=items, total=total, page=page, limit=limit
        )

    @debug_trace
    async def tab_counts(
        self,
        user: UserContext,
        bank_statement_id: int | None,
    ) -> MatchingTabCountsResponse:
        owner_invoice = invoice_owner_user_id(user)
        owner_upload = upload_owner_user_id(user)
        cache_key = (
            f"matching_tab_counts:{owner_invoice}:{owner_upload}:{bank_statement_id}"
        )
        cached = cache.get_model(cache_key, MatchingTabCountsResponse)
        if cached is not None:
            return cached
        (
            matched,
            partially_matched,
            unmatched_invoices,
            unmatched_transactions,
            needs_review,
            multi_invoice,
        ) = await asyncio.gather(
            self._match_repo.count_matches(
                None,
                bank_statement_id,
                owner_user_id=owner_invoice,
                confirmed_only=True,
            ),
            self._invoice_repo.count_by_match_status(
                "partially_matched",
                owner_user_id=owner_invoice,
            ),
            self._invoice_repo.count_by_match_status(
                "unmatched",
                owner_user_id=owner_invoice,
            ),
            self._bank_txn_repo.count_transactions(
                bank_statement_id,
                "needs_review",
                owner_user_id=owner_upload,
            ),
            self._invoice_repo.count_by_match_statuses(
                ["unmatched", "needs_review"],
                owner_user_id=owner_invoice,
            ),
            self._bank_txn_repo.count_transactions(
                bank_statement_id,
                None,
                owner_user_id=owner_upload,
                multi_invoice=True,
            ),
        )
        response = MatchingTabCountsResponse(
            matched=matched,
            partially_matched=partially_matched,
            unmatched_invoices=unmatched_invoices,
            unmatched_transactions=unmatched_transactions,
            needs_review=needs_review,
            multi_invoice=multi_invoice,
        )
        cache.set_model(cache_key, response, ttl_seconds=_TAB_COUNTS_TTL_SECONDS)
        return response

    @debug_trace
    async def manual_match(
        self, body: ManualMatchRequest, user: UserContext
    ) -> ManualMatchResponse:
        response = await self._matching.manual_match(
            body.invoice_id,
            body.bank_transaction_id,
            user,
            review_task_id=body.review_task_id,
            paid_amount=body.paid_amount,
        )
        cache.delete_pattern("review:*")
        cache.delete_pattern("bank_tx:*")
        _invalidate_matching_tab_counts()
        return response

    @debug_trace
    async def approve_match(
        self, body: ApproveMatchRequest, user: UserContext
    ) -> MatchActionResponse:
        row = await self._require_owned_match(body.match_id, user)
        if row.status in ("approved", "rejected"):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "match_already_resolved",
                    "message": "Match already approved or rejected.",
                },
            )
        updated = await self._match_repo.approve(body.match_id)
        if not updated:
            raise HTTPException(
                status_code=500,
                detail={"error": "approve_failed", "message": "Could not approve match."},
            )
        await self._ensure_match_paid_amount(row)
        await self._invoice_repo.update_paid_at_date(row.invoice_id, row.paid_at_date)
        await self._invoice_repo.update_paid_by(
            row.invoice_id, approver_paid_by(user)
        )
        row = await self._match_repo.get(body.match_id) or row
        paid = row.paid_amount
        if paid is not None:
            total_paid = await self._match_repo.sum_paid_for_invoice(row.invoice_id)
            owner = invoice_owner_user_id(user)
            invoice = await self._invoice_repo.get_owned_row(
                row.invoice_id, owner_user_id=owner
            )
            if invoice and invoice.amount is not None and total_paid >= Decimal(
                str(invoice.amount)
            ):
                await self._invoice_repo.settle_invoice_from_transaction(
                    row.invoice_id, Decimal(str(paid))
                )
            else:
                await self._recalculate_invoice_payment(row.invoice_id, user)
        else:
            await self._recalculate_invoice_payment(row.invoice_id, user)
        await self._audit_repo.log(
            user.user_id,
            "match_approved",
            "invoice_payment_match",
            body.match_id,
            {"status": row.status},
            {"status": "approved"},
        )
        cache.delete_pattern("review:*")
        cache.delete_pattern("bank_tx:*")
        _invalidate_matching_tab_counts()
        return MatchActionResponse(match_id=body.match_id, status=updated.status)

    @debug_trace
    async def reject_match(
        self, body: RejectMatchRequest, user: UserContext
    ) -> MatchActionResponse:
        row = await self._require_owned_match(body.match_id, user)
        if row.status in ("approved", "rejected"):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "match_already_resolved",
                    "message": "Match already approved or rejected.",
                },
            )
        owner = invoice_owner_user_id(user)
        invoice_id = row.invoice_id
        bank_transaction_id = row.bank_transaction_id
        status_before = row.status
        before_invoice = await self._invoice_repo.get(
            invoice_id,
            owner_user_id=owner,
        )
        deleted = await self._match_repo.delete(body.match_id)
        if not deleted:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "reject_failed",
                    "message": "Could not reject match.",
                },
            )
        if status_before == "suggested":
            await self._audit_repo.log(
                user.user_id,
                "match_rejected",
                "invoice_payment_match",
                body.match_id,
                {"status": "suggested"},
                {"status": "deleted", "reason": body.reason},
            )
            await self._reset_bank_transaction_if_unmatched(bank_transaction_id)
            cache.delete_pattern("review:*")
            cache.delete_pattern("bank_tx:*")
            _invalidate_matching_tab_counts()
            return MatchActionResponse(match_id=body.match_id, status="rejected")

        remaining_matches = await self._match_repo.list_active_for_invoice(
            invoice_id
        )
        new_match_status = "needs_review"
        if remaining_matches:
            total_paid = sum(
                (m.paid_amount for m in remaining_matches if m.paid_amount is not None),
                Decimal("0"),
            )
            inv_amount = before_invoice.amount if before_invoice else None
            if inv_amount is not None:
                remaining = max(Decimal(str(inv_amount)) - total_paid, Decimal("0"))
                await self._invoice_repo.update_debt(invoice_id, remaining)
                new_match_status = (
                    "matched" if remaining <= 0 else "partially_matched"
                )
            else:
                new_match_status = "partially_matched"
            await self._invoice_repo.update_match_status(
                invoice_id, new_match_status
            )
        else:
            await self._invoice_repo.clear_paid_at_date(invoice_id)
            await self._invoice_repo.update_match_status(invoice_id, "needs_review")
            await self._invoice_repo.flag_for_review(
                invoice_id,
                "bank_match_failed",
                match_status="needs_review",
            )

        await self._reset_bank_transaction_if_unmatched(bank_transaction_id)

        await self._audit_repo.log(
            user.user_id,
            "match_rejected",
            "invoice",
            invoice_id,
            {
                "paid_at_date": str(before_invoice.paid_at_date)
                if before_invoice and before_invoice.paid_at_date
                else None,
                "match_id": body.match_id,
            },
            {
                "match_status": new_match_status,
                "reason": body.reason,
            },
        )
        cache.delete_pattern("review:*")
        cache.delete_pattern("bank_tx:*")
        _invalidate_matching_tab_counts()
        return MatchActionResponse(match_id=body.match_id, status="rejected")

