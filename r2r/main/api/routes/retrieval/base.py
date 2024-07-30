from fastapi import Depends
from fastapi.responses import StreamingResponse

from r2r.base import GenerationConfig, KGSearchSettings, VectorSearchSettings
from r2r.main.api.routes.retrieval.requests import (
    R2REvalRequest,
    R2RRAGAgentRequest,
    R2RRAGRequest,
    R2RSearchRequest,
)

from ....engine import R2REngine
from ..base_router import BaseRouter


class RetrievalRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.setup_routes()

    def setup_routes(self):
        @self.router.post("/search")
        @self.base_endpoint
        async def search_app(
            request: R2RSearchRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            kg_search_settings = request.kg_search_settings or {}

            if "entity_types" not in kg_search_settings:
                kg_search_settings["entity_types"] = []
            elif not isinstance(kg_search_settings["entity_types"], list):
                kg_search_settings["entity_types"] = [
                    kg_search_settings["entity_types"]
                ]

            if "kg_search_generation_config" in kg_search_settings:
                kg_search_settings["kg_search_generation_config"] = (
                    GenerationConfig(
                        **kg_search_settings["kg_search_generation_config"]
                        or {}
                    )
                )

            results = await self.engine.asearch(
                query=request.query,
                vector_search_settings=VectorSearchSettings(
                    **(request.vector_search_settings or {})
                ),
                kg_search_settings=KGSearchSettings(**kg_search_settings),
                user=auth_user,
            )
            return results

        @self.router.post("/rag")
        @self.base_endpoint
        async def rag_app(
            request: R2RRAGRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            if "kg_search_generation_config" in request.kg_search_settings:
                request.kg_search_settings["kg_search_generation_config"] = (
                    GenerationConfig(
                        **(
                            request.kg_search_settings[
                                "kg_search_generation_config"
                            ]
                            or {}
                        )
                    )
                )
            response = await self.engine.arag(
                query=request.query,
                vector_search_settings=VectorSearchSettings(
                    **(request.vector_search_settings or {})
                ),
                kg_search_settings=KGSearchSettings(
                    **(request.kg_search_settings or {})
                ),
                rag_generation_config=GenerationConfig(
                    **(request.rag_generation_config or {})
                ),
                task_prompt_override=request.task_prompt_override,
                user=auth_user,
            )
            if (
                request.rag_generation_config
                and request.rag_generation_config.get("stream", False)
            ):

                async def stream_generator():
                    async for chunk in response:
                        yield chunk

                return StreamingResponse(
                    stream_generator(), media_type="application/json"
                )
            else:
                return response

        @self.router.post("/rag_agent")
        @self.base_endpoint
        async def rag_agent_app(
            request: R2RRAGAgentRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            if "kg_search_generation_config" in request.kg_search_settings:
                request.kg_search_settings["kg_search_generation_config"] = (
                    GenerationConfig(
                        **(
                            request.kg_search_settings[
                                "kg_search_generation_config"
                            ]
                            or {}
                        )
                    )
                )

            response = await self.engine.arag_agent(
                messages=request.messages,
                vector_search_settings=VectorSearchSettings(
                    **(request.vector_search_settings or {})
                ),
                kg_search_settings=KGSearchSettings(
                    **(request.kg_search_settings or {})
                ),
                rag_generation_config=GenerationConfig(
                    **(request.rag_generation_config or {})
                ),
                task_prompt_override=request.task_prompt_override,
                include_title_if_available=request.include_title_if_available,
                user=auth_user,
            )

            if (
                request.rag_generation_config
                and request.rag_generation_config.get("stream", False)
            ):

                async def stream_generator():
                    async for chunk in response:
                        yield chunk

                return StreamingResponse(
                    stream_generator(), media_type="application/json"
                )
            else:
                return response

        @self.router.post("/evaluate")
        @self.base_endpoint
        async def evaluate_app(
            request: R2REvalRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            results = await self.engine.aevaluate(
                query=request.query,
                context=request.context,
                completion=request.completion,
                user=auth_user,
            )
            return results
