from typing import Any, Optional

from pydantic import BaseModel, Field

from core.base.abstractions import KGSearchResult, Message, VectorSearchResult
from core.base.api.models.base import ResultsWrapper


class SearchResponse(BaseModel):
    vector_search_results: list[VectorSearchResult] = Field(
        ...,
        description="List of vector search results",
    )
    kg_search_results: Optional[list[KGSearchResult]] = Field(
        None,
        description="Knowledge graph search results, if applicable",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "vector_search_results": [
                    VectorSearchResult.Config.json_schema_extra,
                ],
                "kg_search_results": [
                    KGSearchResult.Config.json_schema_extra,
                ],
            }
        }


class RAGResponse(BaseModel):
    completion: Any = Field(
        ...,
        description="The generated completion from the RAG process",
    )
    search_results: SearchResponse = Field(
        ...,
        description="The search results used for the RAG process",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "completion": {
                    "id": "chatcmpl-example123",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "index": 0,
                            "logprobs": None,
                            "message": {
                                "content": "Paris is the capital of France.",
                                "role": "assistant",
                            },
                        }
                    ],
                },
                "search_results": {
                    "vector_search_results": [
                        VectorSearchResult.Config.json_schema_extra,
                    ],
                    "kg_search_results": [
                        KGSearchResult.Config.json_schema_extra,
                    ],
                },
            }
        }


RAGAgentResponse = list[Message]
# Create wrapped versions of the responses
WrappedSearchResponse = ResultsWrapper[SearchResponse]
WrappedRAGResponse = ResultsWrapper[RAGResponse]
WrappedRAGAgentResponse = ResultsWrapper[RAGAgentResponse]
