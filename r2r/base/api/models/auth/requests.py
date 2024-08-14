from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    verification_code: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserPutRequest(BaseModel):
    email: EmailStr | None = None
    name: str | None = None
    bio: str | None = None
    profile_picture: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    new_password: str


class LogoutRequest(BaseModel):
    token: str


class DeleteUserRequest(BaseModel):
    user_id: UUID
    password: Optional[str] = None
