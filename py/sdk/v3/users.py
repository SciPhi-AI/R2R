from typing import Optional
from uuid import UUID

from shared.api.models.auth.responses import WrappedTokenResponse
from shared.api.models.base import (
    WrappedBooleanResponse,
    WrappedGenericMessageResponse,
)
from shared.api.models.management.responses import (
    WrappedCollectionsResponse,
    WrappedUserResponse,
    WrappedUsersResponse,
)

from ..models import Token


class UsersSDK:
    def __init__(self, client):
        self.client = client

    async def register(self, email: str, password: str) -> WrappedUserResponse:
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
            "POST",
            "users/register",
            json=data,
            version="v3",
        )

    async def delete(
        self, id: str | UUID, password: str
    ) -> WrappedBooleanResponse:
        """
        Delete a specific user.
        Users can only delete their own account unless they are superusers.

        Args:
            id (str | UUID): User ID to delete
            password (str): User's password

        Returns:
            dict: Deletion result
        """
        data = {"password": password}
        return await self.client._make_request(
            "DELETE",
            f"users/{str(id)}",
            json=data,
            version="v3",
        )

    async def verify_email(
        self, email: str, verification_code: str
    ) -> WrappedGenericMessageResponse:
        """
        Verify a user's email address.

        Args:
            email (str): User's email address
            verification_code (str): Verification code sent to the user's email

        Returns:
            dict: Verification result
        """
        data = {"email": email, "verification_code": verification_code}
        return await self.client._make_request(
            "POST",
            "users/verify-email",
            json=data,
            version="v3",
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
            "POST",
            "users/login",
            data=data,
            version="v3",
        )
        self.client.access_token = response["results"]["access_token"]["token"]
        self.client._refresh_token = response["results"]["refresh_token"][
            "token"
        ]
        return response

    # FIXME: What is going on here...
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
            await self.client._make_request(
                "GET",
                "users/me",
                version="v3",
            )
            return {
                "access_token": Token(
                    token=access_token, token_type="access_token"
                ),
            }
        except Exception:
            self.access_token = None
            self.client._refresh_token = None
            raise ValueError("Invalid token provided")

    async def logout(self) -> WrappedGenericMessageResponse:
        """Log out the current user."""
        response = await self.client._make_request(
            "POST",
            "users/logout",
            version="v3",
        )
        self.client.access_token = None
        self.client._refresh_token = None
        return response

    async def refresh_token(self) -> WrappedTokenResponse:
        """Refresh the access token using the refresh token."""
        response = await self.client._make_request(
            "POST",
            "users/refresh-token",
            json=self.client._refresh_token,
            version="v3",
        )
        self.client.access_token = response["results"]["access_token"]["token"]
        self.client._refresh_token = response["results"]["refresh_token"][
            "token"
        ]
        return response

    async def change_password(
        self, current_password: str, new_password: str
    ) -> WrappedGenericMessageResponse:
        """
        Change the user's password.

        Args:
            current_password (str): User's current password
            new_password (str): User's new password

        Returns:
            dict: Change password result
        """
        data = {
            "current_password": current_password,
            "new_password": new_password,
        }
        return await self.client._make_request(
            "POST",
            "users/change-password",
            json=data,
            version="v3",
        )

    async def request_password_reset(
        self, email: str
    ) -> WrappedGenericMessageResponse:
        """
        Request a password reset.

        Args:
            email (str): User's email address

        Returns:
            dict: Password reset request result
        """
        return await self.client._make_request(
            "POST",
            "users/request-password-reset",
            json=email,
            version="v3",
        )

    async def reset_password(
        self, reset_token: str, new_password: str
    ) -> WrappedGenericMessageResponse:
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
            "POST",
            "users/reset-password",
            json=data,
            version="v3",
        )

    async def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedUsersResponse:
        """
        List users with pagination and filtering options.

        Args:
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of users and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
        }
        if ids:
            params["ids"] = [str(user_id) for user_id in ids]  # type: ignore

        return await self.client._make_request(
            "GET",
            "users",
            params=params,
            version="v3",
        )

    async def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedUserResponse:
        """
        Get a specific user.

        Args:
            id (str | UUID): User ID to retrieve

        Returns:
            dict: Detailed user information
        """
        return await self.client._make_request(
            "GET",
            f"users/{str(id)}",
            version="v3",
        )

    async def me(
        self,
    ) -> WrappedUserResponse:
        """
        Get detailed information about the currently authenticated user.

        Returns:
            dict: Detailed user information
        """
        return await self.client._make_request(
            "GET",
            "users/me",
            version="v3",
        )

    async def update(
        self,
        id: str | UUID,
        email: Optional[str] = None,
        is_superuser: Optional[bool] = None,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
    ) -> WrappedUserResponse:
        """
        Update user information.

        Args:
            id (str | UUID): User ID to update
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
            version="v3",
        )

    async def list_collections(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedCollectionsResponse:
        """
        Get all collections associated with a specific user.

        Args:
            id (str | UUID): User ID to get collections for
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of collections and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        return await self.client._make_request(
            "GET",
            f"users/{str(id)}/collections",
            params=params,
            version="v3",
        )

    async def add_to_collection(
        self,
        id: str | UUID,
        collection_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Add a user to a collection.

        Args:
            id (str | UUID): User ID to add
            collection_id (str | UUID): Collection ID to add user to
        """
        return await self.client._make_request(
            "POST",
            f"users/{str(id)}/collections/{str(collection_id)}",
            version="v3",
        )

    async def remove_from_collection(
        self,
        id: str | UUID,
        collection_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Remove a user from a collection.

        Args:
            id (str | UUID): User ID to remove
            collection_id (str | UUID): Collection ID to remove user from

        Returns:
            bool: True if successful
        """
        return await self.client._make_request(
            "DELETE",
            f"users/{str(id)}/collections/{str(collection_id)}",
            version="v3",
        )
