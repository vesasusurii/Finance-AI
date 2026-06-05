"""Display helpers for authenticated users."""

from schemas.auth import UserContext


def approver_paid_by(user: UserContext) -> str:
    """Value stored in invoices.paid_by when a user approves an invoice or match."""
    return user.email.strip()[:300]
