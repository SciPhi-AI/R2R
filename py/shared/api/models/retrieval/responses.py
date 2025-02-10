from typing import Any, Optional

from pydantic import BaseModel, Field

from shared.abstractions import (
    AggregateSearchResult,
    ChunkSearchResult,
    Message,
)
from shared.abstractions.llm import LLMChatCompletion
from shared.api.models.base import R2RResults
from shared.api.models.management.responses import DocumentResponse


class Citation(BaseModel):
    """
    Represents a single citation reference in the RAG response.
    Combines both bracket metadata (start/end offsets, snippet range)
    and the mapped source fields (id, doc ID, chunk text, etc.).
    """

    # Bracket references
    index: int = Field(
        ..., description="Citation bracket index after re-labeling"
    )
    oldIndex: Optional[int] = Field(
        None, description="Original citation bracket index before re-labeling"
    )
    startIndex: Optional[int] = Field(
        None,
        description="Character offset (start) for the bracket [n] in the final text",
    )
    endIndex: Optional[int] = Field(
        None,
        description="Character offset (end) for the bracket [n] in the final text",
    )

    # Expanded snippet offsets around the bracket
    snippetStartIndex: Optional[int] = Field(
        None,
        description="Start offset for the snippet region around the bracket",
    )
    snippetEndIndex: Optional[int] = Field(
        None,
        description="End offset for the snippet region around the bracket",
    )
    snippet: Optional[str] = Field(
        None,
        description="Sentence-based snippet or text chunk containing this bracket reference",
    )

    # Mapped source fields
    sourceType: Optional[str] = Field(
        None,
        description="Type of the cited source (chunk, graph, web, contextDoc)",
    )
    id: Optional[str] = Field(
        None, description="Search result ID (if chunk, e.g. chunk.id)"
    )
    document_id: Optional[str] = Field(
        None, description="Document ID if chunk references a particular doc"
    )
    owner_id: Optional[str] = Field(
        None,
        description="Owner ID if chunk or doc references a particular user",
    )
    collection_ids: Optional[list[str]] = Field(
        None, description="Collections this chunk or doc belongs to"
    )
    score: Optional[float] = Field(
        None, description="Search score or similarity value"
    )
    text: Optional[str] = Field(
        None, description="Full chunk text or short snippet from the source"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional key-value fields from the source (title, license, etc.)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "index": 1,
                "oldIndex": 9,
                "startIndex": 393,
                "endIndex": 396,
                "snippetStartIndex": 320,
                "snippetEndIndex": 418,
                "snippet": "some line referencing the bracket [1]",
                "sourceType": "chunk",
                "id": "e760bb76-1c6e-52eb-910d-0ce5b567011b",
                "document_id": "e43864f5-a36f-548e-aacd-6f8d48b30c7f",
                "owner_id": "2acb499e-8428-543b-bd85-0d9098718220",
                "collection_ids": ["122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"],
                "score": 0.64,
                "text": "Document Title: DeepSeek_R1.pdf\n\nText: could achieve an accuracy of ...",
                "metadata": {
                    "title": "DeepSeek_R1.pdf",
                    "license": "CC-BY-4.0",
                    "chunk_order": 68,
                    "document_type": "pdf",
                },
            }
        }


class RAGResponse(BaseModel):
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

    class Config:
        json_schema_extra = {
            "example": {
                "completion": {
                    "id": "chatcmpl-example123",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "index": 0,
                            "message": {
                                "content": "Paris is the capital of France.",
                                "role": "assistant",
                            },
                        }
                    ],
                },
                "search_results": {
                    "chunk_search_results": [],
                    "graph_search_results": [],
                    "web_search_results": [],
                },
                "citations": {
                    "citations": [
                        {
                            "index": 1,
                            "startIndex": 25,
                            "endIndex": 28,
                            "uri": "https://example.com/doc1",
                            "title": "example_document_1.pdf",
                            "license": "CC-BY-4.0",
                        }
                    ]
                },
                "metadata": {},
            }
        }


