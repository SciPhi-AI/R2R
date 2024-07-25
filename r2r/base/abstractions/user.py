from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from ..utils import generate_id_from_label


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class User(BaseModel):
    email: EmailStr
    id: UUID = Field(default=None)
    hashed_password: str
    is_superuser: bool = False
    is_active: bool = True
    is_verified: bool = False
    verification_code_expiry: Optional[datetime] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self.id = generate_id_from_label(self.email)


class UserResponse(UserBase):
    id: UUID
    is_superuser: bool
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    token_type: Optional[str] = None
    exp: Optional[datetime] = None


class UserStats(BaseModel):
    user_id: UUID
    num_files: int
    total_size_in_bytes: int
    document_ids: List[UUID]
