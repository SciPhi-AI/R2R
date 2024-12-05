from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from shared.abstractions import R2RSerializable

from ..utils import generate_default_user_collection_id


class Collection(BaseModel):
    id: UUID = Field(default=None)
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
    )

    class Config:
        populate_by_name = True
        from_attributes = True

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self.id = generate_default_user_collection_id(self.name)


class Token(BaseModel):
    token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    token_type: Optional[str] = None
    exp: Optional[datetime] = None


class User(R2RSerializable):
    id: UUID
    email: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    is_verified: bool = False
    collection_ids: list[UUID] = []
    graph_ids: list[UUID] = []
    document_ids: list[UUID] = []

    # Optional fields (to update or set at creation)
    hashed_password: Optional[str] = None
    verification_code_expiry: Optional[datetime] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture: Optional[str] = None
    total_size_in_bytes: Optional[int] = None
    num_files: Optional[int] = None
