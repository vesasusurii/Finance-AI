from core.invoice_access import invoice_owner_user_id
from core.roles import ROLE_ADMIN, ROLE_FINANCE
from schemas.auth import UserContext


def _ctx(user_id: int, role: str) -> UserContext:
    return UserContext(user_id=user_id, email="u@borek.com", role=role)


def test_finance_user_scoped_to_self():
    assert invoice_owner_user_id(_ctx(5, ROLE_FINANCE)) == 5


def test_admin_user_sees_all():
    assert invoice_owner_user_id(_ctx(1, ROLE_ADMIN)) is None
