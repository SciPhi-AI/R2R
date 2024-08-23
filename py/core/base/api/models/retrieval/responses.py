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
                    {
                        "fragment_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
                        "extraction_id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                        "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
                        "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
                        "group_ids": [],
                        "score": 0.23943702876567796,
                        "text": "Example text from the document",
                        "metadata": {
                            "title": "example_document.pdf",
                            "associatedQuery": "What is the capital of France?",
                        },
                    }
                ],
                "kg_search_results": None,
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
                        {
                            "fragment_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
                            "extraction_id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                            "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
                            "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
                            "group_ids": [],
                            "score": 0.23943702876567796,
                            "text": "Paris is the capital and most populous city of France.",
                            "metadata": {
                                "text": "Paris is the capital and most populous city of France.",
                                "title": "france_info.pdf",
                                "associatedQuery": "What is the capital of France?",
                            },
                        }
                    ],
                    "kg_search_results": None,
                },
            }
        }


RAGAgentResponse = list[Message]
# Create wrapped versions of the responses
WrappedSearchResponse = ResultsWrapper[SearchResponse]
WrappedRAGResponse = ResultsWrapper[RAGResponse]
WrappedRAGAgentResponse = ResultsWrapper[RAGAgentResponse]
