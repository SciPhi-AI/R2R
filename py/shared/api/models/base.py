from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResultsWrapper(BaseModel, Generic[T]):
    results: T


class PaginatedResultsWrapper(BaseModel, Generic[T]):
    results: T
    total_entries: int


class GenericBooleanResponse(BaseModel):
    success: bool


class GenericMessageResponse(BaseModel):
    message: str


WrappedBooleanResponse = ResultsWrapper[GenericBooleanResponse]
WrappedGenericMessageResponse = ResultsWrapper[GenericMessageResponse]
