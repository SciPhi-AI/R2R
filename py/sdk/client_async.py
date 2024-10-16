import asyncio
import inspect
import json
from typing import AsyncGenerator, Generator, Optional, Any
from uuid import UUID


import httpx
import nest_asyncio
from fastapi.testclient import TestClient
from .base_client import BaseClient, handle_request_error_async

from .auth import AuthMixin
from .ingestion import IngestionMixin
from .kg import KGMixins
from .management import ManagementMixins
from .retrieval import RetrievalMixins
from .server import ServerMixins
from .models import R2RException

from .models import Token, UserResponse


class R2RAsyncClient(AuthMixin):
    def __init__(self, base_url: str = "http://localhost:7272", prefix: str = "/v2", timeout: float = 300.0):
        self.base_url = base_url
        self.prefix = prefix
        self.timeout = timeout
        self.access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=timeout)

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = self._build_url(endpoint)
        headers = kwargs.pop("headers", {})
        headers.update(self._get_auth_header())
        try:
            response = await self.client.request(
                method, url, headers=headers, **kwargs
            )
            await handle_request_error_async(response)
            return response.json() if response.content else None
        except httpx.RequestError as e:
            raise R2RException(
                status_code=500, message=f"Request failed: {str(e)}"
            ) from e

    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        return await self._make_request(method, endpoint, **kwargs)

    async def register(self, email: str, password: str) -> UserResponse:
        return await super().register(email, password)
    
    async def verify_email(self, verification_code: str) -> dict[str, Any]:
        return await super().verify_email(verification_code)

    async def login(self, email: str, password: str) -> dict[str, Token]:
        return await super().login(email, password)
    
    async def logout(self) -> dict:
        return await super().logout()
    
    async def user(self) -> UserResponse:
        return await super().user()
    
    async def update_user(self, user_id: str | UUID, email: str | None = None, is_superuser: bool | None = None, name: str | None = None, bio: str | None = None, profile_picture: str | None = None) -> UserResponse:
        return super().update_user(user_id, email, is_superuser, name, bio, profile_picture)
    
    async def refresh_access_token(self) -> dict[str, Token]:
        return super().refresh_access_token()
    
    async def change_password(self, current_password: str, new_password: str) -> dict:
        return super().change_password(current_password, new_password)
    
    async def request_password_reset(self, email: str) -> dict:
        return super().request_password_reset(email)
    
    async def confirm_password_reset(self, reset_token: str, new_password: str) -> dict:
        return super().confirm_password_reset(reset_token, new_password)
    
    async def login_with_token(self, access_token: str) -> dict[str, Token]:
        return super().login_with_token(access_token)
    
    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
