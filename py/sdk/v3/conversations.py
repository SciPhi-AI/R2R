import json
from inspect import getmembers, isasyncgenfunction, iscoroutinefunction
from typing import Optional, Union
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
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "desc",
    ) -> dict:
        """
        List conversations with pagination and sorting options.

        Args:
            offset (int): Number of records to skip
            limit (int): Maximum number of records to return
            sort_by (Optional[str]): Field to sort by
            sort_order (Optional[str]): Sort order (asc or desc)

        Returns:
            dict: List of conversations and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
        }
        if sort_by:
            params["sort_by"] = sort_by
        if sort_order:
            params["sort_order"] = sort_order

        return await self.client._make_request(
            "GET", "conversations", params=params
        )

    async def retrieve(
        self,
        id: Union[str, UUID],
        branch_id: Optional[str] = None,
    ) -> dict:
        """
        Get detailed information about a specific conversation.

        Args:
            id (Union[str, UUID]): Conversation ID to retrieve
            branch_id (Optional[str]): ID of the specific branch to retrieve

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
        id: Union[str, UUID],
    ) -> bool:
        """
        Delete a conversation.

        Args:
            id (Union[str, UUID]): Conversation ID to delete

        Returns:
            bool: True if deletion was successful
        """
        result = await self.client._make_request(
            "DELETE", f"conversations/{str(id)}"
        )
        return result.get("results", True)

    async def add_message(
        self,
        id: Union[str, UUID],
        content: str,
        role: str,
        parent_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Add a new message to a conversation.

        Args:
            id (Union[str, UUID]): Conversation ID
            content (str): Content of the message
            parent_id (Optional[str]): ID of the parent message
            metadata (Optional[dict]): Additional metadata for the message

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
            data["metadata"] = json.dumps(metadata)

        return await self.client._make_request(
            "POST", f"conversations/{str(id)}/messages", json=data
        )

    async def update_message(
        self,
        id: Union[str, UUID],
        message_id: str,
        content: str,
    ) -> dict:
        """
        Update an existing message in a conversation.

        Args:
            id (Union[str, UUID]): Conversation ID
            message_id (str): ID of the message to update
            content (str): New content for the message

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
        id: Union[str, UUID],
    ) -> dict:
        """
        List all branches in a conversation.

        Args:
            id (Union[str, UUID]): Conversation ID

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
