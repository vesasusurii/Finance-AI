"""Invoice visibility rules — finance users see own uploads plus shared access."""

from sqlalchemy import exists, or_, select

from core.roles import is_admin
from models.invoice import Invoice
from models.invoice_access import InvoiceAccess
from schemas.auth import UserContext


def invoice_owner_user_id(user: UserContext) -> int | None:
    """Return user id to scope queries, or None when the user may see all invoices."""
    if is_admin(user.role):
        return None
    return user.user_id


# Bank statements and uploads use the same uploaded_by scoping as invoices.
upload_owner_user_id = invoice_owner_user_id


def invoice_visible_to_user_clause(owner_user_id: int):
    """SQLAlchemy filter: invoice owned by user or granted via invoice_access."""
    shared = exists(
        select(1).where(
            InvoiceAccess.invoice_id == Invoice.id,
            InvoiceAccess.user_id == owner_user_id,
        )
    )
    return or_(Invoice.uploaded_by == owner_user_id, shared)


def apply_invoice_visibility(query, owner_user_id: int | None):
    if owner_user_id is not None:
        return query.where(invoice_visible_to_user_clause(owner_user_id))
    return query


def invoice_belongs_to_owner(
    uploaded_by: int | None,
    owner_user_id: int | None,
    *,
    has_shared_access: bool = False,
) -> bool:
    """True when the invoice is visible under owner scope (admin passes None)."""
    if owner_user_id is None:
        return True
    if uploaded_by == owner_user_id:
        return True
    return has_shared_access


def user_may_delete_invoice(uploaded_by: int, owner_user_id: int | None) -> bool:
    """Only the original uploader (or admin) may delete an invoice row."""
    if owner_user_id is None:
        return True
    return uploaded_by == owner_user_id
