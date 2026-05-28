"""Application roles for authorization."""

from typing import Literal

ROLE_FINANCE = "finance"
ROLE_ADMIN = "admin"

Role = Literal["finance", "admin"]

ALL_ROLES: frozenset[str] = frozenset({ROLE_FINANCE, ROLE_ADMIN})


def is_valid_role(role: str) -> bool:
    return role in ALL_ROLES


def is_admin(role: str) -> bool:
    return role == ROLE_ADMIN
