"""Invoice visibility rules — finance users see only their own uploads."""

from core.roles import is_admin
from schemas.auth import UserContext


def invoice_owner_user_id(user: UserContext) -> int | None:
    """Return user id to scope queries, or None when the user may see all invoices."""
    if is_admin(user.role):
        return None
    return user.user_id
