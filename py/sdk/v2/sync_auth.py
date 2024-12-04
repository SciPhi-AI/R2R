from __future__ import annotations  # for Python 3.10+

from typing import Optional, Union
from uuid import UUID

from typing_extensions import deprecated

from ..models import Token, User


class SyncAuthMixins:
    @deprecated("Use client.users.register() instead")
    def register(self, email: str, password: str) -> User:
        """
        Registers a new user with the given email and password.

        Args:
            email (str): The email of the user to register.
            password (str): The password of the user to register.

        Returns:
            User: The response from the server.
        """
        data = {"email": email, "password": password}
        return self._make_request("POST", "register", json=data)  # type: ignore

    @deprecated("Use client.users.verify_email() instead")
    def verify_email(self, email: str, verification_code: str) -> dict:
        """
        Verifies the email of a user with the given verification code.

        Args:
            verification_code (str): The verification code to verify the email with.

        """
        data = {"email": email, "verification_code": verification_code}
        return self._make_request(  # type: ignore
            "POST",
            "verify_email",
            json=data,
        )

    @deprecated("Use client.users.login() instead")
    def login(self, email: str, password: str) -> dict[str, Token]:
        """
        Attempts to log in a user with the given email and password.

        Args:
            email (str): The email of the user to log in.
            password (str): The password of the user to log in.

        Returns:
            dict[str, Token]: The access and refresh tokens from the server.
        """
        data = {"username": email, "password": password}
        response = self._make_request("POST", "login", data=data)  # type: ignore
        self.access_token = response["results"]["access_token"]["token"]
        self._refresh_token = response["results"]["refresh_token"]["token"]
        return response

    @deprecated("Use client.users.logout() instead")
    def logout(self) -> dict:
        """
        Logs out the currently authenticated user.

        Returns:
            dict: The response from the server.
        """
        response = self._make_request("POST", "logout")  # type: ignore
        self.access_token = None
        self._refresh_token = None
        return response

    @deprecated("Use client.users.retrieve() instead")
    def user(self) -> User:
        """
        Retrieves the user information for the currently authenticated user.

        Returns:
            User: The response from the server.
        """
        return self._make_request("GET", "user")  # type: ignore

    @deprecated("Use client.users.update() instead")
    def update_user(
        self,
        user_id: Union[str, UUID],
        email: Optional[str] = None,
        is_superuser: Optional[bool] = None,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
    ) -> User:
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
            User: The response from the server.
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
        return self._make_request("PUT", "user", json=data)  # type: ignore

    @deprecated("Use client.users.refresh_token() instead")
    def refresh_access_token(self) -> dict[str, Token]:
        """
        Refreshes the access token for the currently authenticated user.

        Returns:
            dict[str, Token]: The access and refresh tokens from the server.
        """
        response = self._make_request(  # type: ignore
            "POST", "refresh_access_token", json=self._refresh_token
        )
        self.access_token = response["results"]["access_token"]["token"]
        self._refresh_token = response["results"]["refresh_token"]["token"]
        return response

    @deprecated("Use client.users.change_password() instead")
    def change_password(
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
        return self._make_request("POST", "change_password", json=data)  # type: ignore

    @deprecated("Use client.users.request_password_reset() instead")
    def request_password_reset(self, email: str) -> dict:
        """
        Requests a password reset for the user with the given email.

        Args:
            email (str): The email of the user to request a password reset for.

        Returns:
            dict: The response from the server.
        """
        return self._make_request(  # type: ignore
            "POST", "request_password_reset", json=email
        )

    @deprecated("Use client.users.reset_password() instead")
    def confirm_password_reset(
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
        return self._make_request("POST", "reset_password", json=data)  # type: ignore

    @deprecated("Use client.users.login_with_token() instead")
    def login_with_token(
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
            self._make_request("GET", "user")  # type: ignore
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

    @deprecated("")
    def get_user_verification_code(self, user_id: Union[str, UUID]) -> dict:
        """
        Retrieves only the verification code for a specific user. Requires superuser access.

        Args:
            user_id (Union[str, UUID]): The ID of the user to get verification code for.

        Returns:
            dict: Contains verification code and its expiry date
        """
        return self._make_request(  # type: ignore
            "GET", f"user/{user_id}/verification_data"
        )

    @deprecated("")
    def send_reset_email(self, email: str) -> dict:
        """
        Generates a new verification code and sends a reset email to the user.

        Args:
            email (str): The email address of the user to send the reset email to.

        Returns:
            dict: Contains verification code and message from the server.
        """
        return self._make_request(  # type: ignore
            "POST", "send_reset_email", json=email
        )
