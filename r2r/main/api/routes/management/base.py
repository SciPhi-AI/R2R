# TODO - Cleanup the handling for non-auth configurations
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import psutil
from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel

from r2r.base import R2RException
from r2r.base.api.models.management.responses import (
    WrappedAnalyticsResponse,
    WrappedAppSettingsResponse,
    WrappedDeleteResponse,
    WrappedDocumentChunkResponse,
    WrappedDocumentOverviewResponse,
    WrappedGroupListResponse,
    WrappedGroupOverviewResponse,
    WrappedGroupResponse,
    WrappedKnowledgeGraphResponse,
    WrappedLogResponse,
    WrappedPromptResponse,
    WrappedScoreCompletionResponse,
    WrappedServerStatsResponse,
    WrappedUserOverviewResponse,
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
        @self.base_endpoint
        async def health_check():
            return {"response": "ok"}

        @self.router.get("/server_stats")
        @self.base_endpoint
        async def server_stats(
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedServerStatsResponse:
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
            name: str = Body(..., description="Prompt name"),
            template: Optional[str] = Body(
                None, description="Prompt template"
            ),
            input_types: Optional[dict[str, str]] = Body(
                {}, description="Input types"
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedPromptResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `update_prompt` endpoint.",
                    403,
                )

            result = await self.engine.aupdate_prompt(
                name, template, input_types
            )
            return result

        @self.router.get("/logs")
        @self.base_endpoint
        async def logs_app(
            run_type_filter: Optional[str] = Query(""),
            max_runs: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedLogResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `logs` endpoint.", 403
                )

            return await self.engine.alogs(
                run_type_filter=run_type_filter,
                max_runs=max_runs,
            )

        @self.router.get("/analytics")
        @self.base_endpoint
        async def get_analytics_app(
            filter_criteria: Optional[str] = Query("{}"),
            analysis_types: Optional[str] = Query("{}"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedAnalyticsResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `analytics` endpoint.", 403
                )

            try:
                # Parse the query parameters
                filter_criteria_dict = (
                    json.loads(filter_criteria) if filter_criteria else {}
                )
                analysis_types_dict = (
                    json.loads(analysis_types) if analysis_types else {}
                )

                return await self.engine.aanalytics(
                    filter_criteria=filter_criteria_dict,
                    analysis_types=analysis_types_dict,
                )
            except json.JSONDecodeError as e:
                raise R2RException(
                    f"Invalid JSON in query parameters: {str(e)}", 400
                )
            except ValueError as e:
                raise R2RException(
                    f"Invalid data in query parameters: {str(e)}", 400
                )

        @self.router.delete("/delete")
        @self.base_endpoint
        async def delete_app(
            filters: Optional[str] = Query("{}"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedDeleteResponse:
            filters_dict = json.loads(filters) if filters else None
            return await self.engine.adelete(filters=filters_dict)

        @self.router.get("/document_chunks")
        @self.base_endpoint
        async def document_chunks_app(
            document_id: uuid.UUID = Query(...),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedDocumentChunkResponse:
            chunks = await self.engine.adocument_chunks(document_id)

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

        @self.router.get("/users_overview")
        @self.base_endpoint
        async def users_overview_app(
            user_ids: list[uuid.UUID] = Query([]),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedUserOverviewResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `users_overview` endpoint.",
                    403,
                )

            return await self.engine.ausers_overview(user_ids=user_ids)

        @self.router.get("/documents_overview")
        @self.base_endpoint
        async def documents_overview_app(
            document_id: list[uuid.UUID] = Query([]),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedDocumentOverviewResponse:
            request_user_ids = (
                [auth_user.id] if not auth_user.is_superuser else None
            )
            return await self.engine.adocuments_overview(
                user_ids=request_user_ids,
                group_ids=auth_user.group_ids,
                document_ids=document_id,
            )

        @self.router.get("/inspect_knowledge_graph")
        @self.base_endpoint
        async def inspect_knowledge_graph(
            limit: int = 100,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedKnowledgeGraphResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `inspect_knowledge_graph` endpoint.",
                    403,
                )
            return await self.engine.ainspect_knowledge_graph(limit=limit)

        @self.router.get("/app_settings")
        @self.base_endpoint
        async def app_settings(
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedAppSettingsResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `app_settings` endpoint.",
                    403,
                )
            return await self.engine.aapp_settings()

        @self.router.post("/create_group")
        @self.base_endpoint
        async def create_group_app(
            name: str = Body(..., description="Group name"),
            description: Optional[str] = Body(
                "", description="Group description"
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupResponse:
            if not auth_user.is_superuser:
                raise R2RException("Only a superuser can create groups.", 403)
            return await self.engine.acreate_group(name, description)

        @self.router.get("/get_group/{group_id}")
        @self.base_endpoint
        async def get_group_app(
            group_id: uuid.UUID = Path(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can get group details.", 403
                )
            result = await self.engine.aget_group(group_id)
            print(result)
            return result

        @self.router.put("/update_group")
        @self.base_endpoint
        async def update_group_app(
            group_id: uuid.UUID = Body(..., description="Group ID"),
            name: Optional[str] = Body(None, description="Updated group name"),
            description: Optional[str] = Body(
                None, description="Updated group description"
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupResponse:
            if not auth_user.is_superuser:
                raise R2RException("Only a superuser can update groups.", 403)
            return await self.engine.aupdate_group(group_id, name, description)

        @self.router.delete("/delete_group/{group_id}")
        @self.base_endpoint
        async def delete_group_app(
            group_id: uuid.UUID = Path(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupResponse:
            if not auth_user.is_superuser:
                raise R2RException("Only a superuser can delete groups.", 403)
            return await self.engine.adelete_group(group_id)

        @self.router.get("/list_groups")
        @self.base_endpoint
        async def list_groups_app(
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupListResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can list all groups.", 403
                )
            return await self.engine.alist_groups(offset, limit)

        @self.router.post("/add_user_to_group")
        @self.base_endpoint
        async def add_user_to_group_app(
            user_id: uuid.UUID = Body(..., description="User ID"),
            group_id: uuid.UUID = Body(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can add users to groups.", 403
                )
            return await self.engine.aadd_user_to_group(user_id, group_id)

        @self.router.post("/remove_user_from_group")
        @self.base_endpoint
        async def remove_user_from_group_app(
            user_id: uuid.UUID = Body(..., description="User ID"),
            group_id: uuid.UUID = Body(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can remove users from groups.", 403
                )
            return await self.engine.aremove_user_from_group(user_id, group_id)

        # TODO - Proivde response model
        @self.router.get("/get_users_in_group/{group_id}/{offset}/{limit}")
        @self.base_endpoint
        async def get_users_in_group_app(
            group_id: uuid.UUID = Path(..., description="Group ID"),
            offset: int = Path(..., description="Offset"),
            limit: int = Path(..., description="limit"),
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
            user_id: uuid.UUID = Path(..., description="User ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupListResponse:
            if not auth_user.is_superuser and auth_user.id != user_id:
                raise R2RException(
                    "You can only get groups for yourself unless you're a superuser.",
                    403,
                )
            return await self.engine.aget_groups_for_user(user_id)

        @self.router.get("/groups_overview")
        @self.base_endpoint
        async def groups_overview_app(
            group_ids: Optional[list[uuid.UUID]] = Query(None),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupOverviewResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `groups_overview` endpoint.",
                    403,
                )

            return await self.engine.agroups_overview(group_ids=group_ids)

        @self.router.post("/score_completion")
        @self.base_endpoint
        async def score_completion(
            message_id: uuid.UUID = Body(..., description="Message ID"),
            score: float = Body(..., description="Completion score"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedScoreCompletionResponse:
            return await self.engine.ascore_completion(
                message_id=message_id, score=score
            )

        @self.router.post("/assign_document_to_group")
        @self.base_endpoint
        async def assign_document_to_group_app(
            document_id: str = Body(..., description="Document ID"),
            group_id: uuid.UUID = Body(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can assign documents to groups.", 403
                )
            return await self.engine.aassign_document_to_group(
                document_id, group_id
            )

        @self.router.post("/remove_document_from_group")
        @self.base_endpoint
        async def remove_document_from_group_app(
            document_id: str = Body(..., description="Document ID"),
            group_id: uuid.UUID = Body(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can remove documents from groups.", 403
                )
            return await self.engine.aremove_document_from_group(
                document_id, group_id
            )

        @self.router.get("/get_document_groups/{document_id}")
        @self.base_endpoint
        async def get_document_groups_app(
            document_id: str = Path(..., description="Document ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupListResponse:
            return await self.engine.aget_document_groups(document_id)


class R2RExtractionRequest(BaseModel):
    entity_types: list[str]
    relations: list[str]
