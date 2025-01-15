from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class FUSEResults(BaseModel, Generic[T]):
    results: T

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "examples": [{"results": {}}]
        }
    )

    def __hash__(self):
        return hash(("FUSEResults", hash(str(self.results))))


class PaginatedFUSEResult(BaseModel, Generic[T]):
    results: T
    total_entries: int

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "examples": [{
                "results": [],
                "total_entries": 0
            }]
        }
    )

    def __hash__(self):
        return hash(("PaginatedFUSEResult", hash(str(self.results)), self.total_entries))

class GenericBooleanResponse(BaseModel):
    success: bool

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "success": True
            }]
        }
    }


class GenericMessageResponse(BaseModel):
    message: str

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "message": "Operation completed successfully"
            }]
        }
    }


# Type aliases with explicit OpenAPI schemas
WrappedBooleanResponse = FUSEResults[GenericBooleanResponse]
WrappedGenericMessageResponse = FUSEResults[GenericMessageResponse]
