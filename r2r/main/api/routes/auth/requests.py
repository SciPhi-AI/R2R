from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    new_password: str


class DeleteUserRequest(BaseModel):
    user_id: UUID
    password: Optional[str] = None
