# TODO - Cleanup the handling for non-auth configurations
import json
import mimetypes
from datetime import datetime, timezone
from typing import Optional, Set
from uuid import UUID

import psutil
from fastapi import Body, Depends, Path, Query
from fastapi.responses import StreamingResponse
from pydantic import Json

from core.base import R2RException
from core.base.api.models import (
    WrappedAddUserResponse,
    WrappedAnalyticsResponse,
    WrappedAppSettingsResponse,
    WrappedCollectionListResponse,
    WrappedCollectionOverviewResponse,
    WrappedCollectionResponse,
    WrappedDeleteResponse,
    WrappedDocumentChunkResponse,
    WrappedDocumentOverviewResponse,
    WrappedGetPromptsResponse,
    WrappedKnowledgeGraphResponse,
    WrappedLogResponse,
    WrappedPromptMessageResponse,
    WrappedScoreCompletionResponse,
    WrappedServerStatsResponse,
    WrappedUserCollectionResponse,
    WrappedUserOverviewResponse,
    WrappedUsersInCollectionResponse,
)
from core.base.logging import AnalysisTypes, LogFilterCriteria
from core.base.providers import OrchestrationProvider

from ..services.management_service import ManagementService
from .base_router import BaseRouter, RunType


class ManagementRouter(BaseRouter):
    def __init__(
        self,
        service: ManagementService,
        orchestration_provider: OrchestrationProvider,
        run_type: RunType = RunType.MANAGEMENT,
    ):
        super().__init__(service, orchestration_provider, run_type)
        self.service: ManagementService = service  # for type hinting
        self.start_time = datetime.now(timezone.utc)

    # TODO: remove this from the management route, it should be at the base of the server
    def _setup_routes(self):
        @self.router.get("/health")
        @self.base_endpoint
        async def health_check():
            return {"response": "ok"}

        @self.router.get("/server_stats")
        @self.base_endpoint
        async def server_stats(
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedServerStatsResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only an authorized user can call the `server_stats` endpoint.",
                    403,
                )
            return {  # type: ignore
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
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedPromptMessageResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `update_prompt` endpoint.",
                    403,
                )

            result = await self.service.update_prompt(
                name, template, input_types
            )
            return result  # type: ignore

        @self.router.post("/add_prompt")
        @self.base_endpoint
        async def add_prompt_app(
            name: str = Body(..., description="Prompt name"),
            template: str = Body(..., description="Prompt template"),
            input_types: dict[str, str] = Body({}, description="Input types"),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedPromptMessageResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `add_prompt` endpoint.",
                    403,
                )
            result = await self.service.add_prompt(name, template, input_types)
            return result  # type: ignore

        @self.router.get("/get_prompt/{prompt_name}")
        @self.base_endpoint
        async def get_prompt_app(
            prompt_name: str = Path(..., description="Prompt name"),
            inputs: Optional[Json[dict]] = Query(
                None, description="JSON-encoded prompt inputs"
            ),
            prompt_override: Optional[str] = Query(
                None, description="Prompt override"
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedPromptMessageResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `get_prompt` endpoint.",
                    403,
                )
            result = await self.service.get_prompt(
                prompt_name, inputs, prompt_override
            )
            return result  # type: ignore

        @self.router.get("/get_all_prompts")
        @self.base_endpoint
        async def get_all_prompts_app(
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedGetPromptsResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `get_all_prompts` endpoint.",
                    403,
                )
            result = await self.service.get_all_prompts()
            return {"prompts": result}  # type: ignore

        @self.router.delete("/delete_prompt/{prompt_name}")
        @self.base_endpoint
        async def delete_prompt_app(
            prompt_name: str = Path(..., description="Prompt name"),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedDeleteResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `delete_prompt` endpoint.",
                    403,
                )
            await self.service.delete_prompt(prompt_name)
            return None  # type: ignore

        @self.router.get("/analytics")
        @self.base_endpoint
        async def get_analytics_app(
            filter_criteria: Optional[Json[dict]] = Query({}),
            analysis_types: Optional[Json[dict]] = Query({}),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedAnalyticsResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `analytics` endpoint.", 403
                )

            try:
                result = await self.service.analytics(
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
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedLogResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `logs` endpoint.", 403
                )

            return await self.service.logs(
                run_type_filter=run_type_filter,
                offset=offset,
                limit=limit,
            )

        @self.router.get("/app_settings")
        @self.base_endpoint
        async def app_settings(
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedAppSettingsResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `app_settings` endpoint.",
                    403,
                )
            return await self.service.app_settings()

        @self.router.post("/score_completion")
        @self.base_endpoint
        async def score_completion(
            message_id: str = Body(..., description="Message ID"),
            score: float = Body(..., description="Completion score"),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedScoreCompletionResponse:
            message_uuid = UUID(message_id)
            return await self.service.score_completion(
                message_id=message_uuid, score=score
            )

        @self.router.get("/users_overview")
        @self.base_endpoint
        async def users_overview_app(
            user_ids: Optional[list[str]] = Query([]),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedUserOverviewResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `users_overview` endpoint.",
                    403,
                )

            user_uuids = (
                [UUID(user_id) for user_id in user_ids] if user_ids else None
            )

            users_overview_response = await self.service.users_overview(
                user_ids=user_uuids, offset=offset, limit=limit
            )

            return users_overview_response["results"], {  # type: ignore
                "total_entries": users_overview_response["total_entries"]
            }

        @self.router.delete("/delete", status_code=204)
        @self.base_endpoint
        async def delete_app(
            filters: str = Query(..., description="JSON-encoded filters"),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            filters_dict = json.loads(filters) if filters else None
            return await self.service.delete(filters=filters_dict)  # type: ignore

        @self.router.get(
            "/download_file/{document_id}", response_class=StreamingResponse
        )
        @self.base_endpoint
        async def download_file_app(
            document_id: str = Path(..., description="Document ID"),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            """
            Download a file by its document ID as a stream.
            """
            # TODO: Add a check to see if the user has access to the file

            try:
                document_uuid = UUID(document_id)
            except ValueError:
                raise R2RException(
                    status_code=400, message="Invalid document ID format."
                )

            file_tuple = await self.service.download_file(document_uuid)
            if not file_tuple:
                raise R2RException(status_code=404, message="File not found.")

            file_name, file_content, file_size = file_tuple

            mime_type, _ = mimetypes.guess_type(file_name)
            if not mime_type:
                mime_type = "application/octet-stream"

            async def file_stream():
                chunk_size = 1024 * 1024  # 1MB
                while True:
                    data = file_content.read(chunk_size)
                    if not data:
                        break
                    yield data

            return StreamingResponse(  # type: ignore
                file_stream(),
                media_type=mime_type,
                headers={
                    "Content-Disposition": f'inline; filename="{file_name}"',
                    "Content-Length": str(file_size),
                },
            )

        @self.router.get("/documents_overview")
        @self.base_endpoint
        async def documents_overview_app(
            document_ids: list[str] = Query([]),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedDocumentOverviewResponse:
            request_user_ids = (
                None if auth_user.is_superuser else [auth_user.id]
            )
            document_uuids = [
                UUID(document_id) for document_id in document_ids
            ]
            documents_overview_response = (
                await self.service.documents_overview(
                    user_ids=request_user_ids,
                    collection_ids=auth_user.collection_ids,
                    document_ids=document_uuids,
                    offset=offset,
                    limit=limit,
                )
            )
            return documents_overview_response["results"], {  # type: ignore
                "total_entries": documents_overview_response["total_entries"]
            }

        @self.router.get("/document_chunks/{document_id}")
        @self.base_endpoint
        async def document_chunks_app(
            document_id: str = Path(...),
            offset: Optional[int] = Query(0, ge=0),
            limit: Optional[int] = Query(100, ge=0),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedDocumentChunkResponse:
            document_uuid = UUID(document_id)

            document_chunks = await self.service.document_chunks(
                document_uuid, offset, limit
            )

            document_chunks_result = document_chunks["results"]

            if not document_chunks_result:
                raise R2RException(
                    "No chunks found for the given document ID.",
                    404,
                )

            is_owner = str(document_chunks_result[0].get("user_id")) == str(
                auth_user.id
            )

            if not is_owner and not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can arbitrarily call document_chunks.",
                    403,
                )

            return document_chunks_result, {  # type: ignore
                "total_entries": document_chunks["total_entries"]
            }

        @self.router.get("/collections_overview")
        @self.base_endpoint
        async def collections_overview_app(
            collection_ids: Optional[list[str]] = Query(None),
            offset: Optional[int] = Query(0, ge=0),
            limit: Optional[int] = Query(100, ge=1, le=1000),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedCollectionOverviewResponse:
            user_collections: Optional[Set[UUID]] = (
                None
                if auth_user.is_superuser
                else {UUID(str(cid)) for cid in auth_user.collection_ids}
            )

            filtered_collections: Optional[Set[UUID]] = None

            if collection_ids:
                input_collections = {UUID(cid) for cid in collection_ids}
                if user_collections is not None:
                    filtered_collections = input_collections.intersection(
                        user_collections
                    )
                else:
                    filtered_collections = input_collections
            else:
                filtered_collections = user_collections

            collections_overview_response = (
                await self.service.collections_overview(
                    collection_ids=(
                        [str(cid) for cid in filtered_collections]
                        if filtered_collections is not None
                        else None
                    ),
                    offset=offset,
                    limit=limit,
                )
            )

            return collections_overview_response["results"], {  # type: ignore
                "total_entries": collections_overview_response["total_entries"]
            }

        @self.router.post("/create_collection")
        @self.base_endpoint
        async def create_collection_app(
            name: str = Body(..., description="Collection name"),
            description: Optional[str] = Body(
                "", description="Collection description"
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedCollectionResponse:
            collection_id = await self.service.create_collection(
                name, description
            )
            return await self.service.add_user_to_collection(  # type: ignore
                auth_user.id, collection_id.collection_id
            )

        @self.router.get("/get_collection/{collection_id}")
        @self.base_endpoint
        async def get_collection_app(
            collection_id: str = Path(..., description="Collection ID"),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedCollectionResponse:
            collection_uuid = UUID(collection_id)
            if (
                not auth_user.is_superuser
                and collection_uuid not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            result = await self.service.get_collection(collection_uuid)
            return result  # type: ignore

        @self.router.put("/update_collection")
        @self.base_endpoint
        async def update_collection_app(
            collection_id: str = Body(..., description="Collection ID"),
            name: Optional[str] = Body(
                None, description="Updated collection name"
            ),
            description: Optional[str] = Body(
                None, description="Updated collection description"
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedCollectionResponse:
            collection_uuid = UUID(collection_id)
            if (
                not auth_user.is_superuser
                and collection_uuid not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            return await self.service.update_collection(  # type: ignore
                collection_uuid, name, description
            )

        @self.router.delete("/delete_collection/{collection_id}")
        @self.base_endpoint
        async def delete_collection_app(
            collection_id: str = Path(..., description="Collection ID"),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            collection_uuid = UUID(collection_id)
            if (
                not auth_user.is_superuser
                and collection_uuid not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )
            return await self.service.delete_collection(collection_uuid)  # type: ignore

        @self.router.get("/list_collections")
        @self.base_endpoint
        async def list_collections_app(
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedCollectionListResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can list all collections.", 403
                )
            list_collections_response = await self.service.list_collections(
                offset=offset, limit=min(max(limit, 1), 1000)
            )

            return list_collections_response["results"], {  # type: ignore
                "total_entries": list_collections_response["total_entries"]
            }

        @self.router.post("/add_user_to_collection")
        @self.base_endpoint
        async def add_user_to_collection_app(
            user_id: str = Body(..., description="User ID"),
            collection_id: str = Body(..., description="Collection ID"),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedAddUserResponse:
            collection_uuid = UUID(collection_id)
            user_uuid = UUID(user_id)
            if (
                not auth_user.is_superuser
                and collection_uuid not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            result = await self.service.add_user_to_collection(
                user_uuid, collection_uuid
            )
            return {"result": result}  # type: ignore

        @self.router.post("/remove_user_from_collection")
        @self.base_endpoint
        async def remove_user_from_collection_app(
            user_id: str = Body(..., description="User ID"),
            collection_id: str = Body(..., description="Collection ID"),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            collection_uuid = UUID(collection_id)
            user_uuid = UUID(user_id)
            if (
                not auth_user.is_superuser
                and collection_uuid not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            await self.service.remove_user_from_collection(
                user_uuid, collection_uuid
            )
            return None  # type: ignore

        # TODO - Proivde response model
        @self.router.get("/get_users_in_collection/{collection_id}")
        @self.base_endpoint
        async def get_users_in_collection_app(
            collection_id: str = Path(..., description="Collection ID"),
            offset: int = Query(0, ge=0, description="Pagination offset"),
            limit: int = Query(
                100, ge=1, le=1000, description="Pagination limit"
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedUsersInCollectionResponse:
            collection_uuid = UUID(collection_id)
            if (
                not auth_user.is_superuser
                and collection_uuid not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            users_in_collection_response = (
                await self.service.get_users_in_collection(
                    collection_id=collection_uuid,
                    offset=offset,
                    limit=min(max(limit, 1), 1000),
                )
            )

            return users_in_collection_response["results"], {  # type: ignore
                "total_entries": users_in_collection_response["total_entries"]
            }

        @self.router.get("/user_collections/{user_id}")
        @self.base_endpoint
        async def get_collections_for_user_app(
            user_id: str = Path(..., description="User ID"),
            offset: int = Query(0, ge=0, description="Pagination offset"),
            limit: int = Query(
                100, ge=1, le=1000, description="Pagination limit"
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedUserCollectionResponse:
            if str(auth_user.id) != user_id or not auth_user.is_superuser:
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )
            user_uuid = UUID(user_id)
            user_collection_response = (
                await self.service.get_collections_for_user(
                    user_uuid, offset, limit
                )
            )

            return user_collection_response["results"], {  # type: ignore
                "total_entries": user_collection_response["total_entries"]
            }

        @self.router.post("/assign_document_to_collection")
        @self.base_endpoint
        async def assign_document_to_collection_app(
            document_id: str = Body(..., description="Document ID"),
            collection_id: str = Body(..., description="Collection ID"),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            collection_uuid = UUID(collection_id)
            document_uuid = UUID(document_id)
            if (
                not auth_user.is_superuser
                and collection_uuid not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            return await self.service.assign_document_to_collection(  # type: ignore
                document_uuid, collection_uuid
            )

        @self.router.post("/remove_document_from_collection")
        @self.base_endpoint
        async def remove_document_from_collection_app(
            document_id: str = Body(..., description="Document ID"),
            collection_id: str = Body(..., description="Collection ID"),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedDeleteResponse:
            collection_uuid = UUID(collection_id)
            document_uuid = UUID(document_id)
            if (
                not auth_user.is_superuser
                and collection_uuid not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            await self.service.remove_document_from_collection(
                document_uuid, collection_uuid
            )
            return None  # type: ignore

        @self.router.get("/document_collections/{document_id}")
        @self.base_endpoint
        async def document_collections_app(
            document_id: str = Path(..., description="Document ID"),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedCollectionListResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can get the collections belonging to a document.",
                    403,
                )
            document_collections_response = (
                await self.service.document_collections(
                    document_id, offset, limit
                )
            )

            return document_collections_response["results"], {  # type: ignore
                "total_entries": document_collections_response["total_entries"]
            }

        @self.router.get("/collection/{collection_id}/documents")
        @self.base_endpoint
        async def documents_in_collection_app(
            collection_id: str = Path(..., description="Collection ID"),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedDocumentOverviewResponse:
            collection_uuid = UUID(collection_id)
            if (
                not auth_user.is_superuser
                and collection_uuid not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            documents_in_collection_response = (
                await self.service.documents_in_collection(
                    collection_uuid, offset, limit
                )
            )

            return documents_in_collection_response["results"], {  # type: ignore
                "total_entries": documents_in_collection_response[
                    "total_entries"
                ]
            }
