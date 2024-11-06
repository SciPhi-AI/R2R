import json
from inspect import getmembers, isasyncgenfunction, iscoroutinefunction
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from ..base.base_client import sync_generator_wrapper, sync_wrapper
from ..models import Token, UserResponse


class UsersSDK:
    """
    SDK for interacting with users in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    # New authentication methods
    async def register(self, email: str, password: str) -> UserResponse:
        """
        Register a new user.

        Args:
            email (str): User's email address
            password (str): User's password

        Returns:
            UserResponse: New user information
        """
        data = {"email": email, "password": password}
        return await self.client._make_request(
            "POST", "users/register", json=data
        )

    async def verify_email(self, email: str, verification_code: str) -> dict:
        """
        Verify a user's email address.

        Args:
            email (str): User's email address
            verification_code (str): Verification code sent to email

        Returns:
            dict: Verification result
        """
        data = {"email": email, "verification_code": verification_code}
        return await self.client._make_request(
            "POST", "users/verify-email", json=data
        )

    async def login(self, email: str, password: str) -> dict[str, Token]:
        """
        Log in a user.

        Args:
            email (str): User's email address
            password (str): User's password

        Returns:
            dict[str, Token]: Access and refresh tokens
        """
        data = {"username": email, "password": password}
        response = await self.client._make_request(
            "POST", "users/login", data=data
        )
        self.client.access_token = response["results"]["access_token"]["token"]
        self.client._refresh_token = response["results"]["refresh_token"][
            "token"
        ]
        return response

    async def login_with_token(self, access_token: str) -> dict[str, Token]:
        """
        Log in using an existing access token.

        Args:
            access_token (str): Existing access token

        Returns:
            dict[str, Token]: Token information
        """
        self.client.access_token = access_token
        try:
            await self.client._make_request("GET", "users/me")
            return {
                "access_token": Token(
                    token=access_token, token_type="access_token"
                ),
            }
        except Exception:
            self.access_token = None
            self.client._refresh_token = None
            raise ValueError("Invalid token provided")

    async def logout(self) -> dict:
        """Log out the current user."""
        response = await self.client._make_request("POST", "users/logout")
        self.client.access_token = None
        self.client._refresh_token = None
        return response

    async def refresh_token(self) -> dict[str, Token]:
        """Refresh the access token using the refresh token."""
        response = await self.client._make_request(
            "POST",
            "users/refresh-token",
            json=self.client._refresh_token,
        )
        self.client.access_token = response["results"]["access_token"]["token"]
        self.client._refresh_token = response["results"]["refresh_token"][
            "token"
        ]
        return response

    async def change_password(
        self, current_password: str, new_password: str
    ) -> dict:
        """
        Change the user's password.

        Args:
            current_password (str): Current password
            new_password (str): New password

        Returns:
            dict: Change password result
        """
        data = {
            "current_password": current_password,
            "new_password": new_password,
        }
        return await self.client._make_request(
            "POST", "users/change-password", json=data
        )

    async def request_password_reset(self, email: str) -> dict:
        """
        Request a password reset.

        Args:
            email (str): User's email address

        Returns:
            dict: Password reset request result
        """
        return await self.client._make_request(
            "POST", "users/request-password-reset", json=email
        )

    async def reset_password(
        self, reset_token: str, new_password: str
    ) -> dict:
        """
        Reset password using a reset token.

        Args:
            reset_token (str): Password reset token
            new_password (str): New password

        Returns:
            dict: Password reset result
        """
        data = {"reset_token": reset_token, "new_password": new_password}
        return await self.client._make_request(
            "POST", "users/reset-password", json=data
        )

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
        params: dict = {
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
        email: Optional[str] = None,
        is_superuser: Optional[bool] = None,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
    ) -> dict:
        """
        Update user information.

        Args:
            id (Union[str, UUID]): User ID to update
            username (Optional[str]): New username
            is_superuser (Optional[bool]): Update superuser status
            metadata (Optional[Dict[str, Any]]): Update user metadata

        Returns:
            dict: Updated user information
        """
        data: dict = {}
        if email is not None:
            data["email"] = email
        if is_superuser is not None:
            data["is_superuser"] = is_superuser
        if name is not None:
            data["name"] = name
        if bio is not None:
            data["bio"] = bio
        if profile_picture is not None:
            data["profile_picture"] = profile_picture

        return await self.client._make_request(
            "POST",
            f"users/{str(id)}",
            json=data,  #  if len(data.keys()) != 1 else list(data.values())[0]
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
            "POST", f"users/{str(id)}/collections/{str(collection_id)}"
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
