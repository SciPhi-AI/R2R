from pathlib import Path
from typing import Optional

import yaml
from fastapi import Body, Depends
from fastapi.responses import StreamingResponse

from core.base import (
    GenerationConfig,
    KGSearchSettings,
    Message,
    R2RException,
    RunType,
    VectorSearchSettings,
)
from core.base.api.models import (
    WrappedRAGAgentResponse,
    WrappedRAGResponse,
    WrappedSearchResponse,
)

from ....engine import R2REngine
from ..base_router import BaseRouter


class RetrievalRouter(BaseRouter):
    def __init__(
        self, engine: R2REngine, run_type: RunType = RunType.RETRIEVAL
    ):
        super().__init__(engine, run_type)
        self.openapi_extras = self.load_openapi_extras()
        self.setup_routes()

    def load_openapi_extras(self):
        yaml_path = Path(__file__).parent / "retrieval_router_openapi.yml"
        with open(yaml_path, "r") as yaml_file:
            yaml_content = yaml.safe_load(yaml_file)
        return yaml_content

    def retrieval_endpoint(self, run_type: RunType = RunType.RETRIEVAL):
        return self.base_endpoint(run_type)

    def setup_routes(self):
        search_extras = self.openapi_extras.get("search", {})
        search_descriptions = search_extras.get("input_descriptions", {})

        @self.router.post(
            "/search",
            openapi_extra=search_extras.get("openapi_extra"),
        )
        @self.retrieval_endpoint
        async def search_app(
            query: str = Body(
                ..., description=search_descriptions.get("query")
            ),
            vector_search_settings: VectorSearchSettings = Body(
                default_factory=VectorSearchSettings,
                description=search_descriptions.get("vector_search_settings"),
            ),
            kg_search_settings: KGSearchSettings = Body(
                default_factory=KGSearchSettings,
                description=search_descriptions.get("kg_search_settings"),
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedSearchResponse:
            """
            Perform a search query on the vector database and knowledge graph.

            This endpoint allows for complex filtering of search results using PostgreSQL-based queries.
            Filters can be applied to various fields such as document_id, and internal metadata values.


            Allowed operators include `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, and `nin`.

            """
            user_groups = set(auth_user.group_ids)
            selected_groups = set(vector_search_settings.selected_group_ids)
            allowed_groups = user_groups.intersection(selected_groups)
            if selected_groups - allowed_groups != set():
                raise ValueError(
                    "User does not have access to the specified group(s): "
                    f"{selected_groups - allowed_groups}"
                )

            filters = {
                "$or": [
                    {"user_id": {"$eq": str(auth_user.id)}},
                    # {"group_ids": {"$any": list([str(ele) for ele in allowed_groups])}},
                    {"group_ids": {"$overlap": list(allowed_groups)}},
                ]
            }
            if vector_search_settings.filters != {}:
                filters = {"$and": [filters, vector_search_settings.filters]}

            vector_search_settings.filters = filters
            results = await self.engine.asearch(
                query=query,
                vector_search_settings=vector_search_settings,
                kg_search_settings=kg_search_settings,
            )
            return results

        rag_extras = self.openapi_extras.get("rag", {})
        rag_descriptions = rag_extras.get("input_descriptions", {})

        @self.router.post(
            "/rag",
            openapi_extra=rag_extras.get("openapi_extra"),
        )
        @self.retrieval_endpoint
        async def rag_app(
            query: str = Body(..., description=rag_descriptions.get("query")),
            vector_search_settings: VectorSearchSettings = Body(
                default_factory=VectorSearchSettings,
                description=rag_descriptions.get("vector_search_settings"),
            ),
            kg_search_settings: KGSearchSettings = Body(
                default_factory=KGSearchSettings,
                description=rag_descriptions.get("kg_search_settings"),
            ),
            rag_generation_config: GenerationConfig = Body(
                default_factory=GenerationConfig,
                description=rag_descriptions.get("rag_generation_config"),
            ),
            task_prompt_override: Optional[str] = Body(
                None, description=rag_descriptions.get("task_prompt_override")
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
            allowed_groups = set(auth_user.group_ids)
            filters = {
                "$or": [
                    {"user_id": str(auth_user.id)},
                    {"group_ids": {"$overlap": list(allowed_groups)}},
                ]
            }
            if vector_search_settings.filters != {}:
                filters = {"$and": [filters, vector_search_settings.filters]}

            vector_search_settings.filters = filters

            response = await self.engine.arag(
                query=query,
                vector_search_settings=vector_search_settings,
                kg_search_settings=kg_search_settings,
                rag_generation_config=rag_generation_config,
                task_prompt_override=task_prompt_override,
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

        agent_extras = self.openapi_extras.get("agent", {})
        agent_descriptions = agent_extras.get("input_descriptions", {})

        @self.router.post(
            "/agent",
            openapi_extra=agent_extras.get("openapi_extra"),
        )
        @self.retrieval_endpoint
        async def agent_app(
            messages: list[Message] = Body(
                ..., description=agent_descriptions.get("messages")
            ),
            vector_search_settings: VectorSearchSettings = Body(
                default_factory=VectorSearchSettings,
                description=agent_descriptions.get("vector_search_settings"),
            ),
            kg_search_settings: KGSearchSettings = Body(
                default_factory=KGSearchSettings,
                description=agent_descriptions.get("kg_search_settings"),
            ),
            rag_generation_config: GenerationConfig = Body(
                default_factory=GenerationConfig,
                description=agent_descriptions.get("rag_generation_config"),
            ),
            task_prompt_override: Optional[str] = Body(
                None,
                description=agent_descriptions.get("task_prompt_override"),
            ),
            include_title_if_available: bool = Body(
                True,
                description=agent_descriptions.get(
                    "include_title_if_available"
                ),
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedRAGAgentResponse:
            """
            Implement an agent-based interaction for complex query processing.

            This endpoint supports multi-turn conversations and can handle complex queries
            by breaking them down into sub-tasks. It uses the same filtering capabilities
            as the search and RAG endpoints for retrieving relevant information.

            The agent's behavior can be customized using the rag_generation_config and
            task_prompt_override parameters.
            """
            # TODO - Don't just copy paste the same code, refactor this
            allowed_groups = set(auth_user.group_ids)
            filters = {
                "$or": [
                    {"user_id": str(auth_user.id)},
                    {"group_ids": {"$overlap": list(allowed_groups)}},
                ]
            }
            if vector_search_settings.filters != {}:
                filters = {"$and": [filters, vector_search_settings.filters]}

            vector_search_settings.filters = filters

            try:
                response = await self.engine.arag_agent(
                    messages=messages,
                    vector_search_settings=vector_search_settings,
                    kg_search_settings=kg_search_settings,
                    rag_generation_config=rag_generation_config,
                    task_prompt_override=task_prompt_override,
                    include_title_if_available=include_title_if_available,
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
            except Exception as e:
                raise R2RException(str(e), 500)
