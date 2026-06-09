from __future__ import annotations

import time
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from core.debug_logger import get_logger
from models.invoice import Invoice
from models.uploaded_file import UploadedFile
from schemas.invoice import ExtractionResult, InvoiceResponse, InvoiceUpdate
from sqlalchemy.orm import joinedload
from core.invoice_access import apply_invoice_visibility, user_may_delete_invoice
from utils.invoice_currency import (
    monetary_fields_changed,
    normalize_from_extraction,
    normalize_invoice_amounts,
)
from utils.normalization import normalize_invoice_number, split_invoice_number
from utils.search_escape import escape_ilike_pattern

logger = get_logger(__name__)


class DuplicateInvoiceNumberError(ValueError):
    """Raised when uploaded_by + invoice_number_normalized already exists."""


def _is_duplicate_invoice_number_error(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    message = str(orig or exc).lower()
    return "uq_invoices_owner_invoice_number_normalized" in message or (
        "invoice_number_normalized" in message and "unique" in message
    )


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
            "upload_source": upload.upload_source,
            "ingest_sender_email": upload.ingest_sender_email,
            "ingest_sender_name": upload.ingest_sender_name,
            "ingest_email_subject": upload.ingest_email_subject,
            "ingest_message_id": upload.ingest_message_id,
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
        display, normalized = split_invoice_number(data.invoice_number)
        ext_amount = Decimal(str(data.amount)) if data.amount is not None else None
        ext_debt = Decimal(str(data.debt)) if data.debt is not None else None
        row = Invoice(
            invoice_date=_parse_date(data.invoice_date),
            name_of_company=data.name_of_company,
            address_of_company=data.address_of_company,
            invoice_number=display,
            invoice_number_normalized=normalized,
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
        await normalize_from_extraction(
            row,
            amount=ext_amount,
            debt=ext_debt,
            currency=data.currency,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if _is_duplicate_invoice_number_error(exc):
                raise DuplicateInvoiceNumberError(normalized or display or "") from exc
            raise
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
            pattern = f"%{escape_ilike_pattern(str(filters['company']))}%"
            query = query.where(Invoice.name_of_company.ilike(pattern, escape="\\"))
            count_query = count_query.where(
                Invoice.name_of_company.ilike(pattern, escape="\\")
            )
        if filters.get("search"):
            term = str(filters["search"]).strip()
            if term:
                pattern = f"%{escape_ilike_pattern(term)}%"
                text_filter = or_(
                    Invoice.name_of_company.ilike(pattern, escape="\\"),
                    Invoice.invoice_number.ilike(pattern, escape="\\"),
                    Invoice.internal_note_description.ilike(pattern, escape="\\"),
                )
                query = query.where(text_filter)
                count_query = count_query.where(text_filter)
        if filters.get("category"):
            pattern = f"%{escape_ilike_pattern(str(filters['category']))}%"
            query = query.where(Invoice.category.ilike(pattern, escape="\\"))
            count_query = count_query.where(
                Invoice.category.ilike(pattern, escape="\\")
            )
        if filters.get("upload_source"):
            source = str(filters["upload_source"])
            query = query.join(
                UploadedFile, Invoice.source_file_id == UploadedFile.id
            ).where(UploadedFile.upload_source == source)
            count_query = count_query.join(
                UploadedFile, Invoice.source_file_id == UploadedFile.id
            ).where(UploadedFile.upload_source == source)

        sort = filters.get("sort") or "invoice_date_desc"
        if sort == "created_at":
            sort = "created_at_desc"
        order_by = {
            "invoice_date_desc": Invoice.invoice_date.desc().nullslast(),
            "invoice_date_asc": Invoice.invoice_date.asc().nullsfirst(),
            "created_at_desc": Invoice.created_at.desc(),
            "created_at_asc": Invoice.created_at.asc(),
            "id_desc": Invoice.id.desc(),
            "id_asc": Invoice.id.asc(),
        }.get(sort, Invoice.invoice_date.desc().nullslast())
        query = query.order_by(order_by)

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
            display, normalized = split_invoice_number(payload["invoice_number"])
            payload["invoice_number"] = display
            row.invoice_number_normalized = normalized

        monetary_payload = monetary_fields_changed(payload)
        original_amount = payload.pop("original_amount", None)
        original_currency = payload.pop("original_currency", None)
        amount_in = payload.pop("amount", None)
        debt_in = payload.pop("debt", None)
        currency_in = payload.pop("currency", None)

        for key, value in payload.items():
            setattr(row, key, value)

        if monetary_payload:
            from services.currency_conversion_service import normalize_currency_code

            src_currency = normalize_currency_code(
                original_currency
                if original_currency is not None
                else currency_in
                if currency_in is not None
                else row.original_currency or row.currency
            )
            currency_changed = (
                original_currency is not None or currency_in is not None
            ) and src_currency != normalize_currency_code(
                row.original_currency or row.currency
            )
            direct_eur_edit = (
                amount_in is not None
                and original_amount is None
                and not currency_changed
                and src_currency != "EUR"
            )

            if direct_eur_edit:
                row.amount = amount_in
                row.currency = "EUR"
                if debt_in is not None:
                    row.debt = debt_in
                if original_currency is not None:
                    row.original_currency = src_currency
            else:
                if currency_changed:
                    src_amount = (
                        original_amount
                        if original_amount is not None
                        else row.original_amount
                    )
                elif src_currency == "EUR":
                    src_amount = (
                        amount_in
                        if amount_in is not None
                        else row.original_amount or row.amount
                    )
                else:
                    src_amount = (
                        original_amount
                        if original_amount is not None
                        else row.original_amount
                    )
                debt_kw: dict = {}
                if debt_in is not None and src_currency == "EUR":
                    debt_kw["original_debt"] = debt_in
                await normalize_invoice_amounts(
                    row,
                    original_amount=src_amount,
                    original_currency=src_currency,
                    **debt_kw,
                )

        if debt_in is not None and Decimal(str(debt_in)) <= 0:
            row.debt = Decimal("0")
            row.match_status = "matched"

        try:
            await self._session.flush()
        except IntegrityError as exc:
            if _is_duplicate_invoice_number_error(exc):
                num = payload.get("invoice_number", row.invoice_number)
                raise DuplicateInvoiceNumberError(str(num or "")) from exc
            raise
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
        paid_by: str | None = None,
    ) -> InvoiceResponse | None:
        row = await self._get_row(invoice_id, owner_user_id=owner_user_id)
        if not row:
            return None
        row.review_status = "approved"
        row.review_reasons = None
        if paid_by:
            row.paid_by = paid_by[:300]
        await self._session.flush()
        return await self.get(invoice_id, owner_user_id=owner_user_id)

    async def update_paid_by(self, invoice_id: int, paid_by: str) -> None:
        row = await self._session.get(Invoice, invoice_id)
        if row:
            row.paid_by = paid_by[:300]
            await self._session.flush()

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

    async def settle_invoice_from_transaction(
        self, invoice_id: int, txn_amount_eur: Decimal
    ) -> None:
        """Set invoice amount to settled bank amount; preserve original currency fields."""
        row = await self._session.get(Invoice, invoice_id)
        if row is None:
            return
        row.amount = txn_amount_eur
        row.debt = Decimal("0")
        row.currency = "EUR"
        row.match_status = "matched"
        await self._session.flush()

    async def update_debt(self, invoice_id: int, remaining: Decimal) -> None:
        row = await self._session.get(Invoice, invoice_id)
        if row:
            row.debt = remaining
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
