from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class FUSEResults(BaseModel, Generic[T]):
    results: T


class PaginatedFUSEResult(BaseModel, Generic[T]):
    results: T
    total_entries: int


class GenericBooleanResponse(BaseModel):
    success: bool


class GenericMessageResponse(BaseModel):
    message: str


WrappedBooleanResponse = FUSEResults[GenericBooleanResponse]
WrappedGenericMessageResponse = FUSEResults[GenericMessageResponse]
