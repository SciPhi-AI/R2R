from typing import Optional, Union
from uuid import UUID

from ..models import Token, UserResponse


class AuthMixins:
    async def register(self, email: str, password: str) -> UserResponse:
        """
        Registers a new user with the given email and password.

        Args:
            email (str): The email of the user to register.
            password (str): The password of the user to register.

        Returns:
            UserResponse: The response from the server.
        """
        data = {"email": email, "password": password}
        return await self._make_request("POST", "register", json=data)  # type: ignore

    async def verify_email(self, verification_code: str) -> dict:
        """
        Verifies the email of a user with the given verification code.

        Args:
            verification_code (str): The verification code to verify the email with.

        """
        return await self._make_request(  # type: ignore
            "POST",
            "verify_email",
            json=verification_code,
        )

    async def login(self, email: str, password: str) -> dict[str, Token]:
        """
        Attempts to log in a user with the given email and password.

        Args:
            email (str): The email of the user to log in.
            password (str): The password of the user to log in.

        Returns:
            dict[str, Token]: The access and refresh tokens from the server.
        """
        data = {"username": email, "password": password}
        response = await self._make_request("POST", "login", data=data)  # type: ignore
        self.access_token = response["results"]["access_token"]["token"]
        self._refresh_token = response["results"]["refresh_token"]["token"]
        return response

    async def logout(self) -> dict:
        """
        Logs out the currently authenticated user.

        Returns:
            dict: The response from the server.
        """
        response = await self._make_request("POST", "logout")  # type: ignore
        self.access_token = None
        self._refresh_token = None
        return response

    async def user(self) -> UserResponse:
        """
        Retrieves the user information for the currently authenticated user.

        Returns:
            UserResponse: The response from the server.
        """
        return await self._make_request("GET", "user")  # type: ignore

    async def update_user(
        self,
        user_id: Union[str, UUID],
        email: Optional[str] = None,
        is_superuser: Optional[bool] = None,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
    ) -> UserResponse:
        """
        Updates the profile information for the currently authenticated user.

        Args:
            user_id (Union[str, UUID]): The ID of the user to update.
            email (str, optional): The updated email for the user.
            is_superuser (bool, optional): The updated superuser status for the user.
            name (str, optional): The updated name for the user.
            bio (str, optional): The updated bio for the user.
            profile_picture (str, optional): The updated profile picture URL for the user.

        Returns:
            UserResponse: The response from the server.
        """
        data = {
            "user_id": user_id,
            "email": email,
            "is_superuser": is_superuser,
            "name": name,
            "bio": bio,
            "profile_picture": profile_picture,
        }
        data = {k: v for k, v in data.items() if v is not None}
        return await self._make_request("PUT", "user", json=data)  # type: ignore

    async def refresh_access_token(self) -> dict[str, Token]:
        """
        Refreshes the access token for the currently authenticated user.

        Returns:
            dict[str, Token]: The access and refresh tokens from the server.
        """
        response = await self._make_request(  # type: ignore
            "POST", "refresh_access_token", json=self._refresh_token
        )
        self.access_token = response["results"]["access_token"]["token"]
        self._refresh_token = response["results"]["refresh_token"]["token"]
        return response

    async def change_password(
        self, current_password: str, new_password: str
    ) -> dict:
        """
        Changes the password of the currently authenticated user.

        Args:
            current_password (str): The current password of the user.
            new_password (str): The new password to set for the user.

        Returns:
            dict: The response from the server.
        """
        data = {
            "current_password": current_password,
            "new_password": new_password,
        }
        return await self._make_request("POST", "change_password", json=data)  # type: ignore

    async def request_password_reset(self, email: str) -> dict:
        """
        Requests a password reset for the user with the given email.

        Args:
            email (str): The email of the user to request a password reset for.

        Returns:
            dict: The response from the server.
        """
        return await self._make_request(  # type: ignore
            "POST", "request_password_reset", json=email
        )

    async def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> dict:
        """
        Confirms a password reset for the user with the given reset token.

        Args:
            reset_token (str): The reset token to confirm the password reset with.
            new_password (str): The new password to set for the user.

        Returns:
            dict: The response from the server.
        """
        data = {"reset_token": reset_token, "new_password": new_password}
        return await self._make_request("POST", "reset_password", json=data)  # type: ignore

    async def login_with_token(
        self,
        access_token: str,
    ) -> dict[str, Token]:
        """
        Logs in a user using existing access and refresh tokens.

        Args:
            access_token (str): The existing access token.
            refresh_token (str): The existing refresh token.

        Returns:
            dict[str, Token]: The access and refresh tokens from the server.
        """
        self.access_token = access_token
        # Verify the tokens by making a request to the user endpoint
        try:
            await self._make_request("GET", "user")  # type: ignore
            return {
                "access_token": Token(
                    token=access_token, token_type="access_token"
                ),
            }
        except Exception:
            # If the request fails, clear the tokens and raise an exception
            self.access_token = None
            self._refresh_token = None
            raise ValueError("Invalid tokens provided")
