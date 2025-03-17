import logging
import textwrap
from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse

from core.base import Message, R2RException
from core.base.api.models import (
    GenericBooleanResponse,
    WrappedBooleanResponse,
    WrappedConversationMessagesResponse,
    WrappedConversationResponse,
    WrappedConversationsResponse,
    WrappedMessageResponse,
)

from ...abstractions import R2RProviders, R2RServices
from ...config import R2RConfig
from .base_router import BaseRouterV3

logger = logging.getLogger()


class ConversationsRouter(BaseRouterV3):
    def __init__(
        self, providers: R2RProviders, services: R2RServices, config: R2RConfig
    ):
        logging.info("Initializing ConversationsRouter")
        super().__init__(providers, services, config)

    def _setup_routes(self):
        @self.router.post(
            "/conversations",
            summary="Create a new conversation",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.conversations.create()
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.conversations.create();
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/conversations" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_conversation(
            name: Optional[str] = Body(
                None, description="The name of the conversation", embed=True
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedConversationResponse:
            """Create a new conversation.

            This endpoint initializes a new conversation for the authenticated
            user.
            """
            user_id = auth_user.id

            return await self.services.management.create_conversation(  # type: ignore
                user_id=user_id,
                name=name,
            )

        @self.router.get(
            "/conversations",
            summary="List conversations",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.conversations.list(
                                offset=0,
                                limit=10,
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.conversations.list();
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/conversations?offset=0&limit=10" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_conversations(
            ids: list[str] = Query(
                [],
                description="A list of conversation IDs to retrieve. If not provided, all conversations will be returned.",
            ),
            offset: int = Query(
                0,
                ge=0,
                description="Specifies the number of objects to skip. Defaults to 0.",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedConversationsResponse:
            """List conversations with pagination and sorting options.

            This endpoint returns a paginated list of conversations for the
            authenticated user.
            """
            requesting_user_id = (
                None if auth_user.is_superuser else [auth_user.id]
            )

            conversation_uuids = [
                UUID(conversation_id) for conversation_id in ids
            ]

            conversations_response = (
                await self.services.management.conversations_overview(
                    offset=offset,
                    limit=limit,
                    conversation_ids=conversation_uuids,
                    user_ids=requesting_user_id,
                )
            )
            return conversations_response["results"], {  # type: ignore
                "total_entries": conversations_response["total_entries"]
            }

        @self.router.post(
            "/conversations/export",
            summary="Export conversations to CSV",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            response = client.conversations.export(
                                output_path="export.csv",
                                columns=["id", "created_at"],
                                include_header=True,
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                await client.conversations.export({
                                    outputPath: "export.csv",
                                    columns: ["id", "created_at"],
                                    includeHeader: true,
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "http://127.0.0.1:7272/v3/conversations/export" \
                            -H "Authorization: Bearer YOUR_API_KEY" \
                            -H "Content-Type: application/json" \
                            -H "Accept: text/csv" \
                            -d '{ "columns": ["id", "created_at"], "include_header": true }' \
                            --output export.csv
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def export_conversations(
            background_tasks: BackgroundTasks,
            columns: Optional[list[str]] = Body(
                None, description="Specific columns to export"
            ),
            filters: Optional[dict] = Body(
                None, description="Filters to apply to the export"
            ),
            include_header: Optional[bool] = Body(
                True, description="Whether to include column headers"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> FileResponse:
            """Export conversations as a downloadable CSV file."""

            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can export data.",
                    403,
                )

            (
                csv_file_path,
                temp_file,
            ) = await self.services.management.export_conversations(
                columns=columns,
                filters=filters,
                include_header=include_header
                if include_header is not None
                else True,
            )

            background_tasks.add_task(temp_file.close)

            return FileResponse(
                path=csv_file_path,
                media_type="text/csv",
                filename="documents_export.csv",
            )

        @self.router.post(
            "/conversations/export_messages",
            summary="Export messages to CSV",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            response = client.conversations.export_messages(
                                output_path="export.csv",
                                columns=["id", "created_at"],
                                include_header=True,
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                await client.conversations.exportMessages({
                                    outputPath: "export.csv",
                                    columns: ["id", "created_at"],
                                    includeHeader: true,
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "http://127.0.0.1:7272/v3/conversations/export_messages" \
                            -H "Authorization: Bearer YOUR_API_KEY" \
                            -H "Content-Type: application/json" \
                            -H "Accept: text/csv" \
                            -d '{ "columns": ["id", "created_at"], "include_header": true }' \
                            --output export.csv
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def export_messages(
            background_tasks: BackgroundTasks,
            columns: Optional[list[str]] = Body(
                None, description="Specific columns to export"
            ),
            filters: Optional[dict] = Body(
                None, description="Filters to apply to the export"
            ),
            include_header: Optional[bool] = Body(
                True, description="Whether to include column headers"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> FileResponse:
            """Export conversations as a downloadable CSV file."""

            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can export data.",
                    403,
                )

            (
                csv_file_path,
                temp_file,
            ) = await self.services.management.export_messages(
                columns=columns,
                filters=filters,
                include_header=include_header
                if include_header is not None
                else True,
            )

            background_tasks.add_task(temp_file.close)

            return FileResponse(
                path=csv_file_path,
                media_type="text/csv",
                filename="documents_export.csv",
            )

        @self.router.get(
            "/conversations/{id}",
            summary="Get conversation details",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.conversations.get(
                                "123e4567-e89b-12d3-a456-426614174000"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.conversations.retrieve({
                                    id: "123e4567-e89b-12d3-a456-426614174000",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/conversations/123e4567-e89b-12d3-a456-426614174000" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_conversation(
            id: UUID = Path(
                ..., description="The unique identifier of the conversation"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedConversationMessagesResponse:
            """Get details of a specific conversation.

            This endpoint retrieves detailed information about a single
            conversation identified by its UUID.
            """
            requesting_user_id = (
                None if auth_user.is_superuser else [auth_user.id]
            )

            conversation = await self.services.management.get_conversation(
                conversation_id=id,
                user_ids=requesting_user_id,
            )
            return conversation  # type: ignore

        @self.router.post(
            "/conversations/{id}",
            summary="Update conversation",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.conversations.update("123e4567-e89b-12d3-a456-426614174000", "new_name")
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.conversations.update({
                                    id: "123e4567-e89b-12d3-a456-426614174000",
                                    name: "new_name",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/conversations/123e4567-e89b-12d3-a456-426614174000" \
                                -H "Authorization: Bearer YOUR_API_KEY" \
                                -H "Content-Type: application/json" \
                                -d '{"name": "new_name"}'
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_conversation(
            id: UUID = Path(
                ...,
                description="The unique identifier of the conversation to delete",
            ),
            name: str = Body(
                ...,
                description="The updated name for the conversation",
                embed=True,
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedConversationResponse:
            """Update an existing conversation.

            This endpoint updates the name of an existing conversation
            identified by its UUID.
            """
            return await self.services.management.update_conversation(  # type: ignore
                conversation_id=id,
                name=name,
            )

        @self.router.delete(
            "/conversations/{id}",
            summary="Delete conversation",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.conversations.delete("123e4567-e89b-12d3-a456-426614174000")
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.conversations.delete({
                                    id: "123e4567-e89b-12d3-a456-426614174000",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X DELETE "https://api.example.com/v3/conversations/123e4567-e89b-12d3-a456-426614174000" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Delete an existing conversation.

            This endpoint deletes a conversation identified by its UUID.
            """
            requesting_user_id = (
                None if auth_user.is_superuser else [auth_user.id]
            )

            await self.services.management.delete_conversation(
                conversation_id=id,
                user_ids=requesting_user_id,
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/conversations/{id}/messages",
            summary="Add message to conversation",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.conversations.add_message(
                                "123e4567-e89b-12d3-a456-426614174000",
                                content="Hello, world!",
                                role="user",
                                parent_id="parent_message_id",
                                metadata={"key": "value"}
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.conversations.addMessage({
                                    id: "123e4567-e89b-12d3-a456-426614174000",
                                    content: "Hello, world!",
                                    role: "user",
                                    parentId: "parent_message_id",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/conversations/123e4567-e89b-12d3-a456-426614174000/messages" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json" \\
                                -d '{"content": "Hello, world!", "parent_id": "parent_message_id", "metadata": {"key": "value"}}'
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def add_message(
            id: UUID = Path(
                ..., description="The unique identifier of the conversation"
            ),
            content: str = Body(
                ..., description="The content of the message to add"
            ),
            role: str = Body(
                ..., description="The role of the message to add"
            ),
            parent_id: Optional[UUID] = Body(
                None, description="The ID of the parent message, if any"
            ),
            metadata: Optional[dict[str, str]] = Body(
                None, description="Additional metadata for the message"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedMessageResponse:
            """Add a new message to a conversation.

            This endpoint adds a new message to an existing conversation.
            """
            if content == "":
                raise R2RException("Content cannot be empty", status_code=400)
            if role not in ["user", "assistant", "system"]:
                raise R2RException("Invalid role", status_code=400)
            message = Message(role=role, content=content)
            return await self.services.management.add_message(  # type: ignore
                conversation_id=id,
                content=message,
                parent_id=parent_id,
                metadata=metadata,
            )

        @self.router.post(
            "/conversations/{id}/messages/{message_id}",
            summary="Update message in conversation",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.conversations.update_message(
                                "123e4567-e89b-12d3-a456-426614174000",
                                "message_id_to_update",
                                content="Updated content"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.conversations.updateMessage({
                                    id: "123e4567-e89b-12d3-a456-426614174000",
                                    messageId: "message_id_to_update",
                                    content: "Updated content",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/conversations/123e4567-e89b-12d3-a456-426614174000/messages/message_id_to_update" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json" \\
                                -d '{"content": "Updated content"}'
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_message(
            id: UUID = Path(
                ..., description="The unique identifier of the conversation"
            ),
            message_id: UUID = Path(
                ..., description="The ID of the message to update"
            ),
            content: Optional[str] = Body(
                None, description="The new content for the message"
            ),
            metadata: Optional[dict[str, str]] = Body(
                None, description="Additional metadata for the message"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedMessageResponse:
            """Update an existing message in a conversation.

            This endpoint updates the content of an existing message in a
            conversation.
            """
            return await self.services.management.edit_message(  # type: ignore
                message_id=message_id,
                new_content=content,
                additional_metadata=metadata,
            )
