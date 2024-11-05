import logging
from typing import List, Optional, Union
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel, Field

from core.base import Message, R2RException, RunType
from core.base.api.models import (
    ResultsWrapper,
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
    content: str = Field(..., description="The content of the message")
    parent_id: Optional[str] = Field(
        None, description="The ID of the parent message, if any"
    )
    metadata: Optional[dict] = Field(
        None, description="Additional metadata for the message"
    )


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
        @self.router.post(
            "/conversations",
            summary="Create a new conversation",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# when using auth, do client.login(...)

result = client.conversations.create()
""",
                    },
                    {
                        "lang": "cURL",
                        "source": """
curl -X POST "https://api.example.com/v3/conversations" \\
     -H "Authorization: Bearer YOUR_API_KEY"
""",
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_conversation(
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedConversationResponse:
            """
            Create a new conversation.

            This endpoint initializes a new conversation for the authenticated user.

            Args:
                auth_user: The authenticated user making the request.

            Returns:
                WrappedConversationResponse: Details of the newly created conversation.

            Raises:
                R2RException: If there's an error in creating the conversation.
            """
            return await self.services.management.create_conversation()

        @self.router.get(
            "/conversations",
            summary="List conversations",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# when using auth, do client.login(...)

result = client.conversations.list(
    offset=0,
    limit=10,
    sort_by="created_at",
    sort_order="desc"
)
""",
                    },
                    {
                        "lang": "cURL",
                        "source": """
curl -X GET "https://api.example.com/v3/conversations?offset=0&limit=10&sort_by=created_at&sort_order=desc" \\
     -H "Authorization: Bearer YOUR_API_KEY"
""",
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_conversations(
            offset: int = Query(
                0, ge=0, description="The number of conversations to skip"
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="The maximum number of conversations to return",
            ),
            sort_by: Optional[str] = Query(
                None, description="The field to sort the conversations by"
            ),
            sort_order: Optional[str] = Query(
                "desc",
                description="The order to sort the conversations ('asc' or 'desc')",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedConversationsOverviewResponse:
            """
            List conversations with pagination and sorting options.

            This endpoint returns a paginated list of conversations for the authenticated user.

            Args:
                offset (int): The number of conversations to skip (for pagination).
                limit (int): The maximum number of conversations to return (1-1000).
                sort_by (str, optional): The field to sort the conversations by.
                sort_order (str, optional): The order to sort the conversations ("asc" or "desc").
                auth_user: The authenticated user making the request.

            Returns:
                WrappedConversationsOverviewResponse: A paginated list of conversations and total count.

            Raises:
                R2RException: If there's an error in retrieving the conversations.
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

        @self.router.get(
            "/conversations/{id}",
            summary="Get conversation details",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# when using auth, do client.login(...)

result = client.conversations.get(
    "123e4567-e89b-12d3-a456-426614174000",
    branch_id="branch_1"
)
""",
                    },
                    {
                        "lang": "cURL",
                        "source": """
curl -X GET "https://api.example.com/v3/conversations/123e4567-e89b-12d3-a456-426614174000?branch_id=branch_1" \\
     -H "Authorization: Bearer YOUR_API_KEY"
""",
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_conversation(
            id: UUID = Path(
                ..., description="The unique identifier of the conversation"
            ),
            branch_id: Optional[str] = Query(
                None, description="The ID of the specific branch to retrieve"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedConversationResponse:
            """
            Get details of a specific conversation.

            This endpoint retrieves detailed information about a single conversation identified by its UUID.

            Args:
                id (UUID): The unique identifier of the conversation.
                branch_id (str, optional): The ID of the specific branch to retrieve.
                auth_user: The authenticated user making the request.

            Returns:
                WrappedConversationResponse: Detailed information about the requested conversation.

            Raises:
                R2RException: If the conversation is not found or the user doesn't have access.
            """
            return await self.services.management.get_conversation(
                str(id),
                branch_id,
            )

        @self.router.delete(
            "/conversations/{id}",
            summary="Delete conversation",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# when using auth, do client.login(...)

result = client.conversations.delete("123e4567-e89b-12d3-a456-426614174000")
""",
                    },
                    {
                        "lang": "cURL",
                        "source": """
curl -X DELETE "https://api.example.com/v3/conversations/123e4567-e89b-12d3-a456-426614174000" \\
     -H "Authorization: Bearer YOUR_API_KEY"
""",
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_conversation(
            id: UUID = Path(
                ...,
                description="The unique identifier of the conversation to delete",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[bool]:
            """
            Delete an existing conversation.

            This endpoint deletes a conversation identified by its UUID.

            Args:
                id (UUID): The unique identifier of the conversation to delete.
                auth_user: The authenticated user making the request.

            Returns:
                WrappedDeleteResponse: Confirmation of the deletion.

            Raises:
                R2RException: If the conversation is not found or the user doesn't have permission to delete it.
            """
            await self.services.management.delete_conversation(str(id))
            return None

        @self.router.post(
            "/conversations/{id}/messages",
            summary="Add message to conversation",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# when using auth, do client.login(...)

result = client.conversations.add_message(
    "123e4567-e89b-12d3-a456-426614174000",
    content="Hello, world!",
    parent_id="parent_message_id",
    metadata={"key": "value"}
)
""",
                    },
                    {
                        "lang": "cURL",
                        "source": """
curl -X POST "https://api.example.com/v3/conversations/123e4567-e89b-12d3-a456-426614174000/messages" \\
     -H "Authorization: Bearer YOUR_API_KEY" \\
     -H "Content-Type: application/json" \\
     -d '{"content": "Hello, world!", "parent_id": "parent_message_id", "metadata": {"key": "value"}}'
""",
                    },
                ]
            },
        )
        @self.base_endpoint
        async def add_message(
            id: UUID = Path(
                ..., description="The unique identifier of the conversation"
            ),
            message_content: MessageContent = Body(
                ..., description="The content of the message to add"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> dict:
            """
            Add a new message to a conversation.

            This endpoint adds a new message to an existing conversation.

            Args:
                id (UUID): The unique identifier of the conversation.
                message_content (MessageContent): The content of the message to add.
                auth_user: The authenticated user making the request.

            Returns:
                dict: A dictionary containing the ID of the newly added message.

            Raises:
                R2RException: If the conversation is not found or the user doesn't have permission to add messages.
            """
            message = Message(content=message_content.content)
            message_id = await self.services.management.add_message(
                str(id),
                message,
                message_content.parent_id,
                message_content.metadata,
            )
            return {"message_id": message_id}

        @self.router.put(
            "/conversations/{id}/messages/{message_id}",
            summary="Update message in conversation",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# when using auth, do client.login(...)

result = client.conversations.update_message(
    "123e4567-e89b-12d3-a456-426614174000",
    "message_id_to_update",
    content="Updated content"
)
""",
                    },
                    {
                        "lang": "cURL",
                        "source": """
curl -X PUT "https://api.example.com/v3/conversations/123e4567-e89b-12d3-a456-426614174000/messages/message_id_to_update" \\
     -H "Authorization: Bearer YOUR_API_KEY" \\
     -H "Content-Type: application/json" \\
     -d '{"content": "Updated content"}'
""",
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_message(
            id: UUID = Path(
                ..., description="The unique identifier of the conversation"
            ),
            message_id: str = Path(
                ..., description="The ID of the message to update"
            ),
            content: str = Body(
                ..., description="The new content for the message"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> dict:
            """
            Update an existing message in a conversation.

            This endpoint updates the content of an existing message in a conversation.

            Args:
                id (UUID): The unique identifier of the conversation.
                message_id (str): The ID of the message to update.
                content (str): The new content for the message.
                auth_user: The authenticated user making the request.

            Returns:
                dict: A dictionary containing the new message ID and new branch ID.

            Raises:
                R2RException: If the conversation or message is not found, or if the user doesn't have permission to update.
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

        @self.router.get(
            "/conversations/{id}/branches",
            summary="List branches in conversation",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# when using auth, do client.login(...)

result = client.conversations.list_branches("123e4567-e89b-12d3-a456-426614174000")
""",
                    },
                    {
                        "lang": "cURL",
                        "source": """
curl -X GET "https://api.example.com/v3/conversations/123e4567-e89b-12d3-a456-426614174000/branches" \\
     -H "Authorization: Bearer YOUR_API_KEY"
""",
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_branches(
            id: UUID = Path(
                ..., description="The unique identifier of the conversation"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> dict:
            """
            List all branches in a conversation.

            This endpoint retrieves all branches associated with a specific conversation.

            Args:
                id (UUID): The unique identifier of the conversation.
                auth_user: The authenticated user making the request.

            Returns:
                dict: A dictionary containing a list of branches in the conversation.

            Raises:
                R2RException: If the conversation is not found or the user doesn't have permission to view branches.
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
