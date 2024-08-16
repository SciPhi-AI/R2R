from typing import Any, List, Optional

from pydantic import BaseModel, Field

from r2r.base.abstractions.search import KGSearchResult, VectorSearchResult
from r2r.base.api.models.base import ResultsWrapper


class SearchResponse(BaseModel):
    vector_search_results: List[VectorSearchResult] = Field(
        ...,
        description="List of vector search results",
    )
    kg_search_results: Optional[KGSearchResult] = Field(
        None,
        description="Knowledge graph search results, if applicable",
    )

    class Config:
        schema_extra = {
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
        schema_extra = {
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


class RAGAgentResponse(BaseModel):
    completion: Any = Field(
        ...,
        description="The generated completion from the RAG agent process",
    )
    search_results: SearchResponse = Field(
        ...,
        description="The search results used for the RAG agent process",
    )
    thought_process: Optional[str] = Field(
        None,
        description="The agent's thought process or reasoning",
    )

    class Config:
        schema_extra = {
            "example": {
                "completion": {
                    "id": "chatcmpl-example456",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "index": 0,
                            "logprobs": None,
                            "message": {
                                "content": "The capital of France is Paris. Paris is not only the capital but also the largest city in France, known for its iconic landmarks such as the Eiffel Tower, the Louvre Museum, and Notre-Dame Cathedral.",
                                "role": "assistant",
                            },
                        }
                    ],
                },
                "search_results": {
                    "vector_search_results": [
                        {
                            "fragment_id": "d79ef23a-fc23-5452-8f49-d7bd46088a96",
                            "extraction_id": "4f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                            "document_id": "5e157b3a-8469-51db-90d9-52e7d896b49b",
                            "user_id": "3acb499e-8428-543b-bd85-0d9098718220",
                            "group_ids": [],
                            "score": 0.89943702876567796,
                            "text": "Paris is the capital and most populous city of France. It is known for its iconic landmarks such as the Eiffel Tower, the Louvre Museum, and Notre-Dame Cathedral.",
                            "metadata": {
                                "title": "france_geography.pdf",
                                "associatedQuery": "What is the capital of France?",
                            },
                        }
                    ],
                    "kg_search_results": None,
                },
                "thought_process": "To answer this question, I'll need to search for information about France's capital. The search results provide clear information about Paris being the capital of France, along with some additional details about its landmarks.",
            }
        }


# Create wrapped versions of the responses
WrappedSearchResponse = ResultsWrapper[SearchResponse]
WrappedRAGResponse = ResultsWrapper[RAGResponse]
WrappedRAGAgentResponse = ResultsWrapper[RAGAgentResponse]
