import uuid
from typing import Optional

from r2r.base import Token
from r2r.base.api.models.auth.responses import UserResponse


class AuthMethods:

    @staticmethod
    async def register(client, email: str, password: str) -> UserResponse:
        data = {"email": email, "password": password}
        return await client._make_request("POST", "register", json=data)

    async def verify_email(client, verification_code: str) -> dict:
        return await client._make_request(
            "POST",
            "verify_email",
            json={"verification_code": verification_code},
        )

    async def login(client, email: str, password: str) -> dict[str, Token]:
        data = {"username": email, "password": password}
        response = await client._make_request("POST", "login", data=data)
        client.access_token = response["results"]["access_token"]["token"]
        client._refresh_token = response["results"]["refresh_token"]["token"]
        return response

    async def user(client) -> UserResponse:
        return await client._make_request("GET", "user")

    async def refresh_access_token(client) -> dict[str, Token]:
        data = {"refresh_token": client._refresh_token}
        response = await client._make_request(
            "POST", "refresh_access_token", json=data
        )
        client.access_token = response["results"]["access_token"]["token"]
        client._refresh_token = response["results"]["refresh_token"]["token"]
        return response

    async def change_password(
        client, current_password: str, new_password: str
    ) -> dict:
        data = {
            "current_password": current_password,
            "new_password": new_password,
        }
        return await client._make_request("POST", "change_password", json=data)

    async def request_password_reset(client, email: str) -> dict:
        print("email = ", email)
        return await client._make_request(
            "POST", "request_password_reset", json=email
        )

    async def confirm_password_reset(
        client, reset_token: str, new_password: str
    ) -> dict:
        data = {"reset_token": reset_token, "new_password": new_password}
        return await client._make_request("POST", "reset_password", json=data)

    async def logout(client) -> dict:
        response = await client._make_request("POST", "logout")
        client.access_token = None
        client._refresh_token = None
        return response

    async def update_user(
        client,
        email: Optional[str] = None,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
    ) -> UserResponse:
        data = {
            "email": email,
            "name": name,
            "bio": bio,
            "profile_picture": profile_picture,
        }
        data = {k: v for k, v in data.items() if v is not None}
        return await client._make_request("PUT", "user", json=data)

    async def delete_user(
        client, user_id: uuid.UUID, password: Optional[str] = None
    ) -> dict:
        data = {"user_id": str(user_id), "password": password}
        response = await client._make_request("DELETE", "user", json=data)
        client.access_token = None
        client._refresh_token = None
        return response
