import json
from inspect import getmembers, isasyncgenfunction, iscoroutinefunction
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from ..base.base_client import sync_generator_wrapper, sync_wrapper


class UsersSDK:
    """
    SDK for interacting with users in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        username: Optional[str] = None,
        email: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_superuser: Optional[bool] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "desc",
    ) -> dict:
        """
        List users with pagination and filtering options.

        Args:
            offset (int): Number of records to skip
            limit (int): Maximum number of records to return
            username (Optional[str]): Filter by username (partial match)
            email (Optional[str]): Filter by email (partial match)
            is_active (Optional[bool]): Filter by active status
            is_superuser (Optional[bool]): Filter by superuser status
            sort_by (Optional[str]): Field to sort by (created_at, username, email)
            sort_order (Optional[str]): Sort order (asc or desc)

        Returns:
            dict: List of users and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
            "sort_order": sort_order,
        }

        if username:
            params["username"] = username
        if email:
            params["email"] = email
        if is_active is not None:
            params["is_active"] = is_active
        if is_superuser is not None:
            params["is_superuser"] = is_superuser
        if sort_by:
            params["sort_by"] = sort_by

        return await self.client._make_request("GET", "users", params=params)

    async def retrieve(
        self,
        id: Union[str, UUID],
    ) -> dict:
        """
        Get detailed information about a specific user.

        Args:
            id (Union[str, UUID]): User ID to retrieve

        Returns:
            dict: Detailed user information
        """
        return await self.client._make_request("GET", f"users/{str(id)}")

    async def update(
        self,
        id: Union[str, UUID],
        username: Optional[str] = None,
        email: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_superuser: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """
        Update user information.

        Args:
            id (Union[str, UUID]): User ID to update
            username (Optional[str]): New username
            email (Optional[str]): New email address
            is_active (Optional[bool]): Update active status
            is_superuser (Optional[bool]): Update superuser status
            metadata (Optional[Dict[str, Any]]): Update user metadata

        Returns:
            dict: Updated user information
        """
        data = {}
        if username is not None:
            data["username"] = username
        if email is not None:
            data["email"] = email
        if is_active is not None:
            data["is_active"] = is_active
        if is_superuser is not None:
            data["is_superuser"] = is_superuser
        if metadata is not None:
            data["metadata"] = metadata

        return await self.client._make_request(
            "POST", f"users/{str(id)}", json=data
        )

    async def list_collections(
        self,
        id: Union[str, UUID],
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        """
        Get all collections associated with a specific user.

        Args:
            id (Union[str, UUID]): User ID to get collections for
            offset (int): Number of records to skip
            limit (int): Maximum number of records to return

        Returns:
            dict: List of collections and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        return await self.client._make_request(
            "GET", f"users/{str(id)}/collections", params=params
        )

    async def add_to_collection(
        self,
        id: Union[str, UUID],
        collection_id: Union[str, UUID],
    ) -> None:
        """
        Add a user to a collection.

        Args:
            id (Union[str, UUID]): User ID to add
            collection_id (Union[str, UUID]): Collection ID to add user to
        """
        await self.client._make_request(
            "POST", f"users/{str(id)}/collections/{str(collection_id)}"
        )

    async def remove_from_collection(
        self,
        id: Union[str, UUID],
        collection_id: Union[str, UUID],
    ) -> bool:
        """
        Remove a user from a collection.

        Args:
            id (Union[str, UUID]): User ID to remove
            collection_id (Union[str, UUID]): Collection ID to remove user from

        Returns:
            bool: True if successful
        """
        return await self.client._make_request(
            "DELETE", f"users/{str(id)}/collections/{str(collection_id)}"
        )


class SyncUsersSDK:
    """Synchronous wrapper for UsersSDK"""

    def __init__(self, async_sdk: UsersSDK):
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
