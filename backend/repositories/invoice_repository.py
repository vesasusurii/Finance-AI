from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.debug_logger import get_logger
from models.invoice import Invoice
from schemas.invoice import ExtractionResult, InvoiceResponse, InvoiceUpdate
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
    return InvoiceResponse.model_validate(row)


class InvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        data: ExtractionResult,
        source_file_id: int,
        review_status: str,
    ) -> InvoiceResponse:
        normalized = normalize_invoice_number(data.invoice_number)
        row = Invoice(
            invoice_date=_parse_date(data.invoice_date),
            name_of_company=data.name_of_company,
            address_of_company=data.address_of_company,
            invoice_number=data.invoice_number,
            invoice_number_normalized=normalized,
            amount=Decimal(str(data.amount)) if data.amount is not None else None,
            currency=data.currency,
            account_details=data.account_details,
            internal_note_description=data.internal_note_description,
            client_employee_related=data.client_employee_related,
            category=data.category,
            extraction_confidence=Decimal(str(round(data.confidence_score, 4))),
            review_status=review_status,
            match_status="unmatched",
            source_file_id=source_file_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_response(row)

    async def get(self, invoice_id: int) -> InvoiceResponse | None:
        row = await self._session.get(Invoice, invoice_id)
        return _to_response(row) if row else None

    async def list_invoices(
        self,
        filters: dict,
        page: int,
        limit: int,
    ) -> tuple[list[InvoiceResponse], int]:
        query = select(Invoice)
        count_query = select(func.count()).select_from(Invoice)

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

        total = (await self._session.execute(count_query)).scalar_one()
        rows = (await self._session.execute(query)).scalars().all()
        return [_to_response(r) for r in rows], int(total)

    async def list_for_export(self, filters: dict) -> list[InvoiceResponse]:
        items, _ = await self.list_invoices(filters, page=1, limit=10_000)
        return items

    async def update(self, invoice_id: int, data: InvoiceUpdate) -> InvoiceResponse | None:
        row = await self._session.get(Invoice, invoice_id)
        if not row:
            return None
        payload = data.model_dump(exclude_unset=True)
        if "invoice_number" in payload:
            row.invoice_number_normalized = normalize_invoice_number(
                payload["invoice_number"]
            )
        for key, value in payload.items():
            setattr(row, key, value)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_response(row)

    async def delete(self, invoice_id: int) -> bool:
        row = await self._session.get(Invoice, invoice_id)
        if not row:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def approve(self, invoice_id: int) -> InvoiceResponse | None:
        row = await self._session.get(Invoice, invoice_id)
        if not row:
            return None
        row.review_status = "approved"
        await self._session.flush()
        await self._session.refresh(row)
        return _to_response(row)

    async def find_by_number(
        self, normalized: str
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
        result = await self._session.execute(
            select(Invoice)
            .where(Invoice.invoice_number_normalized == normalized)
            .order_by(Invoice.id.asc())
            .limit(2)
        )
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

    async def list_by_number(self, normalized: str) -> list[InvoiceResponse]:
        """Return every invoice row whose normalized number equals `normalized`.

        Used by the matching pipeline to enumerate duplicates when
        `find_by_number` reports an ambiguous match.
        """
        result = await self._session.execute(
            select(Invoice)
            .where(Invoice.invoice_number_normalized == normalized)
            .order_by(Invoice.id.asc())
        )
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

    async def count_by_match_status(self, match_status: str) -> int:
        q = select(func.count()).select_from(Invoice).where(
            Invoice.match_status == match_status
        )
        return int((await self._session.execute(q)).scalar_one())
