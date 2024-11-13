from inspect import isasyncgenfunction, iscoroutinefunction
from typing import Optional
from uuid import UUID

from ..base.base_client import sync_generator_wrapper, sync_wrapper


class ConversationsSDK:
    """
    SDK for interacting with conversations in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(self) -> dict:
        """
        Create a new conversation.

        Returns:
            dict: Created conversation information
        """
        return await self.client._make_request("POST", "conversations")

    async def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> dict:
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
            "GET", "conversations", params=params
        )

    async def retrieve(
        self,
        id: str | UUID,
        branch_id: Optional[str] = None,
    ) -> dict:
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
            "GET", f"conversations/{str(id)}", params=params
        )

    async def delete(
        self,
        id: str | UUID,
    ) -> bool:
        """
        Delete a conversation.

        Args:
            id (Union[str, UUID]): The ID of the conversation to delete

        Returns:
            bool: True if deletion was successful
        """
        result = await self.client._make_request(
            "DELETE", f"conversations/{str(id)}"
        )
        return result.get("results", True)

    async def add_message(
        self,
        id: str | UUID,
        content: str,
        role: str,
        parent_id: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> dict:
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
        data = {
            "content": content,
            "role": role,
        }
        if parent_id:
            data["parent_id"] = parent_id
        if metadata:
            data["metadata"] = metadata

        return await self.client._make_request(
            "POST", f"conversations/{str(id)}/messages", data=data
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
        )

    async def list_branches(
        self,
        id: str | UUID,
    ) -> dict:
        """
        List all branches in a conversation.

        Args:
            id (Union[str, UUID]): The ID of the conversation to list branches for

        Returns:
            dict: List of branches in the conversation
        """
        return await self.client._make_request(
            "GET", f"conversations/{str(id)}/branches"
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


class SyncConversationSDK:
    """Synchronous wrapper for CollectionsSDK"""

    def __init__(self, async_sdk: ConversationsSDK):
        self._async_sdk = async_sdk

        # Get all attributes from the instance
        for name in dir(async_sdk):
            if not name.startswith("_"):  # Skip private methods
                attr = getattr(async_sdk, name)
                # Check if it's a method and if it's async
                if callable(attr) and (
                    iscoroutinefunction(attr) or isasyncgenfunction(attr)
                ):
                    if isasyncgenfunction(attr):
                        setattr(self, name, sync_generator_wrapper(attr))
                    else:
                        setattr(self, name, sync_wrapper(attr))
