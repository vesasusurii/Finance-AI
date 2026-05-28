from fastapi import HTTPException

from core.debug_logger import debug_trace, get_logger
from repositories.audit_repository import AuditRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.match_repository import MatchRepository
from schemas.auth import UserContext
from schemas.reconciliation import (
    ApproveMatchRequest,
    MatchActionResponse,
    MatchListResponse,
    ReconciliationRunRequest,
    ReconciliationSummary,
    RejectMatchRequest,
)
from services.matching_service import MatchingService

logger = get_logger(__name__)


class ReconciliationController:
    def __init__(
        self,
        matching_service: MatchingService,
        match_repo: MatchRepository,
        invoice_repo: InvoiceRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._matching = matching_service
        self._match_repo = match_repo
        self._invoice_repo = invoice_repo
        self._audit_repo = audit_repo

    @debug_trace
    async def run(
        self, request: ReconciliationRunRequest, user: UserContext
    ) -> ReconciliationSummary:
        return await self._matching.run(request.bank_statement_id)

    @debug_trace
    async def results(
        self,
        status: str | None,
        bank_statement_id: int | None,
        page: int,
        limit: int,
    ) -> MatchListResponse:
        items, total = await self._match_repo.list_matches(
            status, bank_statement_id, page, limit
        )
        return MatchListResponse(
            items=items, total=total, page=page, limit=limit
        )

    @debug_trace
    async def approve_match(
        self, body: ApproveMatchRequest, user: UserContext
    ) -> MatchActionResponse:
        row = await self._match_repo.get(body.match_id)
        if not row:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "match_not_found",
                    "message": "Match not found.",
                },
            )
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
        await self._audit_repo.log(
            user.user_id,
            "match_approved",
            "invoice_payment_match",
            body.match_id,
            {"status": row.status},
            {"status": "approved"},
        )
        return MatchActionResponse(match_id=body.match_id, status=updated.status)

    @debug_trace
    async def reject_match(
        self, body: RejectMatchRequest, user: UserContext
    ) -> MatchActionResponse:
        row = await self._match_repo.get(body.match_id)
        if not row:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "match_not_found",
                    "message": "Match not found.",
                },
            )
        if row.status in ("approved", "rejected"):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "match_already_resolved",
                    "message": "Match already approved or rejected.",
                },
            )
        before_paid = await self._invoice_repo.get(row.invoice_id)
        await self._match_repo.reject(body.match_id)
        await self._invoice_repo.clear_paid_at_date(row.invoice_id)
        await self._invoice_repo.update_match_status(row.invoice_id, "needs_review")
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
        return MatchActionResponse(match_id=body.match_id, status="rejected")
