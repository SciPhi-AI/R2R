import asyncio
import json
import os
import uuid
from contextlib import ExitStack
from typing import AsyncGenerator, Generator, Optional, Union

import fire
import httpx
import nest_asyncio
import requests
from fastapi.testclient import TestClient

from r2r.base import (
    ChunkingConfig,
    GenerationConfig,
    KGSearchSettings,
    R2RException,
    VectorDBFilterValue,
    VectorSearchSettings,
)

nest_asyncio.apply()


# The empty args become necessary after a recent modification to `base_endpoint`
# TODO - Remove the explicitly empty args
EMPTY_ARGS = {"args": "", "kwargs": "{}"}


def handle_request_error(response):
    if response.status_code < 400:
        return

    try:
        error_content = response.json()
        if isinstance(error_content, dict) and "detail" in error_content:
            detail = error_content["detail"]
            if isinstance(detail, dict):
                message = detail.get("message", str(response.text))
            else:
                message = str(detail)
        else:
            message = str(error_content)
    except json.JSONDecodeError:
        message = response.text

    raise R2RException(
        status_code=response.status_code,
        message=message,
    )


async def handle_request_error_async(response):
    if response.status_code < 400:
        return

    try:
        if response.headers.get("content-type") == "application/json":
            error_content = await response.json()
        else:
            error_content = await response.text()

        if isinstance(error_content, dict) and "detail" in error_content:
            detail = error_content["detail"]
            if isinstance(detail, dict):
                message = detail.get("message", str(error_content))
            else:
                message = str(detail)
        else:
            message = str(error_content)
    except Exception:
        message = await response.text()

    raise R2RException(
        status_code=response.status_code,
        message=message,
    )


