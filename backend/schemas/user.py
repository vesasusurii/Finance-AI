from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from schemas.auth import UserRole


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class ResetUserPasswordRequest(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class UserSummary(BaseModel):
    id: int
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    bank_statement_count: int = 0


class UserListResponse(BaseModel):
    items: list[UserSummary]
    total: int
