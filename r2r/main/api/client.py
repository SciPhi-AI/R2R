import asyncio
import functools
import json
import threading
import time
import uuid
from typing import Any, AsyncGenerator, Generator, Optional, Union

import fire
import httpx
import nest_asyncio
import requests

from r2r.base import GenerationConfig, KGSearchSettings, VectorSearchSettings

from .requests import (
    R2RAnalyticsRequest,
    R2RDeleteRequest,
    R2RDocumentChunksRequest,
    R2RDocumentsOverviewRequest,
    R2RIngestDocumentsRequest,
    R2RIngestFilesRequest,
    R2RLogsRequest,
    R2RRAGRequest,
    R2RSearchRequest,
    R2RUpdateDocumentsRequest,
    R2RUpdateFilesRequest,
    R2RUpdatePromptRequest,
    R2RUsersOverviewRequest,
)

nest_asyncio.apply()


class R2RHTTPError(Exception):
    def __init__(self, status_code, error_type, message):
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        super().__init__(f"[{status_code}] {error_type}: {message}")


def handle_request_error(response):
    if response.status_code >= 400:
        try:
            error_content = response.json()
            if isinstance(error_content, dict) and "detail" in error_content:
                detail = error_content["detail"]
                if isinstance(detail, dict):
                    message = detail.get("message", str(response.text))
                    error_type = detail.get("error_type", "UnknownError")
                else:
                    message = str(detail)
                    error_type = "HTTPException"
            else:
                message = str(error_content)
                error_type = "UnknownError"
        except json.JSONDecodeError:
            message = response.text
            error_type = "UnknownError"

        raise R2RHTTPError(
            status_code=response.status_code,
            error_type=error_type,
            message=message,
        )


def monitor_request(func):
    @functools.wraps(func)
    def wrapper(*args, monitor=False, **kwargs):
        if not monitor:
            return func(*args, **kwargs)

        result = None
        exception = None

        def run_func():
            nonlocal result, exception
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                exception = e

        thread = threading.Thread(target=run_func)
        thread.start()

        dots = [".", "..", "..."]
        i = 0
        while thread.is_alive():
            print(f"\rRequesting{dots[i % 3]}", end="", flush=True)
            i += 1
            time.sleep(0.5)

        thread.join()

        print("\r", end="", flush=True)

        if exception:
            raise exception
        return result

    return wrapper


