from __future__ import annotations

import bcrypt
from fastapi import HTTPException, status

from core.roles import ROLE_FINANCE, is_valid_role
from repositories.user_repository import UserRepository
from schemas.auth import UserContext
from schemas.user import CreateUserRequest, UserListResponse, UserSummary
from schemas.admin import UpdateUserRoleRequest


class UserController:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def list_users(self) -> UserListResponse:
        users = await self._user_repo.list_all()
        items = [
            UserSummary(
                id=user.id,
                email=user.email,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at,
            )
            for user in users
        ]
        return UserListResponse(items=items, total=len(items))

    async def create_user(self, body: CreateUserRequest) -> UserSummary:
        existing = await self._user_repo.find_by_email(body.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "email_taken",
                    "message": "A user with this email already exists.",
                },
            )

        password_hash = bcrypt.hashpw(
            body.password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        user = await self._user_repo.create(
            email=body.email,
            password_hash=password_hash,
            role=ROLE_FINANCE,
            must_change_password=True,
        )

        return UserSummary(
            id=user.id,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    async def delete_user(self, user_id: int, admin: UserContext) -> dict:
        user = await self._user_repo.get(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "user_not_found",
                    "message": "User not found.",
                },
            )

        await self._user_repo.delete_user_and_related_data(user_id)
        return {"message": "User deleted."}

    async def update_user_role(
        self,
        user_id: int,
        body: UpdateUserRoleRequest,
        admin: UserContext,
    ) -> UserSummary:
        if admin.user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "cannot_change_own_role",
                    "message": "You cannot change your own role.",
                },
            )

        if not is_valid_role(body.role):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_role",
                    "message": "Role must be finance or admin.",
                },
            )

        user = await self._user_repo.get(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "user_not_found",
                    "message": "User not found.",
                },
            )

        if user.role == "admin" and body.role != "admin":
            remaining_admins = await self._user_repo.count_admins(
                exclude_user_id=user_id
            )
            if remaining_admins == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "last_admin",
                        "message": "At least one admin account must remain.",
                    },
                )

        updated = await self._user_repo.update_role(user, body.role)
        return UserSummary(
            id=updated.id,
            email=updated.email,
            role=updated.role,
            is_active=updated.is_active,
            created_at=updated.created_at,
        )
