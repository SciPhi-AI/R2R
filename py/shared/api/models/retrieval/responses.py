from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from shared.abstractions import (
    AggregateSearchResult,
    ChunkSearchResult,
    GraphSearchResult,
    LLMChatCompletion,
    Message,
    WebPageSearchResult,
)
from shared.api.models.base import R2RResults
from shared.api.models.management.responses import DocumentResponse

from ....abstractions import R2RSerializable


class CitationSpan(R2RSerializable):
    """Represents a single occurrence of a citation in text."""

    start_index: int = Field(
        ..., description="Starting character index of the citation"
    )
    end_index: int = Field(
        ..., description="Ending character index of the citation"
    )
    context_start: int = Field(
        ..., description="Starting index of the surrounding context"
    )
    context_end: int = Field(
        ..., description="Ending index of the surrounding context"
    )


class Citation(R2RSerializable):
    """
    Represents a citation reference in the RAG response.

    The first time a citation appears, it includes the full payload.
    Subsequent appearances only include the citation ID and span information.
    """

    # Basic identification
    id: str = Field(
        ..., description="The short ID of the citation (e.g., 'e41ac2d')"
    )
    object: str = Field(
        "citation", description="The type of object, always 'citation'"
    )

    # Optimize payload delivery
    is_new: bool = Field(
        True,
        description="Whether this is the first occurrence of this citation",
    )

    # Position information
    span: Optional[CitationSpan] = Field(
        None, description="Position of this citation occurrence in the text"
    )

    # Source information - only included for first occurrence
    source_type: Optional[str] = Field(
        None, description="Type of source: 'chunk', 'graph', 'web', or 'doc'"
    )

    # Full payload - only included for first occurrence
    payload: (
        ChunkSearchResult
        | GraphSearchResult
        | WebPageSearchResult
        | DocumentResponse
        | dict[str, Any]
        | None
    ) = Field(
        None,
        description="The complete source object (only included for new citations)",
    )

    class Config:
        extra = "ignore"
        json_schema_extra = {
            "example": {
                "id": "e41ac2d",
                "object": "citation",
                "is_new": True,
                "span": {
                    "start_index": 120,
                    "end_index": 129,
                    "context_start": 80,
                    "context_end": 180,
                },
                "source_type": "chunk",
                "payload": {
                    "id": "e41ac2d1-full-id",
                    "text": "The study found significant improvements...",
                    "metadata": {"title": "Research Paper"},
                },
            }
        }


# class Citation(R2RSerializable):
#     """Represents a single citation reference in the RAG response.

#     Combines both bracket metadata (start/end offsets, snippet range) and the
#     mapped source fields (id, doc ID, chunk text, etc.).
#     """

#     # Bracket references
#     id: str = Field(..., description="The ID of the citation object")
#     object: str = Field(
#         ...,
#         description="The type of object, e.g. `citation`",
#     )
#     payload: (
#         ChunkSearchResult
#         | GraphSearchResult
#         | WebPageSearchResult
#         | DocumentResponse
#         | None
#     ) = Field(
#         ..., description="The object payload and it's corresponding type"
#     )

#     class Config:
#         extra = "ignore"  # This tells Pydantic to ignore extra fields
#         json_schema_extra = {
#             "example": {
#                 "id": "cit.abcd123",
#                 "object": "citation",
#                 "payload": "ChunkSearchResult(...)",
#             }
#         }


