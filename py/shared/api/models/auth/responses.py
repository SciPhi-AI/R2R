from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from shared.abstractions import R2RSerializable, Token
from shared.api.models.base import ResultsWrapper


class TokenResponse(BaseModel):
    access_token: Token
    refresh_token: Token


class UserResponse(R2RSerializable):
    id: UUID
    email: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    is_verified: bool = False
    collection_ids: list[UUID] = []

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
