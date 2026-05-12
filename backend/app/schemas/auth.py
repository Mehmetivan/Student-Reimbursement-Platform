# app/schemas/auth.py
from pydantic import BaseModel, EmailStr
from typing import Optional


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    account_id: int
    student_id: int
    email: str
    role: str
    account_status: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    role: str


class MeResponse(BaseModel):
    account_id: int
    email: str
    role: str
    student_id: Optional[int] = None
    account_status: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
