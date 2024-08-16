from typing import Optional

from fastapi import Body, Depends
from fastapi.responses import StreamingResponse

from r2r.base import (
    GenerationConfig,
    KGSearchSettings,
    Message,
    RunType,
    VectorSearchSettings,
)
from r2r.base.api.models import WrappedRAGResponse, WrappedSearchResponse

from ....engine import R2REngine
from ..base_router import BaseRouter


class RetrievalRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.setup_routes()

    def retrieval_endpoint(self, run_type: RunType = RunType.RETRIEVAL):
        return self.base_endpoint(run_type)

    def setup_routes(self):
        @self.router.post(
            "/search",
            responses={
                200: {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "results": {
                                        "type": "object",
                                        "properties": {
                                            "vector_search_results": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "fragment_id": {
                                                            "type": "string"
                                                        },
                                                        "extraction_id": {
                                                            "type": "string"
                                                        },
                                                        "document_id": {
                                                            "type": "string"
                                                        },
                                                        "user_id": {
                                                            "type": "string"
                                                        },
                                                        "group_ids": {
                                                            "type": "array",
                                                            "items": {
                                                                "type": "string"
                                                            },
                                                        },
                                                        "score": {
                                                            "type": "number"
                                                        },
                                                        "text": {
                                                            "type": "string"
                                                        },
                                                        "metadata": {
                                                            "type": "object"
                                                        },
                                                    },
                                                },
                                            },
                                            "kg_search_results": {
                                                "type": "object",
                                                "nullable": True,
                                            },
                                        },
                                    }
                                },
                            },
                            "example": {
                                "results": {
                                    "vector_search_results": [
                                        {
                                            "fragment_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
                                            "extraction_id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                                            "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
                                            "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
                                            "group_ids": [],
                                            "score": 0.93943702876567796,
                                            "text": "The capital of France is Paris.",
                                            "metadata": {
                                                "title": "france_information.pdf",
                                                "associatedQuery": "What is the capital of France?",
                                            },
                                        },
                                        "... Results continued ...",
                                    ],
                                    "kg_search_results": None,
                                }
                            },
                        }
                    },
                }
            },
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """from r2r import R2RClient

client = R2RClient("http://localhost:8000")
# when using auth, do client.login(...)

result = client.search(
    query="What is the capital of France?",
    vector_search_settings={
        "use_vector_search": True,
        "filters": {"document_id": {"eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}},
        "search_limit": 20,
        "do_hybrid_search": True
    }
)
""",
                    },
                    {
                        "lang": "Shell",
                        "source": """curl -X POST "https://api.example.com/search" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "query": "What is the capital of France?",
    "vector_search_settings": {
      "use_vector_search": true,
      "filters": {"document_id": {"eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}},
      "search_limit": 20,
      "do_hybrid_search": true
    }
  }'
""",
                    },
                ]
            },
        )
        @self.retrieval_endpoint
        async def search_app(
            query: str = Body(..., description="Search query"),
            vector_search_settings: VectorSearchSettings = Body(
                default_factory=VectorSearchSettings,
                description="Vector search settings",
                example={
                    "use_vector_search": True,
                    "filters": {"category": "technology"},
                    "search_limit": 20,
                    "do_hybrid_search": True,
                },
            ),
            kg_search_settings: KGSearchSettings = Body(
                default_factory=KGSearchSettings,
                description="Knowledge graph search settings",
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedSearchResponse:
            """
            Perform a search query on the vector database and knowledge graph.

            This endpoint allows for complex filtering of search results using PostgreSQL-based queries.
            Filters can be applied to various fields such as document_id, and internal metadata values.
            Allowed operators include eq, neq, gt, gte, lt, lte, like, ilike, in, and nin.


            """
            results = await self.engine.asearch(
                query=query,
                vector_search_settings=vector_search_settings,
                kg_search_settings=kg_search_settings,
                user=auth_user,
            )
            print("Returning Results:", results)
            return results

        @self.router.post(
            "/rag",
            responses={
                200: {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "results": {
                                        "type": "object",
                                        "properties": {
                                            "completion": {
                                                "type": "object",
                                                "properties": {
                                                    "id": {"type": "string"},
                                                    "choices": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "properties": {
                                                                "finish_reason": {
                                                                    "type": "string"
                                                                },
                                                                "index": {
                                                                    "type": "integer"
                                                                },
                                                                "message": {
                                                                    "type": "object",
                                                                    "properties": {
                                                                        "content": {
                                                                            "type": "string"
                                                                        },
                                                                        "role": {
                                                                            "type": "string"
                                                                        },
                                                                    },
                                                                },
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                            "search_results": {
                                                "$ref": "#/components/schemas/SearchResponse"
                                            },
                                        },
                                    }
                                },
                            },
                            "example": {
                                "results": {
                                    "completion": {
                                        "id": "chatcmpl-123",
                                        "choices": [
                                            {
                                                "finish_reason": "stop",
                                                "index": 0,
                                                "message": {
                                                    "content": "The capital of France is Paris. It is known for its iconic landmarks such as the Eiffel Tower, the Louvre Museum, and Notre-Dame Cathedral.",
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
                                                "score": 0.93943702876567796,
                                                "text": "Paris is the capital of France and is famous for its landmarks.",
                                                "metadata": {
                                                    "title": "france_information.pdf",
                                                    "associatedQuery": "What is the capital of France?",
                                                },
                                            }
                                        ],
                                        "kg_search_results": None,
                                    },
                                }
                            },
                        }
                    },
                }
            },
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """from r2r import R2RClient

client = R2RClient("http://localhost:8000")
# when using auth, do client.login(...)

result = client.rag(
    query="What is the capital of France?",
    vector_search_settings={
        "use_vector_search": True,
        "filters": {"document_id": {"eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}},
        "search_limit": 20,
        "do_hybrid_search": True
    },
    rag_generation_config={
        "stream": False,
        "temperature": 0.7,
        "max_tokens": 150
    }
)
""",
                    },
                    {
                        "lang": "Shell",
                        "source": """curl -X POST "https://api.example.com/rag" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "query": "What is the capital of France?",
    "vector_search_settings": {
      "use_vector_search": true,
      "filters": {"document_id": {"eq": "3e157b3a-8469-51db-90d9-52e7d896b49b"}},
      "search_limit": 20,
      "do_hybrid_search": true
    },
    "rag_generation_config": {
      "stream": false,
      "temperature": 0.7,
      "max_tokens": 150
    }
  }'
""",
                    },
                ]
            },
        )
        @self.retrieval_endpoint
        async def rag_app(
            query: str = Body(..., description="RAG query"),
            vector_search_settings: VectorSearchSettings = Body(
                default_factory=VectorSearchSettings,
                description="Vector search settings",
            ),
            kg_search_settings: KGSearchSettings = Body(
                default_factory=KGSearchSettings,
                description="Knowledge graph search settings",
            ),
            rag_generation_config: GenerationConfig = Body(
                default_factory=GenerationConfig,
                description="RAG generation configuration",
            ),
            task_prompt_override: Optional[str] = Body(
                None, description="Task prompt override"
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedRAGResponse:
            """
            Execute a RAG (Retrieval-Augmented Generation) query.

            This endpoint combines search results with language model generation.
            It supports the same filtering capabilities as the search endpoint,
            allowing for precise control over the retrieved context.

            The generation process can be customized using the rag_generation_config parameter.
            """
            response = await self.engine.arag(
                query=query,
                vector_search_settings=vector_search_settings,
                kg_search_settings=kg_search_settings,
                rag_generation_config=rag_generation_config,
                task_prompt_override=task_prompt_override,
                user=auth_user,
            )

            if rag_generation_config.stream:

                async def stream_generator():
                    async for chunk in response:
                        yield chunk

                return StreamingResponse(
                    stream_generator(), media_type="application/json"
                )
            else:
                return response

        @self.router.post(
            "/agent",
            responses={
                200: {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "results": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "role": {"type": "string"},
                                                "content": {"type": "string"},
                                                "name": {
                                                    "type": "string",
                                                    "nullable": True,
                                                },
                                                "function_call": {
                                                    "type": "object",
                                                    "nullable": True,
                                                },
                                                "tool_calls": {
                                                    "type": "array",
                                                    "nullable": True,
                                                },
                                            },
                                        },
                                    }
                                },
                            },
                            "example": {
                                "results": [
                                    {
                                        "role": "system",
                                        "content": "## You are a helpful assistant that can search for information.\n\nWhen asked a question, perform a search to find relevant information and provide a response.\n\nThe response should contain line-item attributions to relevent search results, and be as informative if possible.\nIf no relevant results are found, then state that no results were found.\nIf no obvious question is present, then do not carry out a search, and instead ask for clarification.",
                                        "name": None,
                                        "function_call": None,
                                        "tool_calls": None,
                                    },
                                    {
                                        "role": "user",
                                        "content": "Who is the greatest philospher of all time?",
                                        "name": None,
                                        "function_call": None,
                                        "tool_calls": None,
                                    },
                                    {
                                        "role": "assistant",
                                        "content": "Aristotle is widely considered the greatest philospher of all time.",
                                        "name": None,
                                        "function_call": None,
                                        "tool_calls": None,
                                    },
                                    {
                                        "role": "user",
                                        "content": "Can you tell me more about him?",
                                        "name": None,
                                        "function_call": None,
                                        "tool_calls": None,
                                    },
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
                                ]
                            },
                        }
                    },
                }
            },
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """from r2r import R2RClient

client = R2RClient("http://localhost:8000")
# when using auth, do client.login(...)

result = client.agent(
    messages=[
        {"role": "user", "content": "Who is the greatest philospher of all time?"},
        {"role": "assistant", "content": "Aristotle is widely considered the greatest philospher of all time."},
        {"role": "user", "content": "Can you tell me more about him?"}
    ],
    vector_search_settings={
        "use_vector_search": True,
        "filters": {"document_id": {"eq": "5e157b3a-8469-51db-90d9-52e7d896b49b"}},
        "search_limit": 20,
        "do_hybrid_search": True
    },
    rag_generation_config={
        "stream": False,
        "temperature": 0.7,
        "max_tokens": 200
    },
    include_title_if_available=True
)
""",
                    },
                    {
                        "lang": "Shell",
                        "source": """curl -X POST "https://api.example.com/agent" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "messages": [
      {"role": "user", "content": "Who is the greatest philospher of all time?"},
      {"role": "assistant", "content": "Aristotle is widely considered the greatest philospher of all time."},
      {"role": "user", "content": "Can you tell me more about him?"}
    ],
    "vector_search_settings": {
      "use_vector_search": true,
      "filters": {"document_id": {"eq": "5e157b3a-8469-51db-90d9-52e7d896b49b"}},
      "search_limit": 20,
      "do_hybrid_search": true
    },
    "rag_generation_config": {
      "stream": false,
      "temperature": 0.7,
      "max_tokens": 200
    },
    "include_title_if_available": true
  }'
""",
                    },
                ]
            },
        )
        @self.retrieval_endpoint
        async def agent_app(
            messages: list[Message] = Body(
                ..., description="List of message objects"
            ),
            vector_search_settings: VectorSearchSettings = Body(
                default_factory=VectorSearchSettings,
                description="Vector search settings",
            ),
            kg_search_settings: KGSearchSettings = Body(
                default_factory=KGSearchSettings,
                description="Knowledge graph search settings",
            ),
            rag_generation_config: GenerationConfig = Body(
                default_factory=GenerationConfig,
                description="RAG generation configuration",
            ),
            task_prompt_override: Optional[str] = Body(
                None, description="Task prompt override"
            ),
            include_title_if_available: bool = Body(
                True, description="Include title if available"
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            """
            Implement an agent-based interaction for complex query processing.

            This endpoint supports multi-turn conversations and can handle complex queries
            by breaking them down into sub-tasks. It uses the same filtering capabilities
            as the search and RAG endpoints for retrieving relevant information.

            The agent's behavior can be customized using the rag_generation_config and
            task_prompt_override parameters.
            """

            response = await self.engine.arag_agent(
                messages=messages,
                vector_search_settings=vector_search_settings,
                kg_search_settings=kg_search_settings,
                rag_generation_config=rag_generation_config,
                task_prompt_override=task_prompt_override,
                include_title_if_available=include_title_if_available,
                user=auth_user,
            )

            if rag_generation_config.stream:

                async def stream_generator():
                    async for chunk in response:
                        yield chunk

                return StreamingResponse(
                    stream_generator(), media_type="application/json"
                )
            else:
                return response
