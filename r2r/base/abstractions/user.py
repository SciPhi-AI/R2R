from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from ..utils import generate_id_from_label


class Group(BaseModel):
    id: UUID = Field(default=None)
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True

    def __init__(self, **data):
        super().__init__(**data)
        if self.id is None:
            self.id = generate_id_from_label(self.name)


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
