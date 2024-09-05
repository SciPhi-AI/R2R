from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from core.base.abstractions import Token
from core.base.abstractions.base import R2RSerializable
from core.base.api.models.base import ResultsWrapper


def utc_now():
    return datetime.now(timezone.utc)


class TokenResponse(BaseModel):
    access_token: Token
    refresh_token: Token


class UserResponse(R2RSerializable):
    id: UUID
    email: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    is_verified: bool = False
    group_ids: list[UUID] = []

    # Optional fields (to update or set at creation)
    hashed_password: Optional[str] = None
    verification_code_expiry: Optional[datetime] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture: Optional[str] = None


class GenericMessageResponse(BaseModel):
    message: str


# Create wrapped versions of each response
WrappedTokenResponse = ResultsWrapper[TokenResponse]
WrappedUserResponse = ResultsWrapper[UserResponse]
WrappedGenericMessageResponse = ResultsWrapper[GenericMessageResponse]
