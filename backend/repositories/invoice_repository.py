from __future__ import annotations

import time
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.debug_logger import get_logger
from models.invoice import Invoice
from schemas.invoice import ExtractionResult, InvoiceResponse, InvoiceUpdate
from sqlalchemy.orm import joinedload
from core.invoice_access import apply_invoice_visibility, user_may_delete_invoice
from utils.normalization import normalize_invoice_number

logger = get_logger(__name__)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _to_response(row: Invoice) -> InvoiceResponse:
    data = InvoiceResponse.model_validate(row)
    upload = row.source_file
    if upload is None:
        return data
    return data.model_copy(
        update={
            "source_filename": upload.original_filename,
            "source_mime_type": upload.mime_type,
        }
    )


def _apply_owner_scope(query, owner_user_id: int | None):
    return apply_invoice_visibility(query, owner_user_id)


class InvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        data: ExtractionResult,
        source_file_id: int,
        review_status: str,
        uploaded_by: int,
    ) -> InvoiceResponse:
        formatted = normalize_invoice_number(data.invoice_number)
        row = Invoice(
            invoice_date=_parse_date(data.invoice_date),
            name_of_company=data.name_of_company,
            address_of_company=data.address_of_company,
            invoice_number=formatted,
            invoice_number_normalized=formatted,
            amount=Decimal(str(data.amount)) if data.amount is not None else None,
            debt=Decimal(str(data.debt)) if data.debt is not None else None,
            currency=data.currency,
            account_details=data.account_details,
            internal_note_description=data.internal_note_description,
            client_employee_related=data.client_employee_related,
            category=data.category,
            extraction_confidence=Decimal(str(round(data.confidence_score, 4))),
            field_confidences=data.field_confidences,
            review_reasons=data.review_reasons or None,
            review_status=review_status,
            match_status="unmatched",
            source_file_id=source_file_id,
            uploaded_by=uploaded_by,
        )
        self._session.add(row)
        await self._session.flush()
        return await self.get(row.id, owner_user_id=None)  # type: ignore[return-value]

    async def get_id_by_source_file(self, source_file_id: int) -> int | None:
        query = (
            select(Invoice.id)
            .where(Invoice.source_file_id == source_file_id)
            .limit(1)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get(
        self,
        invoice_id: int,
        *,
        owner_user_id: int | None = None,
    ) -> InvoiceResponse | None:
        query = (
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(joinedload(Invoice.source_file))
        )
        query = _apply_owner_scope(query, owner_user_id)
        result = await self._session.execute(query)
        row = result.scalar_one_or_none()
        return _to_response(row) if row else None

    async def get_many(
        self,
        invoice_ids: list[int],
        *,
        owner_user_id: int | None = None,
    ) -> dict[int, InvoiceResponse]:
        ids = sorted(set(invoice_ids))
        if not ids:
            return {}
        query = (
            select(Invoice)
            .where(Invoice.id.in_(ids))
            .options(joinedload(Invoice.source_file))
        )
        query = _apply_owner_scope(query, owner_user_id)
        result = await self._session.execute(query)
        return {row.id: _to_response(row) for row in result.scalars().all()}

    async def list_invoices(
        self,
        filters: dict,
        page: int,
        limit: int,
        *,
        owner_user_id: int | None = None,
    ) -> tuple[list[InvoiceResponse], int]:
        query = select(Invoice).options(joinedload(Invoice.source_file))
        count_query = select(func.count()).select_from(Invoice)

        query = _apply_owner_scope(query, owner_user_id)
        count_query = _apply_owner_scope(count_query, owner_user_id)

        if filters.get("review_status"):
            query = query.where(Invoice.review_status == filters["review_status"])
            count_query = count_query.where(
                Invoice.review_status == filters["review_status"]
            )
        if filters.get("match_status"):
            query = query.where(Invoice.match_status == filters["match_status"])
            count_query = count_query.where(
                Invoice.match_status == filters["match_status"]
            )
        if filters.get("invoice_date_from"):
            query = query.where(Invoice.invoice_date >= filters["invoice_date_from"])
            count_query = count_query.where(
                Invoice.invoice_date >= filters["invoice_date_from"]
            )
        if filters.get("invoice_date_to"):
            query = query.where(Invoice.invoice_date <= filters["invoice_date_to"])
            count_query = count_query.where(
                Invoice.invoice_date <= filters["invoice_date_to"]
            )
        if filters.get("company"):
            pattern = f"%{filters['company']}%"
            query = query.where(Invoice.name_of_company.ilike(pattern))
            count_query = count_query.where(Invoice.name_of_company.ilike(pattern))
        if filters.get("category"):
            pattern = f"%{filters['category']}%"
            query = query.where(Invoice.category.ilike(pattern))
            count_query = count_query.where(Invoice.category.ilike(pattern))

        sort = filters.get("sort", "id")
        if sort == "created_at":
            query = query.order_by(Invoice.created_at.desc())
        else:
            query = query.order_by(Invoice.id.desc())

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        db_t0 = time.perf_counter()
        total = (await self._session.execute(count_query)).scalar_one()
        rows = (await self._session.execute(query)).scalars().all()
        db_query_ms = round((time.perf_counter() - db_t0) * 1000, 1)
        if db_query_ms >= settings.slow_route_ms:
            logger.warning(
                "Slow invoice list query db_query_ms=%s page=%d limit=%d filters=%s total=%d",
                db_query_ms,
                page,
                limit,
                sorted(filters.keys()),
                int(total),
            )
        return [_to_response(r) for r in rows], int(total)

    async def list_invoices_for_export(
        self,
        filters: dict,
        *,
        owner_user_id: int | None = None,
        max_rows: int = 10_000,
    ) -> list[InvoiceResponse]:
        query = select(Invoice).options(joinedload(Invoice.source_file))
        query = _apply_owner_scope(query, owner_user_id)

        if filters.get("review_status"):
            query = query.where(Invoice.review_status == filters["review_status"])
        if filters.get("match_status"):
            query = query.where(Invoice.match_status == filters["match_status"])
        if filters.get("invoice_date_from"):
            query = query.where(Invoice.invoice_date >= filters["invoice_date_from"])
        if filters.get("invoice_date_to"):
            query = query.where(Invoice.invoice_date <= filters["invoice_date_to"])
        if filters.get("company"):
            pattern = f"%{filters['company']}%"
            query = query.where(Invoice.name_of_company.ilike(pattern))
        if filters.get("category"):
            pattern = f"%{filters['category']}%"
            query = query.where(Invoice.category.ilike(pattern))

        query = query.order_by(
            Invoice.invoice_date.desc().nulls_last(),
            Invoice.id.desc(),
        ).limit(max_rows)

        rows = (await self._session.execute(query)).scalars().all()
        return [_to_response(r) for r in rows]

    async def update(
        self,
        invoice_id: int,
        data: InvoiceUpdate,
        *,
        owner_user_id: int | None = None,
    ) -> InvoiceResponse | None:
        row = await self._get_row(invoice_id, owner_user_id=owner_user_id)
        if not row:
            return None
        payload = data.model_dump(exclude_unset=True)
        if "invoice_number" in payload:
            formatted = normalize_invoice_number(payload["invoice_number"])
            payload["invoice_number"] = formatted
            row.invoice_number_normalized = formatted
        for key, value in payload.items():
            setattr(row, key, value)
        await self._session.flush()
        return await self.get(invoice_id, owner_user_id=owner_user_id)

    async def delete(
        self,
        invoice_id: int,
        *,
        owner_user_id: int | None = None,
    ) -> bool:
        row = await self._get_row(invoice_id, owner_user_id=owner_user_id)
        if not row:
            return False
        if owner_user_id is not None and not user_may_delete_invoice(
            row.uploaded_by, owner_user_id
        ):
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def approve(
        self,
        invoice_id: int,
        *,
        owner_user_id: int | None = None,
    ) -> InvoiceResponse | None:
        row = await self._get_row(invoice_id, owner_user_id=owner_user_id)
        if not row:
            return None
        row.review_status = "approved"
        row.review_reasons = None
        await self._session.flush()
        return await self.get(invoice_id, owner_user_id=owner_user_id)

    async def find_by_number(
        self,
        normalized: str,
        *,
        owner_user_id: int | None = None,
    ) -> tuple[InvoiceResponse | None, bool]:
        """Look up an invoice by its normalized invoice number.

        Returns a `(invoice, ambiguous)` tuple:
          - `(invoice, False)` — exactly one row matched.
          - `(None, False)`    — no rows matched.
          - `(None, True)`     — 2+ rows share this normalized number; caller
                                  must treat as ambiguous (the matching service
                                  emits a `duplicate_invoice_in_db` review task
                                  in this case).

        We deliberately do NOT pick a winner when ambiguous — silently matching
        a bank payment against an arbitrary one of several invoices with the
        same number could mark the wrong invoice as paid.
        """
        query = (
            select(Invoice)
            .where(Invoice.invoice_number_normalized == normalized)
            .order_by(Invoice.id.asc())
            .limit(2)
        )
        query = _apply_owner_scope(query, owner_user_id)
        result = await self._session.execute(query)
        rows = result.scalars().all()
        if not rows:
            return None, False
        if len(rows) == 1:
            return _to_response(rows[0]), False
        logger.warning(
            "find_by_number ambiguous: normalized=%r matches %d invoices "
            "(ids: %s) — leaving unmatched, review task will be created",
            normalized,
            len(rows),
            [r.id for r in rows],
        )
        return None, True

    async def find_unique_by_numbers(
        self,
        normalized_numbers: list[str],
        *,
        owner_user_id: int | None = None,
    ) -> dict[str, InvoiceResponse]:
        numbers = sorted({n for n in normalized_numbers if n})
        if not numbers:
            return {}
        query = (
            select(Invoice)
            .where(Invoice.invoice_number_normalized.in_(numbers))
            .order_by(Invoice.invoice_number_normalized.asc(), Invoice.id.asc())
            .options(joinedload(Invoice.source_file))
        )
        query = _apply_owner_scope(query, owner_user_id)
        result = await self._session.execute(query)

        grouped: dict[str, list[Invoice]] = {}
        for row in result.scalars().all():
            grouped.setdefault(row.invoice_number_normalized or "", []).append(row)
        return {
            number: _to_response(rows[0])
            for number, rows in grouped.items()
            if number and len(rows) == 1
        }

    async def list_by_number(
        self,
        normalized: str,
        *,
        owner_user_id: int | None = None,
    ) -> list[InvoiceResponse]:
        """Return every invoice row whose normalized number equals `normalized`.

        Used by the matching pipeline to enumerate duplicates when
        `find_by_number` reports an ambiguous match.
        """
        query = (
            select(Invoice)
            .where(Invoice.invoice_number_normalized == normalized)
            .order_by(Invoice.id.asc())
        )
        query = _apply_owner_scope(query, owner_user_id)
        result = await self._session.execute(query)
        return [_to_response(r) for r in result.scalars().all()]

    async def update_paid_at_date(self, invoice_id: int, paid_date: date) -> None:
        row = await self._session.get(Invoice, invoice_id)
        if row:
            row.paid_at_date = paid_date
            await self._session.flush()

    async def clear_paid_at_date(self, invoice_id: int) -> None:
        row = await self._session.get(Invoice, invoice_id)
        if row:
            row.paid_at_date = None
            await self._session.flush()

    async def update_match_status(self, invoice_id: int, match_status: str) -> None:
        row = await self._session.get(Invoice, invoice_id)
        if row:
            row.match_status = match_status
            await self._session.flush()

    async def flag_for_review(
        self,
        invoice_id: int,
        reason: str,
        *,
        match_status: str | None = None,
        force_manual: bool = False,
    ) -> None:
        row = await self._session.get(Invoice, invoice_id)
        if row is None:
            return
        reasons = list(row.review_reasons or [])
        if reason not in reasons:
            reasons.append(reason)
        row.review_reasons = reasons
        if match_status:
            row.match_status = match_status
        if row.review_status == "approved":
            row.review_status = "manual_review" if force_manual else "needs_review"
        elif force_manual:
            row.review_status = "manual_review"
        elif row.review_status == "pending":
            row.review_status = "needs_review"
        await self._session.flush()

    async def list_unpaid_for_amount_matching(
        self,
        *,
        owner_user_id: int | None = None,
        invoice_date_from: date | None = None,
        invoice_date_to: date | None = None,
        limit: int = 200,
    ) -> list[Invoice]:
        q = (
            select(Invoice)
            .where(
                Invoice.paid_at_date.is_(None),
                Invoice.amount.is_not(None),
                Invoice.amount > 0,
            )
            .order_by(Invoice.invoice_date.desc().nullslast(), Invoice.id.desc())
            .limit(limit)
        )
        if invoice_date_from is not None:
            q = q.where(Invoice.invoice_date >= invoice_date_from)
        if invoice_date_to is not None:
            q = q.where(Invoice.invoice_date <= invoice_date_to)
        q = _apply_owner_scope(q, owner_user_id)
        result = await self._session.execute(q)
        return list(result.scalars().all())

    async def count_by_match_status(
        self,
        match_status: str,
        *,
        owner_user_id: int | None = None,
    ) -> int:
        q = select(func.count()).select_from(Invoice).where(
            Invoice.match_status == match_status
        )
        q = _apply_owner_scope(q, owner_user_id)
        return int((await self._session.execute(q)).scalar_one())

    async def get_owned_row(
        self,
        invoice_id: int,
        *,
        owner_user_id: int | None = None,
    ) -> Invoice | None:
        query = (
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(joinedload(Invoice.source_file))
        )
        query = _apply_owner_scope(query, owner_user_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def _get_row(
        self,
        invoice_id: int,
        *,
        owner_user_id: int | None = None,
    ) -> Invoice | None:
        query = select(Invoice).where(Invoice.id == invoice_id)
        query = _apply_owner_scope(query, owner_user_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()