class AgentResponse(BaseModel):
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
                        "content": None,
                        "name": None,
                        "function_call": {
                            "name": "search",
                            "arguments": '{"query":"Aristotle biography"}',
                        },
                        "tool_calls": None,
                    },
                    {
                        "role": "function",
                        "content": "1. Aristotle[A] (Greek: Ἀριστοτέλης Aristotélēs, pronounced [aristotélɛːs]; 384–322 BC) was an Ancient Greek philosopher and polymath. His writings cover a broad range of subjects spanning the natural sciences, philosophy, linguistics, economics, politics, psychology, and the arts. As the founder of the Peripatetic school of philosophy in the Lyceum in Athens, he began the wider Aristotelian tradition that followed, which set the groundwork for the development of modern science.\n2. Aristotle[A] (Greek: Ἀριστοτέλης Aristotélēs, pronounced [aristotélɛːs]; 384–322 BC) was an Ancient Greek philosopher and polymath. His writings cover a broad range of subjects spanning the natural sciences, philosophy, linguistics, economics, politics, psychology, and the arts. As the founder of the Peripatetic school of philosophy in the Lyceum in Athens, he began the wider Aristotelian tradition that followed, which set the groundwork for the development of modern science.\n3. Aristotle was born in 384 BC[C] in Stagira, Chalcidice,[2] about 55 km (34 miles) east of modern-day Thessaloniki.[3][4] His father, Nicomachus, was the personal physician to King Amyntas of Macedon. While he was young, Aristotle learned about biology and medical information, which was taught by his father.[5] Both of Aristotle's parents died when he was about thirteen, and Proxenus of Atarneus became his guardian.[6] Although little information about Aristotle's childhood has survived, he probably spent\n4. Aristotle was born in 384 BC[C] in Stagira, Chalcidice,[2] about 55 km (34 miles) east of modern-day Thessaloniki.[3][4] His father, Nicomachus, was the personal physician to King Amyntas of Macedon. While he was young, Aristotle learned about biology and medical information, which was taught by his father.[5] Both of Aristotle's parents died when he was about thirteen, and Proxenus of Atarneus became his guardian.[6] Although little information about Aristotle's childhood has survived, he probably spent\n5. Life\nIn general, the details of Aristotle's life are not well-established. The biographies written in ancient times are often speculative and historians only agree on a few salient points.[B]\n",
                        "name": "search",
                        "function_call": None,
                        "tool_calls": None,
                    },
                    {
                        "role": "assistant",
                        "content": "Aristotle (384–322 BC) was an Ancient Greek philosopher and polymath whose contributions have had a profound impact on various fields of knowledge. Here are some key points about his life and work:\n\n1. **Early Life**: Aristotle was born in 384 BC in Stagira, Chalcidice, which is near modern-day Thessaloniki, Greece. His father, Nicomachus, was the personal physician to King Amyntas of Macedon, which exposed Aristotle to medical and biological knowledge from a young age [C].\n\n2. **Education and Career**: After the death of his parents, Aristotle was sent to Athens to study at Plato's Academy, where he remained for about 20 years. After Plato's death, Aristotle left Athens and eventually became the tutor of Alexander the Great [C].\n\n3. **Philosophical Contributions**: Aristotle founded the Lyceum in Athens, where he established the Peripatetic school of philosophy. His works cover a wide range of subjects, including metaphysics, ethics, politics, logic, biology, and aesthetics. His writings laid the groundwork for many modern scientific and philosophical inquiries [A].\n\n4. **Legacy**: Aristotle's influence extends beyond philosophy to the natural sciences, linguistics, economics, and psychology. His method of systematic observation and analysis has been foundational to the development of modern science [A].\n\nAristotle's comprehensive approach to knowledge and his systematic methodology have earned him a lasting legacy as one of the greatest philosophers of all time.\n\nSources:\n- [A] Aristotle's broad range of writings and influence on modern science.\n- [C] Details about Aristotle's early life and education.",
                        "name": None,
                        "function_call": None,
                        "tool_calls": None,
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


WrappedCompletionResponse = R2RResults[LLMChatCompletion]
# Create wrapped versions of the responses
WrappedVectorSearchResponse = R2RResults[list[ChunkSearchResult]]
WrappedSearchResponse = R2RResults[AggregateSearchResult]
# FIXME: This is returning DocumentResponse, but should be DocumentSearchResult
WrappedDocumentSearchResponse = R2RResults[list[DocumentResponse]]
WrappedRAGResponse = R2RResults[RAGResponse]
WrappedAgentResponse = R2RResults[AgentResponse]
