"""Invoice visibility rules — finance users see only their own uploads."""

from core.roles import is_admin
from schemas.auth import UserContext


def invoice_owner_user_id(user: UserContext) -> int | None:
    """Return user id to scope queries, or None when the user may see all invoices."""
    if is_admin(user.role):
        return None
    return user.user_id


# Bank statements and uploads use the same uploaded_by scoping as invoices.
upload_owner_user_id = invoice_owner_user_id


def invoice_belongs_to_owner(
    uploaded_by: int | None,
    owner_user_id: int | None,
) -> bool:
    """True when the invoice is visible under owner scope (admin passes None)."""
    if owner_user_id is None:
        return True
    return uploaded_by == owner_user_id