class R2RClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        prefix: str = "/v1",
        custom_client=None,
        timeout: float = 60.0,
    ):
        self.base_url = base_url
        self.prefix = prefix
        self.access_token = None
        self._refresh_token = None
        self.client = custom_client or requests
        self.timeout = timeout

    def _make_request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}{self.prefix}/{endpoint}"
        headers = kwargs.pop("headers", {})
        if self.access_token and endpoint not in [
            "register",
            "login",
            "verify_email",
        ]:
            headers.update(self._get_auth_header())
        params = kwargs.pop("params", {})
        params = {
            **params,
            **EMPTY_ARGS,
        }  # TODO - Why do we need the empty args?
        if isinstance(self.client, TestClient):
            response = getattr(self.client, method.lower())(
                url, headers=headers, **kwargs, params=params
            )
        else:
            response = self.client.request(
                method, url, headers=headers, **kwargs, params=params
            )

        handle_request_error(response)
        return response.json()

    def _get_auth_header(self) -> dict:
        if not self.access_token:
            {}  # Return empty dict if no access token
        return {"Authorization": f"Bearer {self.access_token}"}

    def register(self, email: str, password: str) -> dict:
        user = {"email": email, "password": password}
        return self._make_request("POST", "register", json=user)

    def verify_email(self, verification_code: str) -> dict:
        return self._make_request("POST", f"verify_email/{verification_code}")

    def login(self, email: str, password: str) -> dict:
        form_data = {"username": email, "password": password}
        response = self._make_request("POST", "login", data=form_data)
        self.access_token = response["results"]["access_token"]["token"]
        self._refresh_token = response["results"]["refresh_token"]["token"]
        return response

    def user(self) -> dict:
        return self._make_request("GET", "user")

    def refresh_access_token(self) -> dict:
        if not self._refresh_token:
            raise ValueError("No refresh token available. Please login again.")
        response = self._make_request(
            "POST",
            "refresh_access_token",
            json={"refresh_token": self._refresh_token},
        )
        self.access_token = response["results"]["access_token"]["token"]
        self._refresh_token = response["results"]["refresh_token"][
            "token"
        ]  # Update the refresh token
        return response

    def _ensure_authenticated(self):
        pass
        # if not self.access_token:
        #     raise ValueError("Not authenticated. Please login first.")

    def health(self) -> dict:
        return self._make_request("GET", "health")

    def server_stats(self) -> dict:
        self._ensure_authenticated()
        return self._make_request("GET", "server_stats")

    def update_prompt(
        self,
        name: str = "default_system",
        template: Optional[str] = None,
        input_types: Optional[dict] = None,
    ) -> dict:
        self._ensure_authenticated()
        data = {"name": name, "template": template, "input_types": input_types}
        return self._make_request(
            "POST",
            "update_prompt",
            json={k: v for k, v in data.items() if v is not None},
        )

    def ingest_files(
        self,
        file_paths: list[str],
        metadatas: Optional[list[dict]] = None,
        document_ids: Optional[list[Union[uuid.UUID, str]]] = None,
        versions: Optional[list[str]] = None,
        chunking_config_override: Optional[Union[dict, ChunkingConfig]] = None,
    ) -> dict:
        self._ensure_authenticated()

        if isinstance(chunking_config_override, ChunkingConfig):
            chunking_config_override = chunking_config_override.model_dump()

        all_file_paths = []
        for path in file_paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    all_file_paths.extend(
                        os.path.join(root, file) for file in files
                    )
            else:
                all_file_paths.append(path)

        with ExitStack() as stack:
            files = [
                (
                    "files",
                    (
                        os.path.basename(file),
                        stack.enter_context(open(file, "rb")),
                        "application/octet-stream",
                    ),
                )
                for file in all_file_paths
            ]

            data = {
                "metadatas": json.dumps(metadatas) if metadatas else None,
                "document_ids": (
                    json.dumps([str(doc_id) for doc_id in document_ids])
                    if document_ids
                    else None
                ),
                "versions": json.dumps(versions) if versions else None,
                "chunking_config_override": (
                    json.dumps(chunking_config_override)
                    if chunking_config_override
                    else None
                ),
            }

            return self._make_request(
                "POST", "ingest_files", data=data, files=files
            )

    def update_files(
        self,
        file_paths: list[str],
        document_ids: list[str],
        metadatas: Optional[list[dict]] = None,
        chunking_config_override: Optional[Union[dict, ChunkingConfig]] = None,
    ) -> dict:
        self._ensure_authenticated()

        if isinstance(chunking_config_override, ChunkingConfig):
            chunking_config_override = chunking_config_override.model_dump()

        with ExitStack() as stack:
            files = [
                (
                    "files",
                    (
                        os.path.basename(path),
                        stack.enter_context(open(path, "rb")),
                        "application/octet-stream",
                    ),
                )
                for path in file_paths
            ]

            data = {
                "document_ids": json.dumps(
                    [str(doc_id) for doc_id in document_ids]
                ),
                "metadatas": json.dumps(metadatas) if metadatas else None,
                "chunking_config_override": (
                    json.dumps(chunking_config_override)
                    if chunking_config_override
                    else None
                ),
            }

            return self._make_request(
                "POST", "update_files", data=data, files=files
            )

    def search(
        self,
        query: str,
        vector_search_settings: Optional[
            Union[dict, VectorSearchSettings]
        ] = None,
        kg_search_settings: Optional[Union[dict, KGSearchSettings]] = None,
    ) -> dict:
        self._ensure_authenticated()

        # Convert Pydantic models to dictionaries if necessary
        if isinstance(vector_search_settings, VectorSearchSettings):
            vector_search_settings = vector_search_settings.model_dump()
        if isinstance(kg_search_settings, KGSearchSettings):
            kg_search_settings = kg_search_settings.model_dump()

        # Prepare the JSON payload
        json_data = {
            "query": query,
            "vector_search_settings": vector_search_settings,
            "kg_search_settings": kg_search_settings,
        }

        # Remove None values
        json_data = {k: v for k, v in json_data.items() if v is not None}
        return self._make_request("POST", "search", json=json_data)

    def rag(
        self,
        query: str,
        vector_search_settings: Optional[
            Union[dict, VectorSearchSettings]
        ] = None,
        kg_search_settings: Optional[Union[dict, KGSearchSettings]] = None,
        rag_generation_config: Optional[Union[dict, GenerationConfig]] = None,
        task_prompt_override: Optional[str] = None,
    ) -> dict:
        self._ensure_authenticated()

        # Convert Pydantic models to dictionaries if necessary
        if isinstance(vector_search_settings, VectorSearchSettings):
            vector_search_settings = vector_search_settings.model_dump()
        if isinstance(kg_search_settings, KGSearchSettings):
            kg_search_settings = kg_search_settings.model_dump()
        if isinstance(rag_generation_config, GenerationConfig):
            rag_generation_config = rag_generation_config.model_dump()

        # Prepare the JSON payload
        json_data = {
            "query": query,
            "vector_search_settings": vector_search_settings,
            "kg_search_settings": kg_search_settings,
            "rag_generation_config": rag_generation_config,
            "task_prompt_override": task_prompt_override,
        }

        # Remove None values
        json_data = {k: v for k, v in json_data.items() if v is not None}

        if rag_generation_config and rag_generation_config.get(
            "stream", False
        ):
            return self._stream_rag_sync(json_data)
        else:
            return self._make_request("POST", "rag", json=json_data)

    async def _stream_rag(self, rag_data: dict) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}{self.prefix}/rag"
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                json=rag_data,
                timeout=self.timeout,
            ) as response:
                await handle_request_error_async(response)
                async for chunk in response.aiter_text():
                    yield chunk

    def _stream_rag_sync(self, rag_data: dict) -> Generator[str, None, None]:
        async def run_async_generator():
            async for chunk in self._stream_rag(rag_data):
                yield chunk

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async_gen = run_async_generator()

        try:
            while True:
                yield loop.run_until_complete(async_gen.__anext__())
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    def agent(
        self,
        messages: list[dict],
        vector_search_settings: Optional[
            Union[dict, VectorSearchSettings]
        ] = None,
        kg_search_settings: Optional[Union[dict, KGSearchSettings]] = None,
        rag_generation_config: Optional[Union[dict, GenerationConfig]] = None,
        task_prompt_override: Optional[str] = None,
        include_title_if_available: Optional[bool] = True,
    ) -> dict:
        self._ensure_authenticated()

        # Convert Pydantic models to dictionaries if necessary
        if isinstance(vector_search_settings, VectorSearchSettings):
            vector_search_settings = vector_search_settings.model_dump()
        if isinstance(kg_search_settings, KGSearchSettings):
            kg_search_settings = kg_search_settings.model_dump()
        if isinstance(rag_generation_config, GenerationConfig):
            rag_generation_config = rag_generation_config.model_dump()

        # Prepare the JSON payload
        json_data = {
            "messages": messages,
            "vector_search_settings": vector_search_settings,
            "kg_search_settings": kg_search_settings,
            "rag_generation_config": rag_generation_config,
            "task_prompt_override": task_prompt_override,
            "include_title_if_available": include_title_if_available,
        }

        # Remove None values
        json_data = {k: v for k, v in json_data.items() if v is not None}

        if rag_generation_config and rag_generation_config.get(
            "stream", False
        ):
            return self._stream_agent_sync(json_data)
        else:
            return self._make_request("POST", "agent", json=json_data)

    async def _stream_agent(
        self, agent_data: dict
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}{self.prefix}/agent"
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                json=agent_data,
                timeout=self.timeout,
            ) as response:
                await handle_request_error(response)
                async for chunk in response.aiter_text():
                    yield chunk

    def _stream_agent_sync(
        self, agent_data: dict
    ) -> Generator[str, None, None]:
        async def run_async_generator():
            async for chunk in self._stream_agent(agent_data):
                yield chunk

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async_gen = run_async_generator()

        try:
            while True:
                yield loop.run_until_complete(async_gen.__anext__())
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    def delete(
        self, filters: Optional[dict[str, VectorDBFilterValue]] = None
    ) -> dict:
        self._ensure_authenticated()

        params = {"filters": json.dumps(filters)} if filters else {}

        return self._make_request(
            "DELETE",
            "delete",
            params=params,
        )

    def logs(
        self,
        run_type_filter: Optional[str] = None,
        max_runs: int = 100,
    ) -> dict:
        self._ensure_authenticated()

        params = {
            "run_type_filter": run_type_filter,
            "max_runs": max_runs,
        }
        return self._make_request("GET", "logs", params=params)

    def app_settings(self) -> dict:
        self._ensure_authenticated()

        return self._make_request("GET", "app_settings")

    def score_completion(
        self,
        message_id: uuid.UUID,
        score: float,
    ) -> dict:
        self._ensure_authenticated()
        data = {
            "message_id": str(message_id),
            "score": score,
        }
        return self._make_request(
            "POST",
            "score_completion",
            json=data,
        )

    def analytics(
        self,
        filter_criteria: Optional[Union[dict, str]] = None,
        analysis_types: Optional[Union[dict, str]] = None,
    ) -> dict:
        self._ensure_authenticated()

        params = {}
        if filter_criteria:
            if isinstance(filter_criteria, dict):
                params["filter_criteria"] = json.dumps(filter_criteria)
            else:
                params["filter_criteria"] = filter_criteria
        if analysis_types:
            if isinstance(analysis_types, dict):
                params["analysis_types"] = json.dumps(analysis_types)
            else:
                params["analysis_types"] = analysis_types

        return self._make_request("GET", "analytics", params=params)

    def users_overview(
        self, user_ids: Optional[list[uuid.UUID]] = None
    ) -> dict:
        self._ensure_authenticated()

        return self._make_request(
            "GET", "users_overview", params={"user_ids": user_ids}
        )

    def documents_overview(
        self,
        document_ids: Optional[list[str]] = None,
    ) -> dict:
        self._ensure_authenticated()

        return self._make_request(
            "GET",
            "documents_overview",
            params={
                "document_ids": (
                    [str(ele) for ele in document_ids]
                    if document_ids
                    else None
                )
            },
        )

    def document_chunks(self, document_id: str) -> dict:
        self._ensure_authenticated()

        return self._make_request(
            "GET", "document_chunks", params={"document_id": document_id}
        )

    def inspect_knowledge_graph(self, limit: int = 100) -> str:
        self._ensure_authenticated()

        return self._make_request(
            "GET",
            "inspect_knowledge_graph",
            params={"limit": limit},
        )

    def change_password(
        self, current_password: str, new_password: str
    ) -> dict:
        self._ensure_authenticated()
        return self._make_request(
            "POST",
            "change_password",
            json={
                "current_password": current_password,
                "new_password": new_password,
            },
        )

    def request_password_reset(self, email: str) -> dict:
        return self._make_request(
            "POST",
            "request_password_reset",
            data=email,
            headers={"Content-Type": "text/plain"},
        )

    def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> dict:
        return self._make_request(
            "POST",
            f"reset_password/{reset_token}",
            data=new_password,
            headers={"Content-Type": "text/plain"},
        )

    def logout(self) -> dict:
        self._ensure_authenticated()
        response = self._make_request("POST", "logout")
        self.access_token = None
        self._refresh_token = None
        return response

    def update_user(
        self,
        email: Optional[str] = None,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
    ) -> dict:
        user_data = {
            "email": email,
            "name": name,
            "bio": bio,
            "profile_picture": profile_picture,
        }
        user_data = {k: v for k, v in user_data.items() if v is not None}
        return self._make_request("PUT", "user", json=user_data)

    def delete_user(self, user_id: str, password: str) -> dict:
        self._ensure_authenticated()
        response = self._make_request(
            "DELETE", "user", json={"user_id": user_id, "password": password}
        )
        self.access_token = None
        self._refresh_token = None
        return response

    def get_group(self, group_id: uuid.UUID) -> dict:
        self._ensure_authenticated()
        return self._make_request("GET", f"get_group/{group_id}")

    def create_group(self, name: str, description: str = "") -> dict:
        self._ensure_authenticated()
        data = {"name": name, "description": description}
        return self._make_request("POST", "create_group", json=data)

    def update_group(
        self,
        group_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict:
        self._ensure_authenticated()
        data = {
            "name": name,
            "description": description,
            "group_id": str(group_id),
        }
        data = {k: v for k, v in data.items() if v is not None}
        return self._make_request("PUT", f"update_group", json=data)

    def add_user_to_group(
        self, user_id: uuid.UUID, group_id: uuid.UUID
    ) -> dict:
        self._ensure_authenticated()
        data = {"user_id": str(user_id), "group_id": str(group_id)}
        return self._make_request("POST", "add_user_to_group", json=data)

    def remove_user_from_group(
        self, user_id: uuid.UUID, group_id: uuid.UUID
    ) -> dict:
        self._ensure_authenticated()
        data = {"user_id": str(user_id), "group_id": str(group_id)}
        return self._make_request("POST", "remove_user_from_group", json=data)

    def delete_group(self, group_id: uuid.UUID) -> dict:
        self._ensure_authenticated()
        return self._make_request("DELETE", f"delete_group/{group_id}")

    def list_groups(self, offset: int = 0, limit: int = 100) -> dict:
        self._ensure_authenticated()
        return self._make_request(
            "GET", f"list_groups?offset={offset}&limit={limit}"
        )

    def get_users_in_group(
        self, group_id: uuid.UUID, offset: int = 0, limit: int = 100
    ) -> dict:
        self._ensure_authenticated()
        return self._make_request(
            "GET",
            f"get_users_in_group/{group_id}/{offset}/{limit}",
        )

    def get_groups_for_user(self, user_id: uuid.UUID) -> dict:
        return self._make_request("GET", f"get_groups_for_user/{user_id}")

    def groups_overview(
        self, group_ids: Optional[list[uuid.UUID]] = None
    ) -> dict:
        self._ensure_authenticated()
        params = {}
        if group_ids:
            params["group_ids"] = [str(gid) for gid in group_ids]
        return self._make_request("GET", "groups_overview", params=params)


if __name__ == "__main__":
    client = R2RClient(base_url="http://localhost:8000")
    fire.Fire(client)
