import logging
from typing import List, Optional, Union
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel

from core.base import Message, R2RException, RunType
from core.base.api.models import (
    WrappedConversationResponse,
    WrappedConversationsOverviewResponse,
    WrappedDeleteResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from .base_router import BaseRouterV3

logger = logging.getLogger()


class MessageContent(BaseModel):
    content: str
    parent_id: Optional[str] = None
    metadata: Optional[dict] = None


class ConversationsRouter(BaseRouterV3):
    def __init__(
        self,
        providers,
        services,
        orchestration_provider: Union[
            HatchetOrchestrationProvider, SimpleOrchestrationProvider
        ],
        run_type: RunType = RunType.MANAGEMENT,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _setup_routes(self):
        @self.router.post("/conversations")
        @self.base_endpoint
        async def create_conversation(
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedConversationResponse:
            """
            Create a new conversation.
            """
            return await self.services.management.create_conversation()

        @self.router.get("/conversations")
        @self.base_endpoint
        async def list_conversations(
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            sort_by: Optional[str] = Query(None),
            sort_order: Optional[str] = Query("desc"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedConversationsOverviewResponse:
            """
            List conversations with pagination and sorting options.
            """
            conversations_response = (
                await self.services.management.conversations_overview(
                    conversation_ids=[],  # Empty list to get all conversations
                    offset=offset,
                    limit=limit,
                )
            )
            return conversations_response["results"], {
                "total_entries": conversations_response["total_entries"]
            }

        @self.router.get("/conversations/{id}")
        @self.base_endpoint
        async def get_conversation(
            id: UUID = Path(...),
            branch_id: Optional[str] = Query(None),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedConversationResponse:
            """
            Get details of a specific conversation.
            """
            return await self.services.management.get_conversation(
                str(id),
                branch_id,
            )

        @self.router.delete("/conversations/{id}")
        @self.base_endpoint
        async def delete_conversation(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedDeleteResponse:
            """
            Delete an existing conversation.
            """
            await self.services.management.delete_conversation(str(id))
            return None

        @self.router.post("/conversations/{id}/messages")
        @self.base_endpoint
        async def add_message(
            id: UUID = Path(...),
            message_content: MessageContent = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> dict:
            """
            Add a new message to a conversation.
            """
            message = Message(content=message_content.content)
            message_id = await self.services.management.add_message(
                str(id),
                message,
                message_content.parent_id,
                message_content.metadata,
            )
            return {"message_id": message_id}

        @self.router.put("/conversations/{id}/messages/{message_id}")
        @self.base_endpoint
        async def update_message(
            id: UUID = Path(...),
            message_id: str = Path(...),
            content: str = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> dict:
            """
            Update an existing message in a conversation.
            """
            new_message_id, new_branch_id = (
                await self.services.management.edit_message(
                    message_id, content
                )
            )
            return {
                "new_message_id": new_message_id,
                "new_branch_id": new_branch_id,
            }

        @self.router.get("/conversations/{id}/branches")
        @self.base_endpoint
        async def list_branches(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> dict:
            """
            List all branches in a conversation.
            """
            branches = await self.services.management.branches_overview(
                str(id)
            )
            return {"branches": branches}

        # Commented endpoints to be published after more testing
        # @self.router.get("/conversations/{id}/branches/{branch_id}/next")
        # @self.base_endpoint
        # async def get_next_branch(
        #     id: UUID = Path(...),
        #     branch_id: str = Path(...),
        #     auth_user=Depends(self.providers.auth.auth_wrapper),
        # ) -> dict:
        #     """
        #     Get the next branch in the conversation.
        #     """
        #     next_branch_id = await self.services.management.get_next_branch(branch_id)
        #     return {"next_branch_id": next_branch_id}

        # @self.router.get("/conversations/{id}/branches/{branch_id}/previous")
        # @self.base_endpoint
        # async def get_previous_branch(
        #     id: UUID = Path(...),
        #     branch_id: str = Path(...),
        #     auth_user=Depends(self.providers.auth.auth_wrapper),
        # ) -> dict:
        #     """
        #     Get the previous branch in the conversation.
        #     """
        #     prev_branch_id = await self.services.management.get_prev_branch(branch_id)
        #     return {"prev_branch_id": prev_branch_id}

        # @self.router.post("/conversations/{id}/messages/{message_id}/branch")
        # @self.base_endpoint
        # async def create_branch(
        #     id: UUID = Path(...),
        #     message_id: str = Path(...),
        #     auth_user=Depends(self.providers.auth.auth_wrapper),
        # ) -> dict:
        #     """
        #     Create a new branch starting from a specific message.
        #     """
        #     branch_id = await self.services.management.branch_at_message(message_id)
        #     return {"branch_id": branch_id}
