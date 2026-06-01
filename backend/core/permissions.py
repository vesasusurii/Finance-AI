"""Static RBAC matrix — source of truth for admin Permissions UI."""

from __future__ import annotations

from dataclasses import dataclass

from core.roles import ROLE_ADMIN, ROLE_FINANCE


@dataclass(frozen=True)
class PermissionRow:
    key: str
    label: str
    description: str
    finance: bool
    admin: bool


PERMISSION_MATRIX: tuple[PermissionRow, ...] = (
    PermissionRow(
        key="upload_invoices",
        label="Upload invoices",
        description="Upload purchase invoice documents for extraction.",
        finance=True,
        admin=True,
    ),
    PermissionRow(
        key="edit_invoices",
        label="Edit and approve invoices",
        description="Review extracted fields and approve documents.",
        finance=True,
        admin=True,
    ),
    PermissionRow(
        key="delete_invoices",
        label="Delete invoices",
        description="Remove invoice records from the database.",
        finance=True,
        admin=True,
    ),
    PermissionRow(
        key="upload_bank_statements",
        label="Upload bank statements",
        description="Import ProCredit-style Excel bank exports.",
        finance=True,
        admin=True,
    ),
    PermissionRow(
        key="run_matching",
        label="Run reconciliation matching",
        description="Match bank transactions to invoices.",
        finance=True,
        admin=True,
    ),
    PermissionRow(
        key="view_reports",
        label="View period reports",
        description="Generate daily, weekly, monthly, and yearly summaries.",
        finance=True,
        admin=True,
    ),
    PermissionRow(
        key="manage_users",
        label="Manage users",
        description="Create and delete platform accounts.",
        finance=False,
        admin=True,
    ),
    PermissionRow(
        key="assign_roles",
        label="Assign roles",
        description="Change finance and admin role assignments.",
        finance=False,
        admin=True,
    ),
    PermissionRow(
        key="view_audit_logs",
        label="View audit logs",
        description="Read the full platform activity trail.",
        finance=False,
        admin=True,
    ),
    PermissionRow(
        key="view_settings",
        label="View system settings",
        description="Inspect non-secret runtime configuration.",
        finance=False,
        admin=True,
    ),
)

ROLE_DESCRIPTIONS: dict[str, str] = {
    ROLE_FINANCE: (
        "Upload and manage invoices and bank data, run matching, "
        "and export period reports for their own uploads."
    ),
    ROLE_ADMIN: (
        "Full finance access plus user management, role assignment, "
        "audit logs, and system settings."
    ),
}
