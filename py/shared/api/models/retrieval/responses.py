from typing import Any, Optional

from pydantic import BaseModel, Field

from shared.abstractions import ChunkSearchResult, GraphSearchResult, Message
from shared.abstractions.llm import LLMChatCompletion
from shared.api.models.base import ResultsWrapper


class CombinedSearchResponse(BaseModel):
    chunk_search_results: list[ChunkSearchResult] = Field(
        ...,
        description="List of vector search results",
    )
    graph_search_results: Optional[list[GraphSearchResult]] = Field(
        None,
        description="Knowledge graph search results, if applicable",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "chunk_search_results": [
                    ChunkSearchResult.Config.json_schema_extra,
                ],
                "graph_search_results": [
                    GraphSearchResult.Config.json_schema_extra,
                ],
            }
        }


class RAGResponse(BaseModel):
    completion: Any = Field(
        ...,
        description="The generated completion from the RAG process",
    )
    search_results: CombinedSearchResponse = Field(
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
                    "chunk_search_results": [
                        ChunkSearchResult.Config.json_schema_extra,
                    ],
                    "graph_search_results": [
                        GraphSearchResult.Config.json_schema_extra,
                    ],
                },
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


WrappedCompletionResponse = ResultsWrapper[LLMChatCompletion]
# Create wrapped versions of the responses
WrappedVectorSearchResponse = ResultsWrapper[list[ChunkSearchResult]]
WrappedSearchResponse = ResultsWrapper[CombinedSearchResponse]
WrappedDocumentSearchResponse = ResultsWrapper[list[DocumentSearchResult]]
WrappedRAGResponse = ResultsWrapper[RAGResponse]
WrappedAgentResponse = ResultsWrapper[AgentResponse]
