import asyncio
import json
import os
import uuid
from contextlib import ExitStack
from typing import Any, AsyncGenerator, Dict, Generator, Optional, Union

import fire
import httpx
import nest_asyncio
import requests
from fastapi.testclient import TestClient

from r2r.base import (
    AnalysisTypes,
    FilterCriteria,
    GenerationConfig,
    KGSearchSettings,
    R2RException,
    UserCreate,
    VectorSearchSettings,
)

from .routes.ingestion.requests import (
    R2RIngestFilesRequest,
    R2RUpdateFilesRequest,
)
from .routes.management.requests import (
    R2RAnalyticsRequest,
    R2RDeleteRequest,
    R2RDocumentChunksRequest,
    R2RDocumentsOverviewRequest,
    R2RLogsRequest,
    R2RPrintRelationshipsRequest,
    R2RUpdatePromptRequest,
    R2RUsersOverviewRequest,
)
from .routes.retrieval.requests import (
    R2RRAGAgentRequest,
    R2RRAGRequest,
    R2RSearchRequest,
)

nest_asyncio.apply()


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
        if isinstance(self.client, TestClient):
            response = getattr(self.client, method.lower())(
                url, headers=headers, **kwargs
            )
        else:
            response = self.client.request(
                method, url, headers=headers, **kwargs
            )

        handle_request_error(response)
        return response.json()

    def _get_auth_header(self) -> dict:
        if not self.access_token:
            {}  # Return empty dict if no access token
        return {"Authorization": f"Bearer {self.access_token}"}

    def register(self, email: str, password: str) -> dict:
        user = UserCreate(email=email, password=password)
        return self._make_request("POST", "register", json=user.dict())

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

    def update_prompt(
        self,
        name: str = "default_system",
        template: Optional[str] = None,
        input_types: Optional[dict] = None,
    ) -> dict:
        self._ensure_authenticated()
        request = R2RUpdatePromptRequest(
            name=name, template=template, input_types=input_types
        )
        return self._make_request(
            "POST", "update_prompt", json=json.loads(request.model_dump_json())
        )

    def ingest_files(
        self,
        file_paths: list[str],
        metadatas: Optional[list[dict]] = None,
        document_ids: Optional[list[Union[uuid.UUID, str]]] = None,
        versions: Optional[list[str]] = None,
    ) -> dict:
        self._ensure_authenticated()

        all_file_paths = []

        for path in file_paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    all_file_paths.extend(
                        os.path.join(root, file) for file in files
                    )
            else:
                all_file_paths.append(path)

        files_to_upload = [
            (
                "files",
                (
                    os.path.basename(file),
                    open(file, "rb"),
                    "application/octet-stream",
                ),
            )
            for file in all_file_paths
        ]
        request = R2RIngestFilesRequest(
            metadatas=metadatas,
            document_ids=(
                [str(ele) for ele in document_ids] if document_ids else None
            ),
            versions=versions,
        )
        try:
            return self._make_request(
                "POST",
                "ingest_files",
                data={
                    k: json.dumps(v)
                    for k, v in json.loads(request.model_dump_json()).items()
                },
                files=files_to_upload,
            )
        finally:
            for _, file_tuple in files_to_upload:
                file_tuple[1].close()

    def update_files(
        self,
        file_paths: list[str],
        document_ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> dict:
        self._ensure_authenticated()

        request = R2RUpdateFilesRequest(
            metadatas=metadatas,
            document_ids=document_ids,
        )
        with ExitStack() as stack:
            return self._make_request(
                "POST",
                "update_files",
                data={
                    k: json.dumps(v)
                    for k, v in json.loads(request.model_dump_json()).items()
                },
                files=[
                    (
                        "files",
                        (
                            path.split("/")[-1],
                            stack.enter_context(open(path, "rb")),
                            "application/octet-stream",
                        ),
                    )
                    for path in file_paths
                ],
            )

    def search(
        self,
        query: str,
        use_vector_search: bool = True,
        search_filters: Optional[dict[str, Any]] = {},
        search_limit: int = 10,
        do_hybrid_search: bool = False,
        use_kg_search: bool = False,
        entity_types: list = [],
        relationships: list = [],
        kg_search_generation_config: Optional[dict] = None,
    ) -> dict:
        self._ensure_authenticated()

        request = R2RSearchRequest(
            query=query,
            vector_search_settings={
                "use_vector_search": use_vector_search,
                "search_filters": search_filters or {},
                "search_limit": search_limit,
                "do_hybrid_search": do_hybrid_search,
            },
            kg_search_settings={
                "use_kg_search": use_kg_search,
                "entity_types": entity_types,
                "relationships": relationships,
                "kg_search_generation_config": kg_search_generation_config,
            },
        )
        return self._make_request(
            "POST", "search", json=json.loads(request.model_dump_json())
        )

    def rag(
        self,
        query: str,
        use_vector_search: bool = True,
        search_filters: Optional[dict[str, Any]] = {},
        search_limit: int = 10,
        do_hybrid_search: bool = False,
        use_kg_search: bool = False,
        kg_search_generation_config: Optional[dict] = None,
        rag_generation_config: Optional[Union[dict, GenerationConfig]] = None,
        kg_search_settings: Optional[Union[dict, KGSearchSettings]] = None,
        vector_search_settings: Optional[
            Union[dict, VectorSearchSettings]
        ] = None,
        task_prompt_override: Optional[str] = None,
    ) -> dict:
        self._ensure_authenticated()

        if isinstance(rag_generation_config, GenerationConfig):
            rag_generation_config = json.loads(
                rag_generation_config.model_dump_json()
            )
        if isinstance(kg_search_settings, KGSearchSettings):
            kg_search_settings = json.loads(
                kg_search_settings.model_dump_json()
            )
        if isinstance(vector_search_settings, VectorSearchSettings):
            vector_search_settings = json.loads(
                vector_search_settings.model_dump_json()
            )

        request = R2RRAGRequest(
            query=query,
            vector_search_settings=vector_search_settings
            or {
                "use_vector_search": use_vector_search,
                "search_filters": search_filters or {},
                "search_limit": search_limit,
                "do_hybrid_search": do_hybrid_search,
            },
            kg_search_settings=kg_search_settings
            or {
                "use_kg_search": use_kg_search,
                "kg_search_generation_config": kg_search_generation_config,
            },
            rag_generation_config=rag_generation_config,
            task_prompt_override=task_prompt_override,
        )

        if rag_generation_config and rag_generation_config.get(
            "stream", False
        ):
            return self._stream_rag_sync(request)
        else:
            return self._make_request(
                "POST", "rag", json=json.loads(request.model_dump_json())
            )

    async def _stream_rag(
        self, rag_request: R2RRAGRequest
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}{self.prefix}/rag"
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                json=json.loads(
                    rag_request.model_dump_json(),
                ),
                timeout=self.timeout,
            ) as response:
                handle_request_error(response)
                async for chunk in response.aiter_text():
                    yield chunk

    def _stream_rag_sync(
        self, rag_request: R2RRAGRequest
    ) -> Generator[str, None, None]:
        async def run_async_generator():
            async for chunk in self._stream_rag(rag_request):
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
        self, keys: list[str], values: list[Union[bool, int, str]]
    ) -> dict:
        self._ensure_authenticated()

        request = R2RDeleteRequest(keys=keys, values=values)
        return self._make_request(
            "DELETE", "delete", json=json.loads(request.model_dump_json())
        )

    def logs(self, log_type_filter: Optional[str] = None) -> dict:
        self._ensure_authenticated()

        request = R2RLogsRequest(log_type_filter=log_type_filter)
        return self._make_request(
            "GET", "logs", json=json.loads(request.model_dump_json())
        )

    def app_settings(self) -> dict:
        self._ensure_authenticated()

        return self._make_request("GET", "app_settings")

    def analytics(
        self,
        filter_criteria: Optional[Dict[str, Any]],
        analysis_types: Optional[Dict[str, Any]],
    ) -> dict:
        self._ensure_authenticated()

        request = R2RAnalyticsRequest(
            filter_criteria=FilterCriteria(filters=filter_criteria),
            analysis_types=AnalysisTypes(analysis_types=analysis_types),
        )
        return self._make_request(
            "GET", "analytics", json=request.model_dump(exclude_none=True)
        )

    def users_overview(
        self, user_ids: Optional[list[uuid.UUID]] = None
    ) -> dict:
        self._ensure_authenticated()

        request = R2RUsersOverviewRequest(user_ids=user_ids)
        return self._make_request(
            "GET", "users_overview", json=json.loads(request.model_dump_json())
        )

    def documents_overview(
        self,
        document_ids: Optional[list[str]] = None,
        user_ids: Optional[list[str]] = None,
    ) -> dict:
        self._ensure_authenticated()

        request = R2RDocumentsOverviewRequest(
            document_ids=(
                [uuid.UUID(did) for did in document_ids]
                if document_ids
                else None
            ),
            user_ids=(
                [uuid.UUID(uid) for uid in user_ids] if user_ids else None
            ),
        )
        return self._make_request(
            "GET",
            "documents_overview",
            json=json.loads(request.model_dump_json()),
        )

    def document_chunks(self, document_id: str) -> dict:
        self._ensure_authenticated()

        request = R2RDocumentChunksRequest(document_id=document_id)
        return self._make_request(
            "GET",
            "document_chunks",
            json=json.loads(request.model_dump_json()),
        )

    def inspect_knowledge_graph(self, limit: int = 100) -> str:
        self._ensure_authenticated()

        request = R2RPrintRelationshipsRequest(limit=limit)
        return self._make_request(
            "POST",
            "inspect_knowledge_graph",
            json=json.loads(request.model_dump_json()),
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
            "POST", "request_password_reset", json={"email": email}
        )

    def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> dict:
        return self._make_request(
            "POST",
            f"reset_password/{reset_token}",
            json={"new_password": new_password},
        )

    def logout(self) -> dict:
        self._ensure_authenticated()
        response = self._make_request("POST", "logout")
        self.access_token = None
        self._refresh_token = None
        return response

    def update_user(self, user_data: dict) -> dict:
        self._ensure_authenticated()
        return self._make_request("PUT", "user", json=user_data)

    def delete_user(self, password: str) -> dict:
        self._ensure_authenticated()
        response = self._make_request(
            "DELETE", "user", json={"password": password}
        )
        self.access_token = None
        self._refresh_token = None
        return response

    def rag_agent(
        self,
        messages: list[dict],
        use_vector_search: bool = True,
        search_filters: Optional[dict[str, Any]] = {},
        search_limit: int = 10,
        do_hybrid_search: bool = False,
        use_kg_search: bool = False,
        kg_search_generation_config: Optional[dict] = None,
        rag_generation_config: Optional[Union[dict, GenerationConfig]] = None,
        kg_search_settings: Optional[Union[dict, KGSearchSettings]] = None,
        vector_search_settings: Optional[
            Union[dict, VectorSearchSettings]
        ] = None,
        task_prompt_override: Optional[str] = None,
    ) -> dict:
        self._ensure_authenticated()

        if isinstance(rag_generation_config, GenerationConfig):
            rag_generation_config = json.loads(
                rag_generation_config.model_dump_json()
            )
        if isinstance(kg_search_settings, KGSearchSettings):
            kg_search_settings = json.loads(
                kg_search_settings.model_dump_json()
            )
        if isinstance(vector_search_settings, VectorSearchSettings):
            vector_search_settings = json.loads(
                vector_search_settings.model_dump_json()
            )

        request = R2RRAGAgentRequest(
            messages=messages,
            vector_search_settings=vector_search_settings
            or {
                "use_vector_search": use_vector_search,
                "search_filters": search_filters or {},
                "search_limit": search_limit,
                "do_hybrid_search": do_hybrid_search,
            },
            kg_search_settings=kg_search_settings
            or {
                "use_kg_search": use_kg_search,
                "kg_search_generation_config": kg_search_generation_config,
            },
            rag_generation_config=rag_generation_config,
            task_prompt_override=task_prompt_override,
        )

        if rag_generation_config and rag_generation_config.get(
            "stream", False
        ):
            return self._stream_rag_agent_sync(request)
        else:
            return self._make_request(
                "POST", "rag_agent", json=json.loads(request.model_dump_json())
            )

    async def _stream_rag_agent(
        self, rag_agent_request: R2RRAGAgentRequest
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}{self.prefix}/rag_agent"
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                json=json.loads(
                    rag_agent_request.model_dump_json(),
                ),
                timeout=self.timeout,
            ) as response:
                handle_request_error(response)
                async for chunk in response.aiter_text():
                    yield chunk

    def _stream_rag_agent_sync(
        self, rag_agent_request: R2RRAGAgentRequest
    ) -> Generator[str, None, None]:
        async def run_async_generator():
            async for chunk in self._stream_rag_agent(rag_agent_request):
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


if __name__ == "__main__":
    client = R2RClient(base_url="http://localhost:8000")
    fire.Fire(client)