class RAGResponse(R2RSerializable):
    generated_answer: str = Field(
        ..., description="The generated completion from the RAG process"
    )
    search_results: AggregateSearchResult = Field(
        ..., description="The search results used for the RAG process"
    )
    citations: Optional[list[Citation]] = Field(
        None,
        description="Structured citation metadata, if you do citation extraction.",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional data returned by the LLM provider",
    )
    completion: str = Field(
        ...,
        description="The generated completion from the RAG process",
        # deprecated=True,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "generated_answer": "The capital of France is Paris.",
                "search_results": {
                    "chunk_search_results": [
                        {
                            "index": 1,
                            "start_index": 25,
                            "end_index": 28,
                            "uri": "https://example.com/doc1",
                            "title": "example_document_1.pdf",
                            "license": "CC-BY-4.0",
                        }
                    ],
                    "graph_search_results": [
                        {
                            "content": {
                                "id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                                "name": "Entity Name",
                                "description": "Entity Description",
                                "metadata": {},
                            },
                            "result_type": "entity",
                            "chunk_ids": [
                                "c68dc72e-fc23-5452-8f49-d7bd46088a96"
                            ],
                            "metadata": {
                                "associated_query": "What is the capital of France?"
                            },
                        }
                    ],
                    "web_search_results": [
                        {
                            "title": "Page Title",
                            "link": "https://example.com/page",
                            "snippet": "Page snippet",
                            "position": 1,
                            "date": "2021-01-01",
                            "sitelinks": [
                                {
                                    "title": "Sitelink Title",
                                    "link": "https://example.com/sitelink",
                                }
                            ],
                        }
                    ],
                    "document_search_results": [
                        {
                            "document": {
                                "id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                                "title": "Document Title",
                                "chunks": ["Chunk 1", "Chunk 2"],
                                "metadata": {},
                            },
                        }
                    ],
                },
                "citations": [
                    {
                        "index": 1,
                        "rawIndex": 9,
                        "startIndex": 393,
                        "endIndex": 396,
                        "snippetStartIndex": 320,
                        "snippetEndIndex": 418,
                        "sourceType": "chunk",
                        "id": "e760bb76-1c6e-52eb-910d-0ce5b567011b",
                        "document_id": "e43864f5-a36f-548e-aacd-6f8d48b30c7f",
                        "owner_id": "2acb499e-8428-543b-bd85-0d9098718220",
                        "collection_ids": [
                            "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
                        ],
                        "score": 0.64,
                        "text": "Document Title: DeepSeek_R1.pdf\n\nText: could achieve an accuracy of ...",
                        "metadata": {
                            "title": "DeepSeek_R1.pdf",
                            "license": "CC-BY-4.0",
                            "chunk_order": 68,
                            "document_type": "pdf",
                        },
                    }
                ],
                "metadata": {
                    "id": "chatcmpl-example123",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "index": 0,
                            "message": {"role": "assistant"},
                        }
                    ],
                },
                "completion": "TO BE DEPRECATED",
            }
        }


