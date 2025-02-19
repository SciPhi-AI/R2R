from builtins import list as _list
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from shared.api.models import (
    WrappedBooleanResponse,
    WrappedConversationMessagesResponse,
    WrappedConversationResponse,
    WrappedConversationsResponse,
    WrappedMessageResponse,
)


class ConversationsSDK:
    def __init__(self, client):
        self.client = client

    def create(
        self,
        name: Optional[str] = None,
    ) -> WrappedConversationResponse:
        """Create a new conversation.

        Returns:
            WrappedConversationResponse
        """
        data: dict[str, Any] = {}
        if name:
            data["name"] = name

        response_dict = self.client._make_request(
            "POST",
            "conversations",
            data=data,
            version="v3",
        )

        return WrappedConversationResponse(**response_dict)

    def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedConversationsResponse:
        """List conversations with pagination and sorting options.

        Args:
            ids (Optional[list[str | UUID]]): List of conversation IDs to retrieve
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedConversationsResponse
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }
        if ids:
            params["ids"] = ids

        response_dict = self.client._make_request(
            "GET",
            "conversations",
            params=params,
            version="v3",
        )

        return WrappedConversationsResponse(**response_dict)

    def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedConversationMessagesResponse:
        """Get detailed information about a specific conversation.

        Args:
            id (str | UUID): The ID of the conversation to retrieve

        Returns:
            WrappedConversationMessagesResponse
        """
        response_dict = self.client._make_request(
            "GET",
            f"conversations/{str(id)}",
            version="v3",
        )

        return WrappedConversationMessagesResponse(**response_dict)

    def update(
        self,
        id: str | UUID,
        name: str,
    ) -> WrappedConversationResponse:
        """Update an existing conversation.

        Args:
            id (str | UUID): The ID of the conversation to update
            name (str): The new name of the conversation

        Returns:
            WrappedConversationResponse
        """
        data: dict[str, Any] = {
            "name": name,
        }

        response_dict = self.client._make_request(
            "POST",
            f"conversations/{str(id)}",
            json=data,
            version="v3",
        )

        return WrappedConversationResponse(**response_dict)

    def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Delete a conversation.

        Args:
            id (str | UUID): The ID of the conversation to delete

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "DELETE",
            f"conversations/{str(id)}",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    def add_message(
        self,
        id: str | UUID,
        content: str,
        role: str,
        metadata: Optional[dict] = None,
        parent_id: Optional[str] = None,
    ) -> WrappedMessageResponse:
        """Add a new message to a conversation.

        Args:
            id (str | UUID): The ID of the conversation to add the message to
            content (str): The content of the message
            role (str): The role of the message (e.g., "user" or "assistant")
            parent_id (Optional[str]): The ID of the parent message
            metadata (Optional[dict]): Additional metadata to attach to the message

        Returns:
            WrappedMessageResponse
        """
        data: dict[str, Any] = {
            "content": content,
            "role": role,
        }
        if parent_id:
            data["parent_id"] = parent_id
        if metadata:
            data["metadata"] = metadata

        response_dict = self.client._make_request(
            "POST",
            f"conversations/{str(id)}/messages",
            json=data,
            version="v3",
        )

        return WrappedMessageResponse(**response_dict)

    def update_message(
        self,
        id: str | UUID,
        message_id: str,
        content: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> WrappedMessageResponse:
        """Update an existing message in a conversation.

        Args:
            id (str | UUID): The ID of the conversation containing the message
            message_id (str): The ID of the message to update
            content (str): The new content of the message
            metadata (dict): Additional metadata to attach to the message

        Returns:
            WrappedMessageResponse
        """
        data: dict[str, Any] = {"content": content}
        if metadata:
            data["metadata"] = metadata
        response_dict = self.client._make_request(
            "POST",
            f"conversations/{str(id)}/messages/{message_id}",
            json=data,
            version="v3",
        )

        return WrappedMessageResponse(**response_dict)

    def export(
        self,
        output_path: str | Path,
        columns: Optional[_list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> None:
        """Export conversations to a CSV file, streaming the results directly
        to disk.

        Args:
            output_path (str | Path): Local path where the CSV file should be saved
            columns (Optional[list[str]]): Specific columns to export. If None, exports default columns
            filters (Optional[dict]): Optional filters to apply when selecting conversations
            include_header (bool): Whether to include column headers in the CSV (default: True)

        Returns:
            None
        """
        # Convert path to string if it's a Path object
        output_path = (
            str(output_path) if isinstance(output_path, Path) else output_path
        )

        # Prepare request data
        data: dict[str, Any] = {"include_header": include_header}
        if columns:
            data["columns"] = columns
        if filters:
            data["filters"] = filters

        # Stream response directly to file
        with open(output_path, "wb") as f:
            with self.client.client.post(
                f"{self.client.base_url}/v3/conversations/export",
                json=data,
                headers={
                    "Accept": "text/csv",
                    **self.client._get_auth_header(),
                },
            ) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Export failed with status {response.status}",
                        response,
                    )

                for chunk in response.content.iter_chunks():
                    if chunk:
                        f.write(chunk[0])

    def export_messages(
        self,
        output_path: str | Path,
        columns: Optional[_list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> None:
        """Export messages to a CSV file, streaming the results directly to
        disk.

        Args:
            output_path (str | Path): Local path where the CSV file should be saved
            columns (Optional[list[str]]): Specific columns to export. If None, exports default columns
            filters (Optional[dict]): Optional filters to apply when selecting messages
            include_header (bool): Whether to include column headers in the CSV (default: True)

        Returns:
            None
        """
        # Convert path to string if it's a Path object
        output_path = (
            str(output_path) if isinstance(output_path, Path) else output_path
        )

        # Prepare request data
        data: dict[str, Any] = {"include_header": include_header}
        if columns:
            data["columns"] = columns
        if filters:
            data["filters"] = filters

        # Stream response directly to file
        with open(output_path, "wb") as f:
            with self.client.session.post(
                f"{self.client.base_url}/v3/conversations/export_messages",
                json=data,
                headers={
                    "Accept": "text/csv",
                    **self.client._get_auth_header(),
                },
            ) as response:
                if response.status_code != 200:
                    raise ValueError(
                        f"Export failed with status {response.status_code}",
                        response,
                    )

                for chunk in response.iter_bytes():
                    if chunk:
                        f.write(chunk[0])
