from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.invoice import Invoice
from schemas.invoice import ExtractionResult, InvoiceResponse, InvoiceUpdate
from sqlalchemy.orm import joinedload
from utils.normalization import normalize_invoice_number


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


class InvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        data: ExtractionResult,
        source_file_id: int,
        review_status: str,
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
            review_status=review_status,
            match_status="unmatched",
            source_file_id=source_file_id,
        )
        self._session.add(row)
        await self._session.flush()
        return await self.get(row.id)  # type: ignore[return-value]

    async def get(self, invoice_id: int) -> InvoiceResponse | None:
        result = await self._session.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(joinedload(Invoice.source_file))
        )
        row = result.scalar_one_or_none()
        return _to_response(row) if row else None

    async def list_invoices(
        self,
        filters: dict,
        page: int,
        limit: int,
    ) -> tuple[list[InvoiceResponse], int]:
        query = select(Invoice).options(joinedload(Invoice.source_file))
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
            formatted = normalize_invoice_number(payload["invoice_number"])
            payload["invoice_number"] = formatted
            row.invoice_number_normalized = formatted
        for key, value in payload.items():
            setattr(row, key, value)
        await self._session.flush()
        return await self.get(invoice_id)

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
        return await self.get(invoice_id)

    async def find_by_number(self, normalized: str) -> InvoiceResponse | None:
        result = await self._session.execute(
            select(Invoice).where(Invoice.invoice_number_normalized == normalized)
        )
        row = result.scalar_one_or_none()
        return _to_response(row) if row else None

    async def update_paid_at_date(self, invoice_id: int, paid_date: date) -> None:
        row = await self._session.get(Invoice, invoice_id)
        if row:
            row.paid_at_date = paid_date
            await self._session.flush()
