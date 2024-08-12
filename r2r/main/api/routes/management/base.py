# TODO - Cleanup the handling for non-auth configurations
import uuid
from datetime import datetime, timezone

import psutil
from fastapi import Depends, Query
from pydantic import BaseModel

from r2r.base import R2RException
from r2r.main.api.routes.management.requests import (
    R2RAddUserToGroupRequest,
    R2RAnalyticsRequest,
    R2RAssignDocumentToGroupRequest,
    R2RCreateGroupRequest,
    R2RDeleteRequest,
    R2RDocumentChunksRequest,
    R2RDocumentsOverviewRequest,
    R2RGroupsOverviewRequest,
    R2RLogsRequest,
    R2RPrintRelationshipsRequest,
    R2RRemoveDocumentFromGroupRequest,
    R2RRemoveUserFromGroupRequest,
    R2RScoreCompletionRequest,
    R2RUpdateGroupRequest,
    R2RUpdatePromptRequest,
    R2RUsersOverviewRequest,
)

from ....engine import R2REngine
from ..base_router import BaseRouter


class ManagementRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.start_time = datetime.now(timezone.utc)
        self.setup_routes()

    def setup_routes(self):
        @self.router.get("/health")
        async def health_check():
            return {"response": "ok"}

        @self.router.get("/server_stats")
        @self.base_endpoint
        async def server_stats(
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only an authorized user can call the `server_stats` endpoint.",
                    403,
                )
            return {
                "start_time": self.start_time.isoformat(),
                "uptime_seconds": (
                    datetime.now(timezone.utc) - self.start_time
                ).total_seconds(),
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent,
            }

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
            if not auth_user.is_superuser and (
                "user_id" in request.keys
                and request.values[request.keys.index("user_id")]
                != auth_user.id
            ):
                raise R2RException(
                    "Only a superuser can delete arbitrary user data.", 403
                )

            if "user_id" not in request.keys:
                request.keys.append("user_id")
                request.values.append(auth_user.id)

            return await self.engine.adelete(
                keys=request.keys, values=request.values
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
            filters = request.filters or {}

            if not auth_user.is_superuser:
                if "user_id" in filters:
                    user_id_filter = filters["user_id"]
                    if (
                        isinstance(user_id_filter, dict)
                        and "$eq" in user_id_filter
                    ):
                        if user_id_filter["$eq"] != str(auth_user.id):
                            raise R2RException(
                                "Non-superusers can only delete their own data.",
                                403,
                            )
                    else:
                        raise R2RException(
                            "Invalid user_id filter format for non-superusers.",
                            400,
                        )
                else:
                    filters["user_id"] = {"$eq": str(auth_user.id)}

            return await self.engine.adelete(filters=filters)

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

            request_user_ids = (
                [auth_user.id] if not auth_user.is_superuser else None
            )
            return await self.engine.adocuments_overview(
                user_ids=request_user_ids,
                group_ids=auth_user.group_ids,
                document_ids=request.document_ids,
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

        @self.router.post("/create_group")
        @self.base_endpoint
        async def create_group_app(
            request: R2RCreateGroupRequest,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            print(auth_user)
            if not auth_user.is_superuser:
                raise R2RException("Only a superuser can create groups.", 403)
            return await self.engine.acreate_group(
                request.name, request.description
            )

        @self.router.get("/get_group/{group_id}")
        @self.base_endpoint
        async def get_group_app(
            group_id: uuid.UUID,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can get group details.", 403
                )
            return await self.engine.aget_group(group_id)

        @self.router.put("/update_group/{group_id}")
        @self.base_endpoint
        async def update_group_app(
            group_id: uuid.UUID,
            request: R2RUpdateGroupRequest,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only a superuser can update groups.", 403)
            return await self.engine.aupdate_group(
                group_id, request.name, request.description
            )

        @self.router.delete("/delete_group/{group_id}")
        @self.base_endpoint
        async def delete_group_app(
            group_id: uuid.UUID,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only a superuser can delete groups.", 403)
            return await self.engine.adelete_group(group_id)

        @self.router.get("/list_groups/")
        @self.base_endpoint
        async def list_groups_app(
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can list all groups.", 403
                )
            return await self.engine.alist_groups(offset, limit)

        @self.router.post("/add_user_to_group")
        @self.base_endpoint
        async def add_user_to_group_app(
            request: R2RAddUserToGroupRequest,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can add users to groups.", 403
                )
            return await self.engine.aadd_user_to_group(
                request.user_id, request.group_id
            )

        @self.router.post("/remove_user_from_group")
        @self.base_endpoint
        async def remove_user_from_group_app(
            request: R2RRemoveUserFromGroupRequest,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can remove users from groups.", 403
                )
            return await self.engine.aremove_user_from_group(
                request.user_id, request.group_id
            )

        @self.router.get("/get_users_in_group/{group_id}")
        @self.base_endpoint
        async def get_users_in_group_app(
            group_id: uuid.UUID,
            offset: int = 0,
            limit: int = 100,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can get users in a group.", 403
                )
            return await self.engine.aget_users_in_group(
                group_id, offset, limit
            )

        @self.router.get("/get_groups_for_user/{user_id}")
        @self.base_endpoint
        async def get_groups_for_user_app(
            user_id: uuid.UUID,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser and auth_user.id != user_id:
                raise R2RException(
                    "You can only get groups for yourself unless you're a superuser.",
                    403,
                )
            return await self.engine.aget_groups_for_user(user_id)

        @self.router.post("/groups_overview")
        @self.router.get("/groups_overview")
        @self.base_endpoint
        async def groups_overview_app(
            request: R2RGroupsOverviewRequest,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `groups_overview` endpoint.",
                    403,
                )

            return await self.engine.agroups_overview(
                group_ids=request.group_ids
            )

        @self.router.post("/score_completion")
        @self.base_endpoint
        async def score_completion(
            request: R2RScoreCompletionRequest,
        ):
            return await self.engine.ascore_completion(
                message_id=request.message_id, score=request.score
            )

        @self.router.post("/assign_document_to_group")
        @self.base_endpoint
        async def assign_document_to_group_app(
            request: R2RAssignDocumentToGroupRequest,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can assign documents to groups.", 403
                )
            return await self.engine.aassign_document_to_group(
                request.document_id, request.group_id
            )

        @self.router.post("/remove_document_from_group")
        @self.base_endpoint
        async def remove_document_from_group_app(
            request: R2RRemoveDocumentFromGroupRequest,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can remove documents from groups.", 403
                )
            return await self.engine.aremove_document_from_group(
                request.document_id, request.group_id
            )

        @self.router.get("/get_document_groups/{document_id}")
        @self.base_endpoint
        async def get_document_groups_app(
            document_id: str,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            return await self.engine.aget_document_groups(document_id)


class R2RExtractionRequest(BaseModel):
    entity_types: list[str]
    relations: list[str]