class AgentResponse(R2RSerializable):
    messages: list[Message] = Field(..., description="Agent response messages")
    conversation_id: str = Field(
        ..., description="The conversation ID for the RAG agent response"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {
                        "role": "assistant",
                        "content": """Aristotle (384–322 BC) was an Ancient
                        Greek philosopher and polymath whose contributions
                        have had a profound impact on various fields of
                        knowledge.
                        Here are some key points about his life and work:
                        \n\n1. **Early Life**: Aristotle was born in 384 BC in
                        Stagira, Chalcidice, which is near modern-day
                        Thessaloniki, Greece. His father, Nicomachus, was the
                        personal physician to King Amyntas of Macedon, which
                        exposed Aristotle to medical and biological knowledge
                        from a young age [C].\n\n2. **Education and Career**:
                        After the death of his parents, Aristotle was sent to
                        Athens to study at Plato's Academy, where he remained
                        for about 20 years. After Plato's death, Aristotle
                        left Athens and eventually became the tutor of
                        Alexander the Great [C].
                        \n\n3. **Philosophical Contributions**: Aristotle
                        founded the Lyceum in Athens, where he established the
                        Peripatetic school of philosophy. His works cover a
                        wide range of subjects, including metaphysics, ethics,
                        politics, logic, biology, and aesthetics. His writings
                        laid the groundwork for many modern scientific and
                        philosophical inquiries [A].\n\n4. **Legacy**:
                        Aristotle's influence extends beyond philosophy to the
                          natural sciences, linguistics, economics, and
                          psychology. His method of systematic observation and
                          analysis has been foundational to the development of
                          modern science [A].\n\nAristotle's comprehensive
                          approach to knowledge and his systematic methodology
                          have earned him a lasting legacy as one of the
                          greatest philosophers of all time.\n\nSources:
                          \n- [A] Aristotle's broad range of writings and
                          influence on modern science.\n- [C] Details about
                          Aristotle's early life and education.""",
                        "name": None,
                        "function_call": None,
                        "tool_calls": None,
                        "metadata": {
                            "citations": [
                                {
                                    "index": 1,
                                    "rawIndex": 9,
                                    "startIndex": 393,
                                    "endIndex": 396,
                                    "snippetStartIndex": 320,
                                    "snippetEndIndex": 418,
                                    "sourceType": "chunk",
                                    "id": "e760bb76-1c6e-52eb-910d-0ce5b567011b",
                                    "document_id": """
                                    e43864f5-a36f-548e-aacd-6f8d48b30c7f
                                    """,
                                    "owner_id": """
                                    2acb499e-8428-543b-bd85-0d9098718220
                                    """,
                                    "collection_ids": [
                                        "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"
                                    ],
                                    "score": 0.64,
                                    "text": """
                                    Document Title: DeepSeek_R1.pdf
                                    \n\nText: could achieve an accuracy of ...
                                    """,
                                    "metadata": {
                                        "title": "DeepSeek_R1.pdf",
                                        "license": "CC-BY-4.0",
                                        "chunk_order": 68,
                                        "document_type": "pdf",
                                    },
                                }
                            ],
                            "aggregated_search_results": {
                                "chunk_search_results": [
                                    {
                                        "id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                                        "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
                                        "owner_id": "2acb499e-8428-543b-bd85-0d9098718220",
                                        "collection_ids": [],
                                        "score": 0.23943702876567796,
                                        "text": "Example text from the document",
                                        "metadata": {
                                            "title": "example_document.pdf",
                                            "associated_query": "What is the capital of France?",
                                        },
                                    }
                                ],
                                "graph_search_results": [
                                    {
                                        "content": {
                                            "id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                                            "name": "Entity Name",
                                            "description": "Entity Description",
                                            "metadata": {},
                                        },
                                        "result_type": "entity",
                                        "chunk_ids": [
                                            "c68dc72e-fc23-5452-8f49-d7bd46088a96"
                                        ],
                                        "metadata": {
                                            "associated_query": "What is the capital of France?"
                                        },
                                    }
                                ],
                                "web_search_results": [
                                    {
                                        "title": "Page Title",
                                        "link": "https://example.com/page",
                                        "snippet": "Page snippet",
                                        "position": 1,
                                        "date": "2021-01-01",
                                        "sitelinks": [
                                            {
                                                "title": "Sitelink Title",
                                                "link": "https://example.com/sitelink",
                                            }
                                        ],
                                    }
                                ],
                                "document_search_results": [
                                    {
                                        "document": {
                                            "id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                                            "title": "Document Title",
                                            "chunks": ["Chunk 1", "Chunk 2"],
                                            "metadata": {},
                                        },
                                    }
                                ],
                            },
                        },
                    },
                ],
                "conversation_id": "a32b4c5d-6e7f-8a9b-0c1d-2e3f4a5b6c7d",
            }
        }


class DocumentSearchResult(BaseModel):
    document_id: str = Field(
        ...,
        description="The document ID",
    )
    metadata: Optional[dict] = Field(
        None,
        description="The metadata of the document",
    )
    score: float = Field(
        ...,
        description="The score of the document",
    )


# A generic base model for SSE events
class SSEEventBase(BaseModel):
    event: str
    data: Any


# Model for the search results event
class SearchResultsData(BaseModel):
    id: str
    object: str
    data: AggregateSearchResult


class SearchResultsEvent(SSEEventBase):
    event: Literal["search_results"]
    data: SearchResultsData


class DeltaPayload(BaseModel):
    value: str
    annotations: list[Any]


# Model for message events (partial tokens)
class MessageDelta(BaseModel):
    type: str
    payload: DeltaPayload


