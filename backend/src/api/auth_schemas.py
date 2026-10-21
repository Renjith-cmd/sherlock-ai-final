"""Authentication API schemas and models."""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from src.core.auth_security import User


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = ""


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=3, max_length=100)  # username or email
    password: str = Field(..., min_length=1, max_length=128)


class AuthResponse(BaseModel):
    user: User
    token: str