class R2RClient:
    def __init__(self, base_url: str, prefix: str = "/v1"):
        self.base_url = base_url
        self.prefix = prefix

    def _make_request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}{self.prefix}/{endpoint}"
        response = requests.request(method, url, **kwargs)
        handle_request_error(response)
        return response.json()

    def health(self) -> dict:
        return self._make_request("GET", "health")

    def update_prompt(
        self,
        name: str = "default_system",
        template: Optional[str] = None,
        input_types: Optional[dict] = None,
    ) -> dict:
        request = R2RUpdatePromptRequest(
            name=name, template=template, input_types=input_types
        )
        return self._make_request(
            "POST", "update_prompt", json=json.loads(request.json())
        )

    @monitor_request
    def ingest_documents(
        self, documents: list[dict], versions: Optional[list[str]] = None
    ):
        request = R2RIngestDocumentsRequest(
            documents=documents, versions=versions
        )
        return self._make_request(
            "POST", "ingest_documents", json=json.loads(request.json())
        )

    @monitor_request
    def ingest_files(
        self,
        file_paths: list[str],
        metadatas: Optional[list[dict]] = None,
        document_ids: Optional[list[Union[uuid.UUID, str]]] = None,
        user_ids: Optional[list[Union[uuid.UUID, str]]] = None,
        versions: Optional[list[str]] = None,
    ) -> dict:
        files_to_upload = [
            ("files", (file, open(file, "rb"), "application/octet-stream"))
            for file in file_paths
        ]
        request = R2RIngestFilesRequest(
            metadatas=metadatas,
            document_ids=(
                [str(ele) for ele in document_ids] if document_ids else None
            ),
            user_ids=(
                [(str(ele) if ele else None) for ele in user_ids]
                if user_ids
                else None
            ),
            versions=versions,
        )
        try:
            return self._make_request(
                "POST",
                "ingest_files",
                data={
                    k: json.dumps(v)
                    for k, v in json.loads(request.json()).items()
                },
                files=files_to_upload,
            )
        finally:
            for _, file_tuple in files_to_upload:
                file_tuple[1].close()

    @monitor_request
    def update_documents(
        self,
        documents: list[dict],
        versions: Optional[list[str]] = None,
        metadatas: Optional[list[dict]] = None,
    ) -> dict:
        request = R2RUpdateDocumentsRequest(
            documents=documents, versions=versions, metadatas=metadatas
        )
        return self._make_request(
            "POST", "update_documents", json=json.loads(request.json())
        )

    @monitor_request
    def update_files(
        self,
        files: list[str],
        document_ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> dict:
        files_to_upload = [
            ("files", (file, open(file, "rb"), "application/octet-stream"))
            for file in files
        ]
        request = R2RUpdateFilesRequest(
            metadatas=metadatas,
            document_ids=document_ids,
        )
        try:
            return self._make_request(
                "POST",
                "update_files",
                data={
                    k: json.dumps(v)
                    for k, v in json.loads(request.json()).items()
                },
                files=files_to_upload,
            )
        finally:
            for _, file_tuple in files_to_upload:
                file_tuple[1].close()

    def search(
        self,
        query: str,
        use_vector_search: bool = True,
        search_filters: Optional[dict[str, Any]] = {},
        search_limit: int = 10,
        do_hybrid_search: bool = False,
        use_kg_search: bool = False,
        kg_agent_generation_config: Optional[GenerationConfig] = None,
    ) -> dict:
        request = R2RSearchRequest(
            query=query,
            vector_search_settings=VectorSearchSettings(
                use_vector_search=use_vector_search,
                search_filters=search_filters or {},
                search_limit=search_limit,
                do_hybrid_search=do_hybrid_search,
            ),
            kg_search_settings=KGSearchSettings(
                use_kg_search=use_kg_search,
                agent_generation_config=kg_agent_generation_config,
            ),
        )
        return self._make_request(
            "POST", "search", json=json.loads(request.json())
        )

    def rag(
        self,
        query: str,
        use_vector_search: bool = True,
        search_filters: Optional[dict[str, Any]] = {},
        search_limit: int = 10,
        do_hybrid_search: bool = False,
        use_kg_search: bool = False,
        kg_agent_generation_config: Optional[GenerationConfig] = None,
        rag_generation_config: Optional[GenerationConfig] = None,
    ) -> dict:
        request = R2RRAGRequest(
            query=query,
            vector_search_settings=VectorSearchSettings(
                use_vector_search=use_vector_search,
                search_filters=search_filters or {},
                search_limit=search_limit,
                do_hybrid_search=do_hybrid_search,
            ),
            kg_search_settings=KGSearchSettings(
                use_kg_search=use_kg_search,
                agent_generation_config=kg_agent_generation_config,
            ),
            rag_generation_config=rag_generation_config,
        )

        if rag_generation_config.stream:
            return self._stream_rag_sync(request)
        else:
            return self._make_request(
                "POST", "rag", json=json.loads(request.json())
            )

    async def _stream_rag(
        self, rag_request: R2RRAGRequest
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}{self.prefix}/rag"
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST", url, json=json.loads(rag_request.json())
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
                chunk = loop.run_until_complete(async_gen.__anext__())
                yield chunk
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    def delete(
        self, keys: list[str], values: list[Union[bool, int, str]]
    ) -> dict:
        request = R2RDeleteRequest(keys=keys, values=values)
        return self._make_request(
            "DELETE", "delete", json=json.loads(request.json())
        )

    def logs(self, log_type_filter: Optional[str] = None) -> dict:
        request = R2RLogsRequest(log_type_filter=log_type_filter)
        return self._make_request(
            "GET", "logs", json=json.loads(request.json())
        )

    def app_settings(self) -> dict:
        return self._make_request("GET", "app_settings")

    def analytics(self, filter_criteria: dict, analysis_types: dict) -> dict:
        request = R2RAnalyticsRequest(
            filter_criteria=filter_criteria, analysis_types=analysis_types
        )
        return self._make_request(
            "GET", "analytics", json=json.loads(request.json())
        )

    def users_overview(
        self, user_ids: Optional[list[uuid.UUID]] = None
    ) -> dict:
        request = R2RUsersOverviewRequest(user_ids=user_ids)
        return self._make_request(
            "GET", "users_overview", json=json.loads(request.json())
        )

    def documents_overview(
        self,
        document_ids: Optional[list[str]] = None,
        user_ids: Optional[list[str]] = None,
    ) -> dict:
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
            "GET", "documents_overview", json=json.loads(request.json())
        )

    def document_chunks(self, document_id: str) -> dict:
        request = R2RDocumentChunksRequest(document_id=document_id)
        return self._make_request(
            "GET", "document_chunks", json=json.loads(request.json())
        )


if __name__ == "__main__":
    client = R2RClient(base_url="http://localhost:8000")
    fire.Fire(client)
