from typing import Any, Optional
from uuid import UUID

from shared.api.models.base import WrappedBooleanResponse
from shared.api.models.management.responses import (
    WrappedBranchesResponse,
    WrappedConversationMessagesResponse,
    WrappedConversationResponse,
    WrappedConversationsResponse,
    WrappedMessageResponse,
)


class ConversationsSDK:
    def __init__(self, client):
        self.client = client

    async def create(self) -> WrappedConversationResponse:
        """
        Create a new conversation.

        Returns:
            dict: Created conversation information
        """
        return await self.client._make_request(
            "POST",
            "conversations",
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
        branch_id: Optional[str] = None,
    ) -> WrappedConversationMessagesResponse:
        """
        Get detailed information about a specific conversation.

        Args:
            id (Union[str, UUID]): The ID of the conversation to retrieve
            branch_id (Optional[str]): The ID of the branch to retrieve

        Returns:
            dict: Detailed conversation information
        """
        params = {}
        if branch_id:
            params["branch_id"] = branch_id

        return await self.client._make_request(
            "GET",
            f"conversations/{str(id)}",
            params=params,
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
        parent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
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
            data=data,
            version="v3",
        )

    async def update_message(
        self,
        id: str | UUID,
        message_id: str,
        content: str,
    ) -> dict:
        """
        Update an existing message in a conversation.

        Args:
            id (Union[str, UUID]): The ID of the conversation containing the message
            message_id (str): The ID of the message to update
            content (str): The new content of the message

        Returns:
            dict: Result of the operation, including the new message ID and branch ID
        """
        # data = {"content": content}
        return await self.client._make_request(
            "PUT",
            f"conversations/{str(id)}/messages/{message_id}",
            json=content,
            version="v3",
        )

    async def list_branches(
        self,
        id: str | UUID,
    ) -> WrappedBranchesResponse:
        """
        List all branches in a conversation.

        Args:
            id (Union[str, UUID]): The ID of the conversation to list branches for

        Returns:
            dict: List of branches in the conversation
        """
        return await self.client._make_request(
            "GET",
            f"conversations/{str(id)}/branches",
            version="v3",
        )

    # Commented methods to be added after more testing
    # async def get_next_branch(
    #     self,
    #     id: Union[str, UUID],
    #     branch_id: str,
    # ) -> dict:
    #     """
    #     Get the next branch in the conversation.
    #     """
    #     return await self.client._make_request(
    #         "GET", f"conversations/{str(id)}/branches/{branch_id}/next"
    #     )

    # async def get_previous_branch(
    #     self,
    #     id: Union[str, UUID],
    #     branch_id: str,
    # ) -> dict:
    #     """
    #     Get the previous branch in the conversation.
    #     """
    #     return await self.client._make_request(
    #         "GET", f"conversations/{str(id)}/branches/{branch_id}/previous"
    #     )

    # async def create_branch(
    #     self,
    #     id: Union[str, UUID],
    #     message_id: str,
    # ) -> dict:
    #     """
    #     Create a new branch starting from a specific message.
    #     """
    #     return await self.client._make_request(
    #         "POST", f"conversations/{str(id)}/messages/{message_id}/branch"
    #     )
