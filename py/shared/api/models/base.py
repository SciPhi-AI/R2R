from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class R2RResults(BaseModel, Generic[T]):
    results: T


class PaginatedR2RResult(BaseModel, Generic[T]):
    results: T
    total_entries: int


class GenericBooleanResponse(BaseModel):
    success: bool


class GenericMessageResponse(BaseModel):
    message: str


WrappedBooleanResponse = R2RResults[GenericBooleanResponse]
WrappedGenericMessageResponse = R2RResults[GenericMessageResponse]