class Delta(BaseModel):
    content: list[MessageDelta]


class MessageData(BaseModel):
    id: str
    object: str
    delta: Delta


class MessageEvent(SSEEventBase):
    event: Literal["message"]
    data: MessageData


# Update CitationSpan model for SSE events
class CitationSpanData(BaseModel):
    start: int = Field(
        ..., description="Starting character index of the citation"
    )
    end: int = Field(..., description="Ending character index of the citation")
    context_start: Optional[int] = Field(
        None, description="Starting index of surrounding context"
    )
    context_end: Optional[int] = Field(
        None, description="Ending index of surrounding context"
    )


# Update CitationData model
class CitationData(BaseModel):
    id: str = Field(
        ..., description="The short ID of the citation (e.g., 'e41ac2d')"
    )
    object: str = Field(
        "citation", description="The type of object, always 'citation'"
    )

    # New fields from the enhanced Citation model
    is_new: Optional[bool] = Field(
        None,
        description="Whether this is the first occurrence of this citation",
    )

    span: Optional[CitationSpanData] = Field(
        None, description="Position of this citation occurrence in the text"
    )

    source_type: Optional[str] = Field(
        None, description="Type of source: 'chunk', 'graph', 'web', or 'doc'"
    )

    # Optional payload field, only for first occurrence
    payload: Optional[Any] = Field(
        None,
        description="The complete source object (only included for new citations)",
    )

    # For backward compatibility, maintain the existing fields
    class Config:
        populate_by_name = True
        extra = "ignore"


# CitationEvent remains the same, but now using the updated CitationData
class CitationEvent(SSEEventBase):
    event: Literal["citation"]
    data: CitationData


# Model for the final answer event
class FinalAnswerData(BaseModel):
    generated_answer: str
    citations: list[Citation]  # refine if you have a citation model


class FinalAnswerEvent(SSEEventBase):
    event: Literal["final_answer"]
    data: FinalAnswerData


# "tool_call" event
class ToolCallData(BaseModel):
    tool_call_id: str
    name: str
    arguments: Any  # If JSON arguments, use dict[str, Any], or str if needed


class ToolCallEvent(SSEEventBase):
    event: Literal["tool_call"]
    data: ToolCallData


# "tool_result" event
class ToolResultData(BaseModel):
    tool_call_id: str
    role: Literal["tool", "function"]
    content: str


class ToolResultEvent(SSEEventBase):
    event: Literal["tool_result"]
    data: ToolResultData


# Optionally, define a fallback model for unrecognized events
class UnknownEvent(SSEEventBase):
    pass


# 1) Define a new ThinkingEvent type
class ThinkingData(BaseModel):
    id: str
    object: str
    delta: Delta


class ThinkingEvent(SSEEventBase):
    event: str = "thinking"
    data: ThinkingData


# Create a union type for all RAG events
RAGEvent = (
    SearchResultsEvent
    | MessageEvent
    | CitationEvent
    | FinalAnswerEvent
    | UnknownEvent
    | ToolCallEvent
    | ToolResultEvent
    | ToolResultData
    | ToolResultEvent
)

AgentEvent = (
    ThinkingEvent
    | SearchResultsEvent
    | MessageEvent
    | CitationEvent
    | FinalAnswerEvent
    | ToolCallEvent
    | ToolResultEvent
    | UnknownEvent
)

WrappedCompletionResponse = R2RResults[LLMChatCompletion]
# Create wrapped versions of the responses
WrappedVectorSearchResponse = R2RResults[list[ChunkSearchResult]]
WrappedSearchResponse = R2RResults[AggregateSearchResult]
# FIXME: This is returning DocumentResponse, but should be DocumentSearchResult
WrappedDocumentSearchResponse = R2RResults[list[DocumentResponse]]
WrappedRAGResponse = R2RResults[RAGResponse]
WrappedAgentResponse = R2RResults[AgentResponse]
WrappedLLMChatCompletion = R2RResults[LLMChatCompletion]
WrappedEmbeddingResponse = R2RResults[list[float]]
