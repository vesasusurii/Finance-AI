from datetime import datetime, timezone

from fastapi import HTTPException

from core.debug_logger import debug_trace, get_logger
from core.invoice_access import invoice_owner_user_id, upload_owner_user_id
from models.review_task import ReviewTask
from repositories.audit_repository import AuditRepository
from repositories.bank_transaction_repository import BankTransactionRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.review_repository import ReviewRepository
from schemas.auth import UserContext
from schemas.bank_statement import BankTransactionResponse
from schemas.invoice import InvoiceResponse
from schemas.review import (
    ReviewTaskDecisionResponse,
    ReviewTaskListResponse,
    ReviewTaskResponse,
)
from utils.normalization import normalize_invoice_number
from utils.user_display import approver_paid_by

logger = get_logger(__name__)


class ReviewService:
    def __init__(
        self,
        review_repo: ReviewRepository,
        invoice_repo: InvoiceRepository,
        bank_txn_repo: BankTransactionRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._review_repo = review_repo
        self._invoice_repo = invoice_repo
        self._bank_txn_repo = bank_txn_repo
        self._audit_repo = audit_repo

    async def _require_owned_task(
        self, task_id: int, user: UserContext
    ) -> ReviewTask:
        owner = upload_owner_user_id(user)
        task = await self._review_repo.get(task_id)
        if not task:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "review_task_not_found",
                    "message": "Review task not found.",
                },
            )
        if owner is not None and not await self._review_repo.is_visible_to_user(
            task_id, owner
        ):
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "review_task_not_found",
                    "message": "Review task not found.",
                },
            )
        return task

    @debug_trace
    async def _enrich_task(
        self,
        item: ReviewTaskResponse,
        *,
        owner_user_id: int | None = None,
    ) -> ReviewTaskResponse:
        invoice: InvoiceResponse | None = None
        bank_transaction: BankTransactionResponse | None = None
        invoice_scope = owner_user_id
        if item.invoice_id is not None:
            invoice = await self._invoice_repo.get(
                item.invoice_id, owner_user_id=invoice_scope
            )
        elif item.task_type == "bank_match":
            payload_num = (item.payload or {}).get("invoice_number")
            if isinstance(payload_num, str) and payload_num.strip():
                key = normalize_invoice_number(payload_num.strip())
                found, ambiguous = await self._invoice_repo.find_by_number(key)
                if found and not ambiguous:
                    invoice = found
        if item.bank_transaction_id is not None:
            bank_transaction = await self._bank_txn_repo.get(
                item.bank_transaction_id
            )
        return item.model_copy(
            update={
                "invoice": invoice,
                "bank_transaction": bank_transaction,
            }
        )

    @debug_trace
    async def list_open(
        self,
        task_type: str | None,
        page: int,
        limit: int,
        *,
        owner_user_id: int | None = None,
        has_invoice: bool | None = None,
        reasons: list[str] | None = None,
        enrich: bool = True,
    ) -> ReviewTaskListResponse:
        if has_invoice is not None:
            # Invoice-centric vs bank-line-only queues require enrichment.
            fetch_limit = min(500, max(limit * 10, 200))
            items, _ = await self._review_repo.list_open(
                task_type,
                page=1,
                limit=fetch_limit,
                owner_user_id=owner_user_id,
                reasons=reasons,
            )
            enriched_all: list[ReviewTaskResponse] = []
            for item in items:
                row = await self._enrich_task(item, owner_user_id=owner_user_id)
                if has_invoice and row.invoice is not None:
                    enriched_all.append(row)
                elif not has_invoice and row.invoice is None:
                    enriched_all.append(row)
            total = len(enriched_all)
            offset = (page - 1) * limit
            page_items = enriched_all[offset : offset + limit]
            return ReviewTaskListResponse(
                items=page_items, total=total, page=page, limit=limit
            )

        items, total = await self._review_repo.list_open(
            task_type, page, limit, owner_user_id=owner_user_id, reasons=reasons
        )
        if enrich:
            enriched = [
                await self._enrich_task(item, owner_user_id=owner_user_id)
                for item in items
            ]
        else:
            enriched = items
        return ReviewTaskListResponse(
            items=enriched, total=total, page=page, limit=limit
        )

    @debug_trace
    async def approve(
        self, task_id: int, user: UserContext
    ) -> ReviewTaskDecisionResponse:
        task = await self._require_owned_task(task_id, user)
        if task.status != "open":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "review_task_already_resolved",
                    "message": "Review task is already resolved.",
                },
            )

        before = {
            "status": task.status,
            "task_type": task.task_type,
            "reason": task.reason,
        }

        if task.task_type == "extraction":
            if task.invoice_id is None:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "missing_invoice",
                        "message": "Extraction task has no linked invoice.",
                    },
                )
            approved = await self._invoice_repo.approve(
                task.invoice_id,
                owner_user_id=invoice_owner_user_id(user),
                paid_by=approver_paid_by(user),
            )
            if not approved:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "invoice_not_found",
                        "message": "Linked invoice not found.",
                    },
                )
        elif task.task_type == "bank_match":
            # Finance acknowledges the unmatched bank reference. No paid_at_date
            # or match record is created here — that requires reconciliation
            # approve-match after a real match exists.
            pass
        else:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "unknown_task_type",
                    "message": f"Unknown task type: {task.task_type}",
                },
            )

        now = datetime.now(timezone.utc)
        await self._review_repo.resolve(task_id, "approved", now)
        await self._audit_repo.log(
            user.user_id,
            "review_approved",
            "review_task",
            task_id,
            before,
            {"status": "approved", "resolved_at": now.isoformat()},
        )
        if task.task_type == "extraction" and task.invoice_id is not None:
            await self._audit_repo.log(
                user.user_id,
                "invoice_approved",
                "invoice",
                task.invoice_id,
                None,
                {"review_status": "approved", "via": "review_task", "task_id": task_id},
            )

        return ReviewTaskDecisionResponse(
            review_task_id=task_id,
            status="approved",
            resolved_at=now,
        )

    @debug_trace
    async def reject(
        self, task_id: int, reason: str | None, user: UserContext
    ) -> ReviewTaskDecisionResponse:
        task = await self._require_owned_task(task_id, user)
        if task.status != "open":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "review_task_already_resolved",
                    "message": "Review task is already resolved.",
                },
            )

        before = {
            "status": task.status,
            "task_type": task.task_type,
            "reason": task.reason,
        }
        now = datetime.now(timezone.utc)
        await self._review_repo.resolve(task_id, "rejected", now)
        await self._audit_repo.log(
            user.user_id,
            "review_rejected",
            "review_task",
            task_id,
            before,
            {
                "status": "rejected",
                "resolved_at": now.isoformat(),
                "reason": reason,
            },
        )
        return ReviewTaskDecisionResponse(
            review_task_id=task_id,
            status="rejected",
            resolved_at=now,
        )
