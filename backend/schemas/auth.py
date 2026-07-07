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
    must_change_password: bool = False


class UserContext(BaseModel):
    user_id: int
    email: str
    role: UserRole
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    message: str
