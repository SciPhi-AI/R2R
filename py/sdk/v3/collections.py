from inspect import getmembers, isasyncgenfunction, iscoroutinefunction
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from ..base.base_client import sync_generator_wrapper, sync_wrapper


class CollectionsSDK:
    """
    SDK for interacting with collections in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> dict:
        """
        Create a new collection.

        Args:
            name (str): Name of the collection
            description (Optional[str]): Description of the collection

        Returns:
            dict: Created collection information
        """
        data = {"name": name, "description": description}
        return await self.client._make_request(
            "POST",
            "collections",
            json=data,  # {"config": data}
        )

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        name: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "desc",
    ) -> dict:
        """
        List collections with pagination and filtering options.

        Args:
            offset (int): Number of records to skip
            limit (int): Maximum number of records to return
            name (Optional[str]): Filter collections by name
            sort_by (Optional[str]): Field to sort by
            sort_order (Optional[str]): Sort order (asc or desc)

        Returns:
            dict: List of collections and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
        }
        if name:
            params["name"] = name
        if sort_by:
            params["sort_by"] = sort_by
        if sort_order:
            params["sort_order"] = sort_order

        return await self.client._make_request(
            "GET", "collections", params=params
        )

    async def retrieve(
        self,
        id: Union[str, UUID],
    ) -> dict:
        """
        Get detailed information about a specific collection.

        Args:
            id (Union[str, UUID]): Collection ID to retrieve

        Returns:
            dict: Detailed collection information
        """
        return await self.client._make_request("GET", f"collections/{str(id)}")

    async def update(
        self,
        id: Union[str, UUID],
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict:
        """
        Update collection information.

        Args:
            id (Union[str, UUID]): Collection ID to update
            name (Optional[str]): New name for the collection
            description (Optional[str]): New description for the collection

        Returns:
            dict: Updated collection information
        """
        data = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        return await self.client._make_request(
            "POST", f"collections/{str(id)}", json=data  # {"config": data}
        )

    async def delete(
        self,
        id: Union[str, UUID],
    ) -> bool:
        """
        Delete a collection.

        Args:
            id (Union[str, UUID]): Collection ID to delete

        Returns:
            bool: True if deletion was successful
        """
        result = await self.client._make_request(
            "DELETE", f"collections/{str(id)}"
        )
        return result.get("results", True)

    async def list_documents(
        self,
        id: Union[str, UUID],
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "desc",
    ) -> dict:
        """
        List all documents in a collection.

        Args:
            id (Union[str, UUID]): Collection ID
            offset (int): Number of records to skip
            limit (int): Maximum number of records to return
            sort_by (Optional[str]): Field to sort by
            sort_order (Optional[str]): Sort order (asc or desc)

        Returns:
            dict: List of documents and pagination information
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
            "GET", f"collections/{str(id)}/documents", params=params
        )

    async def add_document(
        self,
        id: Union[str, UUID],
        document_id: Union[str, UUID],
    ) -> dict:
        """
        Add a document to a collection.

        Args:
            id (Union[str, UUID]): Collection ID
            document_id (Union[str, UUID]): Document ID to add

        Returns:
            dict: Result of the operation
        """
        return await self.client._make_request(
            "POST", f"collections/{str(id)}/documents/{str(document_id)}"
        )

    async def remove_document(
        self,
        id: Union[str, UUID],
        document_id: Union[str, UUID],
    ) -> bool:
        """
        Remove a document from a collection.

        Args:
            id (Union[str, UUID]): Collection ID
            document_id (Union[str, UUID]): Document ID to remove

        Returns:
            bool: True if removal was successful
        """
        result = await self.client._make_request(
            "DELETE", f"collections/{str(id)}/documents/{str(document_id)}"
        )
        return result.get("results", True)

    async def list_users(
        self,
        id: Union[str, UUID],
        offset: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "desc",
    ) -> dict:
        """
        List all users in a collection.

        Args:
            id (Union[str, UUID]): Collection ID
            offset (int): Number of records to skip
            limit (int): Maximum number of records to return
            sort_by (Optional[str]): Field to sort by
            sort_order (Optional[str]): Sort order (asc or desc)

        Returns:
            dict: List of users and pagination information
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
            "GET", f"collections/{str(id)}/users", params=params
        )

    async def add_user(
        self,
        id: Union[str, UUID],
        user_id: Union[str, UUID],
    ) -> dict:
        """
        Add a user to a collection.

        Args:
            id (Union[str, UUID]): Collection ID
            user_id (Union[str, UUID]): User ID to add

        Returns:
            dict: Result of the operation
        """
        return await self.client._make_request(
            "POST", f"collections/{str(id)}/users/{str(user_id)}"
        )

    async def remove_user(
        self,
        id: Union[str, UUID],
        user_id: Union[str, UUID],
    ) -> bool:
        """
        Remove a user from a collection.

        Args:
            id (Union[str, UUID]): Collection ID
            user_id (Union[str, UUID]): User ID to remove

        Returns:
            bool: True if removal was successful
        """
        result = await self.client._make_request(
            "DELETE", f"collections/{str(id)}/users/{str(user_id)}"
        )
        return result.get("results", True)


class SyncCollectionsSDK:
    """Synchronous wrapper for CollectionsSDK"""

    def __init__(self, async_sdk: CollectionsSDK):
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