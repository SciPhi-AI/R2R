from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class User(BaseModel):
    email: EmailStr
    id: UUID = Field(default_factory=uuid4)
    hashed_password: str
    is_active: bool = True
    is_verified: bool = False
    verification_code: Optional[str] = None
    verification_code_expiry: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class Token(BaseModel):
    token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    token_type: Optional[str] = None
