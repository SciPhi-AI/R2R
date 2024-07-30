# TODO - Cleanup the handling for non-auth configurations
from fastapi import Depends
from pydantic import BaseModel

from r2r.base import R2RException
from r2r.main.api.routes.management.requests import (
    R2RAnalyticsRequest,
    R2RDeleteRequest,
    R2RDocumentChunksRequest,
    R2RDocumentsOverviewRequest,
    R2RLogsRequest,
    R2RPrintRelationshipsRequest,
    R2RUpdatePromptRequest,
    R2RUsersOverviewRequest,
)

from ....engine import R2REngine
from ..base_router import BaseRouter


class ManagementRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.setup_routes()

    def setup_routes(self):
        @self.router.get("/health")
        async def health_check():
            return {"response": "ok"}

        @self.router.post("/update_prompt")
        @self.base_endpoint
        async def update_prompt_app(
            request: R2RUpdatePromptRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `update_prompt` endpoint.",
                    403,
                )

            return await self.engine.aupdate_prompt(
                request.name, request.template, request.input_types
            )

        @self.router.post("/logs")
        @self.router.get("/logs")
        @self.base_endpoint
        async def logs_app(
            request: R2RLogsRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `logs` endpoint.", 403
                )

            return await self.engine.alogs(
                log_type_filter=request.log_type_filter,
                max_runs_requested=request.max_runs_requested,
            )

        @self.router.post("/analytics")
        @self.router.get("/analytics")
        @self.base_endpoint
        async def get_analytics_app(
            request: R2RAnalyticsRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `analytics` endpoint.", 403
                )

            return await self.engine.aanalytics(
                filter_criteria=request.filter_criteria,
                analysis_types=request.analysis_types,
            )

        @self.router.delete("/delete")
        @self.base_endpoint
        async def delete_app(
            request: R2RDeleteRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            if not auth_user.is_superuser:
                if (
                    "user_id" in request.keys
                    and request.values[request.keys.index("user_id")]
                    != auth_user.id
                ):
                    raise R2RException(
                        "Only a superuser can delete arbitrary user data.", 403
                    )
                else:
                    request.keys.append("user_id")
                    request.values.append(auth_user.id)

            return await self.engine.adelete(
                keys=request.keys, values=request.values
            )

        @self.router.post("/document_chunks")
        @self.router.get("/document_chunks")
        @self.base_endpoint
        async def document_chunks_app(
            request: R2RDocumentChunksRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            chunks = await self.engine.adocument_chunks(request.document_id)

            if not chunks:
                raise R2RException(
                    "No chunks found for the given document ID.",
                    404,
                )

            is_owner = str(chunks[0].get("user_id")) == str(auth_user.id)

            if not is_owner and not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can arbitrarily call document_chunks.",
                    403,
                )

            return chunks

        @self.router.post("/users_overview")
        @self.router.get("/users_overview")
        @self.base_endpoint
        async def users_overview_app(
            request: R2RUsersOverviewRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `users_overview` endpoint.",
                    403,
                )

            return await self.engine.ausers_overview(user_ids=request.user_ids)

        @self.router.post("/documents_overview")
        @self.router.get("/documents_overview")
        @self.base_endpoint
        async def documents_overview_app(
            request: R2RDocumentsOverviewRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            request_user_ids = request.user_ids

            if request_user_ids and not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `documents_overview` endpoint for arbitrary users.",
                    403,
                )
            request_user_ids = request_user_ids or [str(auth_user.id)]
            return await self.engine.adocuments_overview(
                document_ids=request.document_ids, user_ids=request_user_ids
            )

        @self.router.post("/inspect_knowledge_graph")
        @self.router.get("/inspect_knowledge_graph")
        @self.base_endpoint
        async def inspect_knowledge_graph(
            request: R2RPrintRelationshipsRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `inspect_knowledge_graph` endpoint.",
                    403,
                )
            return await self.engine.ainspect_knowledge_graph(
                limit=request.limit
            )

        @self.router.get("/app_settings")
        @self.base_endpoint
        async def app_settings(
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `app_settings` endpoint.",
                    403,
                )
            return await self.engine.aapp_settings()


class R2RExtractionRequest(BaseModel):
    entity_types: list[str]
    relations: list[str]
