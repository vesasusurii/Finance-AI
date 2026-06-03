from fastapi import HTTPException

from core.cache import cache
from core.debug_logger import debug_trace, get_logger
from core.invoice_access import invoice_owner_user_id, upload_owner_user_id
from models.invoice_payment_match import InvoicePaymentMatch
from repositories.audit_repository import AuditRepository
from repositories.bank_statement_repository import BankStatementRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.match_repository import MatchRepository
from schemas.auth import UserContext
from schemas.reconciliation import (
    ApproveMatchRequest,
    ManualMatchRequest,
    ManualMatchResponse,
    MatchActionResponse,
    MatchListResponse,
    ReconciliationRunRequest,
    ReconciliationSummary,
    RejectMatchRequest,
)
from services.matching_service import MatchingService

logger = get_logger(__name__)

_MATCH_NOT_FOUND = HTTPException(
    status_code=404,
    detail={
        "error": "match_not_found",
        "message": "Match not found.",
    },
)


class ReconciliationController:
    def __init__(
        self,
        matching_service: MatchingService,
        match_repo: MatchRepository,
        invoice_repo: InvoiceRepository,
        statement_repo: BankStatementRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._matching = matching_service
        self._match_repo = match_repo
        self._invoice_repo = invoice_repo
        self._statement_repo = statement_repo
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
    ) -> MatchListResponse:
        items, total = await self._match_repo.list_matches(
            status,
            bank_statement_id,
            page,
            limit,
            owner_user_id=invoice_owner_user_id(user),
        )
        return MatchListResponse(
            items=items, total=total, page=page, limit=limit
        )

    @debug_trace
    async def manual_match(
        self, body: ManualMatchRequest, user: UserContext
    ) -> ManualMatchResponse:
        response = await self._matching.manual_match(
            body.invoice_id,
            body.bank_transaction_id,
            user,
            review_task_id=body.review_task_id,
        )
        cache.delete_pattern("review:*")
        cache.delete_pattern("bank_tx:*")
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
        if row.status == "suggested":
            await self._invoice_repo.update_paid_at_date(
                row.invoice_id, row.paid_at_date
            )
            await self._invoice_repo.update_match_status(row.invoice_id, "matched")
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
        before_paid = await self._invoice_repo.get(
            row.invoice_id,
            owner_user_id=owner,
        )
        await self._match_repo.reject(body.match_id)
        if row.status == "suggested":
            await self._audit_repo.log(
                user.user_id,
                "match_rejected",
                "invoice_payment_match",
                body.match_id,
                {"status": "suggested"},
                {"status": "rejected", "reason": body.reason},
            )
            cache.delete_pattern("review:*")
            cache.delete_pattern("bank_tx:*")
            return MatchActionResponse(match_id=body.match_id, status="rejected")
        await self._invoice_repo.clear_paid_at_date(row.invoice_id)
        await self._invoice_repo.update_match_status(row.invoice_id, "needs_review")
        await self._invoice_repo.flag_for_review(
            row.invoice_id,
            "bank_match_failed",
            match_status="needs_review",
        )
        await self._audit_repo.log(
            user.user_id,
            "match_rejected",
            "invoice",
            row.invoice_id,
            {
                "paid_at_date": str(before_paid.paid_at_date)
                if before_paid and before_paid.paid_at_date
                else None,
                "match_id": body.match_id,
            },
            {
                "paid_at_date": None,
                "match_status": "needs_review",
                "reason": body.reason,
            },
        )
        cache.delete_pattern("review:*")
        cache.delete_pattern("bank_tx:*")
        return MatchActionResponse(match_id=body.match_id, status="rejected")
