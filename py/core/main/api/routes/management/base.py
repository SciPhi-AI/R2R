# TODO - Cleanup the handling for non-auth configurations
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import psutil
from fastapi import Body, Depends, Path, Query
from pydantic import Json

from core.base import R2RException
from core.base.api.models.management.responses import (
    WrappedAddUserResponse,
    WrappedAnalyticsResponse,
    WrappedAppSettingsResponse,
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
from core.base.logging import AnalysisTypes, LogFilterCriteria

from ....engine import R2REngine
from ..base_router import BaseRouter, RunType


class ManagementRouter(BaseRouter):
    def __init__(
        self, engine: R2REngine, run_type: RunType = RunType.MANAGEMENT
    ):
        super().__init__(engine, run_type)
        self.start_time = datetime.now(timezone.utc)
        self.setup_routes()

    # TODO: remove this from the management route, it should be at the base of the server
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

        @self.router.get("/analytics")
        @self.base_endpoint
        async def get_analytics_app(
            filter_criteria: Optional[Json[dict]] = Query({}),
            analysis_types: Optional[Json[dict]] = Query({}),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedAnalyticsResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `analytics` endpoint.", 403
                )

            try:
                result = await self.engine.aanalytics(
                    filter_criteria=LogFilterCriteria(filters=filter_criteria),
                    analysis_types=AnalysisTypes(
                        analysis_types=analysis_types
                    ),
                )
                return result
            except json.JSONDecodeError as e:
                raise R2RException(
                    f"Invalid JSON in query parameters: {str(e)}", 400
                )
            except ValueError as e:
                raise R2RException(
                    f"Invalid data in query parameters: {str(e)}", 400
                )

        # TODO: should we add a message to the response model with warnings i.e. if the max_runs passed in violates the max_runs limit?
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
                max_runs=min(max(max_runs, 1), 1000),
            )

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

        @self.router.post("/score_completion")
        @self.base_endpoint
        async def score_completion(
            message_id: str = Body(..., description="Message ID"),
            score: float = Body(..., description="Completion score"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedScoreCompletionResponse:
            message_uuid = UUID(message_id)
            return await self.engine.ascore_completion(
                message_id=message_uuid, score=score
            )

        @self.router.get("/users_overview")
        @self.base_endpoint
        async def users_overview_app(
            user_ids: Optional[list[str]] = Query([]),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedUserOverviewResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `users_overview` endpoint.",
                    403,
                )

            user_uuids = (
                [UUID(user_id) for user_id in user_ids] if user_ids else None
            )

            return await self.engine.ausers_overview(
                user_ids=user_uuids, offset=offset, limit=limit
            )

        @self.router.delete("/delete", status_code=204)
        @self.base_endpoint
        async def delete_app(
            filters: str = Query(..., description="JSON-encoded filters"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> None:
            filters_dict = json.loads(filters) if filters else None
            return await self.engine.adelete(filters=filters_dict)

        @self.router.get("/documents_overview")
        @self.base_endpoint
        async def documents_overview_app(
            document_ids: list[str] = Query([]),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedDocumentOverviewResponse:
            request_user_ids = (
                None if auth_user.is_superuser else [auth_user.id]
            )
            document_uuids = [
                UUID(document_id) for document_id in document_ids
            ]
            result = await self.engine.adocuments_overview(
                user_ids=request_user_ids,
                group_ids=auth_user.group_ids,
                document_ids=document_uuids,
                offset=offset,
                limit=limit,
            )
            return result

        @self.router.get("/document_chunks/{document_id}")
        @self.base_endpoint
        async def document_chunks_app(
            document_id: str = Path(...),
            offset: Optional[int] = Query(0, ge=0),
            limit: Optional[int] = Query(100, ge=0),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedDocumentChunkResponse:
            document_uuid = UUID(document_id)
            chunks = await self.engine.adocument_chunks(
                document_uuid, offset, limit
            )

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

        @self.router.get("/inspect_knowledge_graph")
        @self.base_endpoint
        async def inspect_knowledge_graph(
            offset: int = 0,
            limit: int = 100,
            print_descriptions: bool = False,
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedKnowledgeGraphResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `inspect_knowledge_graph` endpoint.",
                    403,
                )
            return await self.engine.ainspect_knowledge_graph(
                offset=offset,
                limit=limit,
                print_descriptions=print_descriptions,
            )

        @self.router.get("/groups_overview")
        @self.base_endpoint
        async def groups_overview_app(
            group_ids: Optional[list[str]] = Query(None),
            offset: Optional[int] = Query(0, ge=0),
            limit: Optional[int] = Query(100, ge=1, le=1000),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupOverviewResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `groups_overview` endpoint.",
                    403,
                )

            group_uuids = (
                [UUID(group_id) for group_id in group_ids]
                if group_ids
                else None
            )
            return await self.engine.agroups_overview(
                group_ids=group_uuids, offset=offset, limit=limit
            )

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
            group_id: str = Path(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can get group details.", 403
                )
            group_uuid = UUID(group_id)
            result = await self.engine.aget_group(group_uuid)
            return result

        @self.router.put("/update_group")
        @self.base_endpoint
        async def update_group_app(
            group_id: str = Body(..., description="Group ID"),
            name: Optional[str] = Body(None, description="Updated group name"),
            description: Optional[str] = Body(
                None, description="Updated group description"
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupResponse:
            if not auth_user.is_superuser:
                raise R2RException("Only a superuser can update groups.", 403)
            group_uuid = UUID(group_id)
            return await self.engine.aupdate_group(
                group_uuid, name, description
            )

        @self.router.delete("/delete_group/{group_id}")
        @self.base_endpoint
        async def delete_group_app(
            group_id: str = Path(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only a superuser can delete groups.", 403)
            group_uuid = UUID(group_id)
            return await self.engine.adelete_group(group_uuid)

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
            return await self.engine.alist_groups(
                offset=offset, limit=min(max(limit, 1), 1000)
            )

        @self.router.post("/add_user_to_group")
        @self.base_endpoint
        async def add_user_to_group_app(
            user_id: str = Body(..., description="User ID"),
            group_id: str = Body(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedAddUserResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can add users to groups.", 403
                )
            user_uuid = UUID(user_id)
            group_uuid = UUID(group_id)
            return await self.engine.aadd_user_to_group(user_uuid, group_uuid)

        @self.router.post("/remove_user_from_group")
        @self.base_endpoint
        async def remove_user_from_group_app(
            user_id: str = Body(..., description="User ID"),
            group_id: str = Body(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can remove users from groups.", 403
                )
            user_uuid = UUID(user_id)
            group_uuid = UUID(group_id)
            await self.engine.aremove_user_from_group(user_uuid, group_uuid)
            return None

        # TODO - Proivde response model
        @self.router.get("/get_users_in_group/{group_id}")
        @self.base_endpoint
        async def get_users_in_group_app(
            group_id: str = Path(..., description="Group ID"),
            offset: int = Query(0, ge=0, description="Pagination offset"),
            limit: int = Query(
                100, ge=1, le=1000, description="Pagination limit"
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can get users in a group.", 403
                )
            group_uuid = UUID(group_id)
            return await self.engine.aget_users_in_group(
                group_id=group_uuid,
                offset=offset,
                limit=min(max(limit, 1), 1000),
            )

        @self.router.get("/user_groups/{user_id}")
        @self.base_endpoint
        async def get_groups_for_user_app(
            user_id: str = Path(..., description="User ID"),
            offset: int = Query(0, ge=0, description="Pagination offset"),
            limit: int = Query(
                100, ge=1, le=1000, description="Pagination limit"
            ),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can get groups for a user.", 403
                )
            user_uuid = UUID(user_id)
            return await self.engine.aget_groups_for_user(
                user_uuid, offset, limit
            )

        @self.router.post("/assign_document_to_group")
        @self.base_endpoint
        async def assign_document_to_group_app(
            document_id: str = Body(..., description="Document ID"),
            group_id: str = Body(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can assign documents to groups.", 403
                )
            document_uuid = UUID(document_id)
            group_uuid = UUID(group_id)
            return await self.engine.aassign_document_to_group(
                document_uuid, group_uuid
            )

        @self.router.post("/remove_document_from_group")
        @self.base_endpoint
        async def remove_document_from_group_app(
            document_id: str = Body(..., description="Document ID"),
            group_id: str = Body(..., description="Group ID"),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> None:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can remove documents from groups.", 403
                )
            document_uuid = UUID(document_id)
            group_uuid = UUID(group_id)
            await self.engine.aremove_document_from_group(
                document_uuid, group_uuid
            )
            return None

        @self.router.get("/document_groups/{document_id}")
        @self.base_endpoint
        async def document_groups_app(
            document_id: str = Path(..., description="Document ID"),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedGroupListResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can get the groups belonging to a document.",
                    403,
                )
            return await self.engine.adocument_groups(
                document_id, offset, limit
            )

        @self.router.get("/group/{group_id}/documents")
        @self.base_endpoint
        async def documents_in_group_app(
            group_id: str = Path(..., description="Group ID"),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.engine.providers.auth.auth_wrapper),
        ) -> WrappedDocumentOverviewResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can get documents in a group.", 403
                )
            group_uuid = UUID(group_id)
            return await self.engine.adocuments_in_group(
                group_uuid, offset, limit
            )
