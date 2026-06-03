from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from core.roles import ROLE_FINANCE

UserRole = Literal["finance", "admin"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user_id: int
    email: str
    role: UserRole = Field(default=ROLE_FINANCE)
    email_verified: bool = True
    must_change_password: bool = False
    verification_resend_in_seconds: int = 0


class UserContext(BaseModel):
    user_id: int
    email: str
    role: UserRole
    email_verified: bool = True
    must_change_password: bool = False


class VerifyEmailRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)
