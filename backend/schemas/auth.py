from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    user_id: int
    email: str
    role: str


class UserContext(BaseModel):
    user_id: int
    email: str
    role: str
