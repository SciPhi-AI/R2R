from typing import Any, Optional
from uuid import UUID

from shared.api.models.base import WrappedBooleanResponse
from shared.api.models.management.responses import (
    WrappedConversationMessagesResponse,
    WrappedConversationResponse,
    WrappedConversationsResponse,
    WrappedMessageResponse,
)


class ConversationsSDK:
    def __init__(self, client):
        self.client = client

    async def create(
        self,
        name: Optional[str] = None,
    ) -> WrappedConversationResponse:
        """
        Create a new conversation.

        Returns:
            dict: Created conversation information
        """
        data = {"name": name} if name else None

        return await self.client._make_request(
            "POST",
            "conversations",
            data=data,
            version="v3",
        )

    async def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedConversationsResponse:
        """
        List conversations with pagination and sorting options.

        Args:
            ids (Optional[list[Union[str, UUID]]]): List of conversation IDs to retrieve
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of conversations and pagination information
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }
        if ids:
            params["ids"] = ids

        return await self.client._make_request(
            "GET",
            "conversations",
            params=params,
            version="v3",
        )

    async def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedConversationMessagesResponse:
        """
        Get detailed information about a specific conversation.

        Args:
            id (Union[str, UUID]): The ID of the conversation to retrieve

        Returns:
            dict: Detailed conversation information
        """
        return await self.client._make_request(
            "GET",
            f"conversations/{str(id)}",
            version="v3",
        )

    async def update(
        self,
        id: str | UUID,
        name: str,
    ) -> WrappedConversationResponse:
        """
        Update an existing conversation.

        Args:
            id (Union[str, UUID]): The ID of the conversation to update
            name (str): The new name of the conversation

        Returns:
            dict: The updated conversation
        """
        data: dict[str, Any] = {
            "name": name,
        }

        return await self.client._make_request(
            "POST",
            f"conversations/{str(id)}",
            json=data,
            version="v3",
        )

    async def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Delete a conversation.

        Args:
            id (Union[str, UUID]): The ID of the conversation to delete

        Returns:
            bool: True if deletion was successful
        """
        return await self.client._make_request(
            "DELETE",
            f"conversations/{str(id)}",
            version="v3",
        )

    async def add_message(
        self,
        id: str | UUID,
        content: str,
        role: str,
        metadata: Optional[dict] = None,
        parent_id: Optional[str] = None,
    ) -> WrappedMessageResponse:
        """
        Add a new message to a conversation.

        Args:
            id (Union[str, UUID]): The ID of the conversation to add the message to
            content (str): The content of the message
            role (str): The role of the message (e.g., "user" or "assistant")
            parent_id (Optional[str]): The ID of the parent message
            metadata (Optional[dict]): Additional metadata to attach to the message

        Returns:
            dict: Result of the operation, including the new message ID
        """
        data: dict[str, Any] = {
            "content": content,
            "role": role,
        }
        if parent_id:
            data["parent_id"] = parent_id
        if metadata:
            data["metadata"] = metadata

        return await self.client._make_request(
            "POST",
            f"conversations/{str(id)}/messages",
            json=data,
            version="v3",
        )

    async def update_message(
        self,
        id: str | UUID,
        message_id: str,
        content: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Update an existing message in a conversation.

        Args:
            id (str | UUID): The ID of the conversation containing the message
            message_id (str): The ID of the message to update
            content (str): The new content of the message
            metadata (dict): Additional metadata to attach to the message

        Returns:
            dict: Result of the operation, including the new message ID and branch ID
        """
        data = {"content": content}
        if metadata:
            data["metadata"] = metadata
        return await self.client._make_request(
            "POST",
            f"conversations/{str(id)}/messages/{message_id}",
            json=data,
            version="v3",
        )
