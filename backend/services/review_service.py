from datetime import datetime, timezone

from fastapi import HTTPException

from core.debug_logger import debug_trace, get_logger
from core.invoice_access import invoice_owner_user_id, upload_owner_user_id
from models.review_task import ReviewTask
from repositories.audit_repository import AuditRepository
from repositories.bank_statement_repository import BankStatementRepository
from repositories.bank_transaction_repository import BankTransactionRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.review_repository import ReviewRepository
from schemas.auth import UserContext
from schemas.bank_statement import BankTransactionResponse
from schemas.invoice import InvoiceResponse
from schemas.review import (
    ManualReviewEntryResponse,
    ManualReviewQueueResponse,
    BankMatchCandidatesResponse,
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
        statement_repo: BankStatementRepository,
    ) -> None:
        self._review_repo = review_repo
        self._invoice_repo = invoice_repo
        self._bank_txn_repo = bank_txn_repo
        self._audit_repo = audit_repo
        self._statement_repo = statement_repo

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
    async def _enrich_tasks(
        self,
        items: list[ReviewTaskResponse],
        *,
        owner_user_id: int | None = None,
    ) -> list[ReviewTaskResponse]:
        if not items:
            return []

        invoice_ids = [i.invoice_id for i in items if i.invoice_id is not None]
        txn_ids = [
            i.bank_transaction_id for i in items if i.bank_transaction_id is not None
        ]
        invoices_map = await self._invoice_repo.get_many(
            invoice_ids, owner_user_id=owner_user_id
        )
        txns_map = await self._bank_txn_repo.get_many(txn_ids)

        enriched: list[ReviewTaskResponse] = []
        for item in items:
            invoice: InvoiceResponse | None = None
            if item.invoice_id is not None:
                invoice = invoices_map.get(item.invoice_id)
            elif item.task_type == "bank_match":
                payload_num = (item.payload or {}).get("invoice_number")
                if isinstance(payload_num, str) and payload_num.strip():
                    key = normalize_invoice_number(payload_num.strip())
                    found, ambiguous = await self._invoice_repo.find_by_number(key)
                    if found and not ambiguous:
                        invoice = found
            bank_transaction: BankTransactionResponse | None = None
            if item.bank_transaction_id is not None:
                bank_transaction = txns_map.get(item.bank_transaction_id)
            enriched.append(
                item.model_copy(
                    update={
                        "invoice": invoice,
                        "bank_transaction": bank_transaction,
                    }
                )
            )
        return enriched

    @debug_trace
    async def _enrich_task(
        self,
        item: ReviewTaskResponse,
        *,
        owner_user_id: int | None = None,
    ) -> ReviewTaskResponse:
        rows = await self._enrich_tasks([item], owner_user_id=owner_user_id)
        return rows[0]

    @debug_trace
    async def manual_queue(
        self,
        queue_filter: str,
        page: int,
        limit: int,
        *,
        invoice_owner_user_id: int | None = None,
        upload_owner_user_id: int | None = None,
    ) -> ManualReviewQueueResponse:
        if queue_filter == "extraction":
            return await self._manual_queue_extraction(
                page,
                limit,
                upload_owner_user_id=upload_owner_user_id,
                invoice_owner_user_id=invoice_owner_user_id,
            )
        if queue_filter == "bank_match":
            return await self._manual_queue_bank_match(
                page,
                limit,
                upload_owner_user_id=upload_owner_user_id,
                invoice_owner_user_id=invoice_owner_user_id,
            )
        return await self._manual_queue_all(
            page,
            limit,
            upload_owner_user_id=upload_owner_user_id,
            invoice_owner_user_id=invoice_owner_user_id,
        )

    async def _manual_queue_extraction(
        self,
        page: int,
        limit: int,
        *,
        upload_owner_user_id: int | None,
        invoice_owner_user_id: int | None,
    ) -> ManualReviewQueueResponse:
        items, total = await self._review_repo.list_open(
            "extraction", page, limit, owner_user_id=upload_owner_user_id
        )
        enriched = await self._enrich_tasks(
            items, owner_user_id=invoice_owner_user_id
        )
        entries = [
            ManualReviewEntryResponse(
                key=f"task-{item.id}",
                mode="extraction",
                invoice=item.invoice,
                task=item,
            )
            for item in enriched
            if item.invoice is not None
        ]
        return ManualReviewQueueResponse(
            items=entries, total=total, page=page, limit=limit
        )

    async def _manual_queue_bank_match(
        self,
        page: int,
        limit: int,
        *,
        upload_owner_user_id: int | None,
        invoice_owner_user_id: int | None,
    ) -> ManualReviewQueueResponse:
        invoices, total = await self._invoice_repo.list_invoices(
            {
                "match_statuses": ["unmatched", "needs_review"],
                "sort": "updated_at_desc",
            },
            page,
            limit,
            owner_user_id=invoice_owner_user_id,
        )
        invoice_ids = [inv.id for inv in invoices]
        tasks = await self._review_repo.list_open_for_invoice_ids(
            invoice_ids, owner_user_id=upload_owner_user_id
        )
        enriched_tasks = await self._enrich_tasks(
            tasks, owner_user_id=invoice_owner_user_id
        )
        task_by_invoice = {
            task.invoice_id: task
            for task in enriched_tasks
            if task.invoice_id is not None
        }
        entries = [
            ManualReviewEntryResponse(
                key=f"inv-{invoice.id}",
                mode="bank_match",
                invoice=invoice,
                task=task_by_invoice.get(invoice.id),
            )
            for invoice in invoices
        ]
        return ManualReviewQueueResponse(
            items=entries, total=total, page=page, limit=limit
        )

    async def _manual_queue_all(
        self,
        page: int,
        limit: int,
        *,
        upload_owner_user_id: int | None,
        invoice_owner_user_id: int | None,
    ) -> ManualReviewQueueResponse:
        fetch_limit = min(200, max(limit, page * limit))
        bank = await self._manual_queue_bank_match(
            1,
            fetch_limit,
            upload_owner_user_id=upload_owner_user_id,
            invoice_owner_user_id=invoice_owner_user_id,
        )
        extraction = await self._manual_queue_extraction(
            1,
            fetch_limit,
            upload_owner_user_id=upload_owner_user_id,
            invoice_owner_user_id=invoice_owner_user_id,
        )
        seen: set[int] = set()
        merged: list[ManualReviewEntryResponse] = []
        for entry in [*extraction.items, *bank.items]:
            if entry.invoice.id in seen:
                continue
            seen.add(entry.invoice.id)
            merged.append(entry)
        merged.sort(
            key=lambda e: e.invoice.updated_at,
            reverse=True,
        )
        offset = (page - 1) * limit
        page_items = merged[offset : offset + limit]
        return ManualReviewQueueResponse(
            items=page_items,
            total=len(merged),
            page=page,
            limit=limit,
        )

    @debug_trace
    async def bank_match_candidates(
        self,
        invoice_id: int,
        *,
        bank_statement_id: int | None,
        invoice_owner_user_id: int | None,
        upload_owner_user_id: int | None,
        limit: int = 100,
    ) -> BankMatchCandidatesResponse:
        invoice = await self._invoice_repo.get(
            invoice_id, owner_user_id=invoice_owner_user_id
        )
        if invoice is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invoice_not_found",
                    "message": "Invoice not found.",
                },
            )

        statement_id = bank_statement_id
        if statement_id is None:
            stmts, _ = await self._statement_repo.list_statements(
                1, 1, owner_user_id=upload_owner_user_id
            )
            if stmts:
                statement_id = stmts[0].id

        items = await self._bank_txn_repo.list_reconciliation_candidates(
            bank_statement_id=statement_id,
            owner_user_id=upload_owner_user_id,
            limit=limit,
        )
        return BankMatchCandidatesResponse(
            items=items,
            bank_statement_id=statement_id,
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
            enriched_all = await self._enrich_tasks(
                items, owner_user_id=owner_user_id
            )
            filtered: list[ReviewTaskResponse] = []
            for row in enriched_all:
                if has_invoice and row.invoice is not None:
                    filtered.append(row)
                elif not has_invoice and row.invoice is None:
                    filtered.append(row)
            total = len(filtered)
            offset = (page - 1) * limit
            page_items = filtered[offset : offset + limit]
            return ReviewTaskListResponse(
                items=page_items, total=total, page=page, limit=limit
            )

        items, total = await self._review_repo.list_open(
            task_type, page, limit, owner_user_id=owner_user_id, reasons=reasons
        )
        if enrich:
            enriched = await self._enrich_tasks(
                items, owner_user_id=owner_user_id
            )
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
