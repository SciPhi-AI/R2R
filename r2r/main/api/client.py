import asyncio
import json
import uuid
from typing import Any, AsyncGenerator, Generator, Optional, Union

import fire
import httpx
import nest_asyncio
import requests

from r2r.core import GenerationConfig, KGSearchSettings, VectorSearchSettings

from ..abstractions import (
    R2RAnalyticsRequest,
    R2RDeleteRequest,
    R2RDocumentChunksRequest,
    R2RDocumentsOverviewRequest,
    R2RIngestDocumentsRequest,
    R2RIngestFilesRequest,
    R2RRAGRequest,
    R2RSearchRequest,
    R2RUpdateDocumentsRequest,
    R2RUpdateFilesRequest,
    R2RUpdatePromptRequest,
    R2RUsersOverviewRequest,
)

nest_asyncio.apply()


class R2RClient:
    def __init__(self, base_url: str, prefix: str = "/v1"):
        self.base_url = base_url
        self.prefix = prefix

    def update_prompt(
        self,
        name: str = "default_system",
        template: Optional[str] = None,
        input_types: Optional[dict] = None,
    ) -> dict:
        url = f"{self.base_url}{self.prefix}/update_prompt"
        request = R2RUpdatePromptRequest(
            name=name, template=template, input_types=input_types
        )
        response = requests.post(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def ingest_documents(
        self, documents: list[dict], versions: Optional[list[str]] = None
    ):
        request = R2RIngestDocumentsRequest(
            documents=documents, versions=versions
        )
        url = f"{self.base_url}{self.prefix}/ingest_documents"
        response = requests.post(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def ingest_files(
        self,
        file_paths: list[str],
        metadatas: Optional[list[dict]] = None,
        document_ids: Optional[list[Union[uuid.UUID, str]]] = None,
        user_ids: Optional[list[Union[uuid.UUID, str]]] = None,
        versions: Optional[list[str]] = None,
        skip_document_info: Optional[bool] = False,
    ) -> dict:
        url = f"{self.base_url}{self.prefix}/ingest_files"
        files_to_upload = [
            ("files", (file, open(file, "rb"), "application/octet-stream"))
            for file in file_paths
        ]
        request = R2RIngestFilesRequest(
            metadatas=metadatas,
            document_ids=(
                [str(ele) for ele in document_ids] if document_ids else None
            ),
            user_ids=[str(ele) for ele in user_ids] if user_ids else None,
            versions=versions,
            skip_document_info=skip_document_info,
        )
        response = requests.post(
            url,
            # must use data instead of json when sending files
            data={
                k: json.dumps(v) for k, v in json.loads(request.json()).items()
            },
            files=files_to_upload,
        )

        response.raise_for_status()
        return response.json()

    def update_documents(
        self,
        documents: list[dict],
        versions: Optional[list[str]] = None,
        metadatas: Optional[list[dict]] = None,
    ) -> dict:
        url = f"{self.base_url}{self.prefix}/update_documents"
        request = R2RUpdateDocumentsRequest(
            documents=documents, versions=versions, metadatas=metadatas
        )
        response = requests.post(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def update_files(
        self,
        files: list[str],
        document_ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> dict:
        url = f"{self.base_url}{self.prefix}/update_files"
        files_to_upload = [
            ("files", (file, open(file, "rb"), "application/octet-stream"))
            for file in files
        ]
        request = R2RUpdateFilesRequest(
            metadatas=metadatas,
            document_ids=document_ids,
        )
        response = requests.post(
            url, files=files_to_upload, data=request.json()
        )
        response.raise_for_status()
        return response.json()

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
                search_filters=search_filters,
                search_limit=search_limit,
                do_hybrid_search=do_hybrid_search,
            ),
            kg_search_settings=KGSearchSettings(
                use_kg_search=use_kg_search,
                agent_generation_config=kg_agent_generation_config,
            ),
        )
        url = f"{self.base_url}{self.prefix}/search"
        response = requests.post(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

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
                search_filters=search_filters,
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
            try:
                url = f"{self.base_url}{self.prefix}/rag"
                response = requests.post(url, json=json.loads(request.json()))
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                raise e

    async def _stream_rag(
        self, rag_request: R2RRAGRequest
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}{self.prefix}/rag"
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST", url, json=json.loads(rag_request.json())
            ) as response:
                response.raise_for_status()
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

        # Run the async generator and yield each chunk synchronously
        async_gen = run_async_generator()

        try:
            while True:
                # Fetch the next chunk from the async generator
                chunk = loop.run_until_complete(async_gen.__anext__())
                yield chunk
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    def delete(
        self, keys: list[str], values: list[Union[bool, int, str]]
    ) -> dict:
        url = f"{self.base_url}{self.prefix}/delete"
        request = R2RDeleteRequest(keys=keys, values=values)
        response = requests.delete(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def logs(self, log_type_filter: Optional[str] = None) -> dict:
        url = f"{self.base_url}{self.prefix}/logs"
        params = {}
        if log_type_filter:
            params["log_type_filter"] = log_type_filter
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def app_settings(self) -> dict:
        url = f"{self.base_url}{self.prefix}/app_settings"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def analytics(self, filter_criteria: dict, analysis_types: dict) -> dict:
        url = f"{self.base_url}{self.prefix}/analytics"
        request = R2RAnalyticsRequest(
            filter_criteria=filter_criteria, analysis_types=analysis_types
        )
        response = requests.get(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def users_overview(
        self, user_ids: Optional[list[uuid.UUID]] = None
    ) -> dict:
        url = f"{self.base_url}{self.prefix}/users_overview"
        request = R2RUsersOverviewRequest(user_ids=user_ids)
        response = requests.get(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def documents_overview(
        self,
        document_ids: Optional[list[str]] = None,
        user_ids: Optional[list[str]] = None,
    ) -> dict:
        url = f"{self.base_url}{self.prefix}/documents_overview"
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
        response = requests.get(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def document_chunks(self, document_id: str) -> dict:
        url = f"{self.base_url}{self.prefix}/document_chunks"
        request = R2RDocumentChunksRequest(document_id=document_id)
        response = requests.get(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    client = R2RClient(base_url="http://localhost:8000")
    fire.Fire(client)
