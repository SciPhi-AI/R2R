import asyncio
import json
import uuid
from typing import AsyncGenerator, Generator, Optional, Union

import fire
import httpx
import nest_asyncio
import requests

from r2r.core import KGSearchSettings, VectorSearchSettings
from r2r.main.r2r_abstractions import (
    GenerationConfig,
    R2RAnalyticsRequest,
    R2RDeleteRequest,
    R2RDocumentChunksRequest,
    R2RDocumentsInfoRequest,
    R2RIngestDocumentsRequest,
    R2RIngestFilesRequest,
    R2RRAGRequest,
    R2RSearchRequest,
    R2RUpdateDocumentsRequest,
    R2RUpdateFilesRequest,
    R2RUpdatePromptRequest,
    R2RUsersStatsRequest,
)

nest_asyncio.apply()


class R2RClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def update_prompt(
        self,
        name: str = "default_system",
        template: Optional[str] = None,
        input_types: Optional[dict] = None,
    ) -> dict:
        url = f"{self.base_url}/update_prompt"
        request = R2RUpdatePromptRequest(
            name=name, template=template, input_types=input_types
        )
        response = requests.post(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def ingest_documents(
        self, documents: list[dict], versions: Optional[list[str]] = None
    ) -> dict:
        url = f"{self.base_url}/ingest_documents"
        request = R2RIngestDocumentsRequest(
            documents=documents, versions=versions
        )
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
        url = f"{self.base_url}/ingest_files"
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
        request_dict = json.loads(request.json())
        print("request_dict = ", request_dict)
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
        url = f"{self.base_url}/update_documents"
        request = R2RUpdateDocumentsRequest(documents=documents, versions=None)
        response = requests.post(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def update_files(
        self,
        files: list[str],
        document_ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> dict:
        url = f"{self.base_url}/update_files"
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
        search_request: R2RSearchRequest,
    ) -> dict:
        url = f"{self.base_url}/search"
        response = requests.post(url, json=json.loads(search_request.json()))
        response.raise_for_status()
        return response.json()

    def rag(
        self,
        message: str,
        vector_search_settings: VectorSearchSettings,
        kg_search_settings: KGSearchSettings,
        streaming: bool = False,
        rag_generation_config: Optional[GenerationConfig] = None,
    ) -> Union[dict, Generator[str, None, None]]:
        rag_request = R2RRAGRequest(
            message=message,
            vector_settings=vector_search_settings,
            kg_settings=kg_search_settings,
            rag_generation_config=rag_generation_config,
        )

        if streaming:
            return self._stream_rag_sync(rag_request)
        else:
            try:
                url = f"{self.base_url}/rag"
                response = requests.post(
                    url, json=json.loads(rag_request.json())
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                raise e

    async def _stream_rag(
        self, rag_request: R2RRAGRequest
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/rag"
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
        url = f"{self.base_url}/delete"
        request = R2RDeleteRequest(keys=keys, values=values)
        response = requests.delete(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def logs(self, log_type_filter: Optional[str] = None) -> dict:
        url = f"{self.base_url}/logs"
        params = {}
        if log_type_filter:
            params["log_type_filter"] = log_type_filter
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def app_settings(self) -> dict:
        url = f"{self.base_url}/app_settings"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def analytics(self, filter_criteria: dict, analysis_types: dict) -> dict:
        url = f"{self.base_url}/analytics"
        request = R2RAnalyticsRequest(
            filter_criteria=filter_criteria, analysis_types=analysis_types
        )
        response = requests.post(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def users_stats(self, user_ids: Optional[list[str]] = None) -> dict:
        url = f"{self.base_url}/users_stats"
        request = R2RUsersStatsRequest(
            user_ids=[uuid.UUID(uid) for uid in user_ids] if user_ids else None
        )
        response = requests.get(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()

    def documents_info(
        self,
        document_ids: Optional[list[str]] = None,
        user_ids: Optional[list[str]] = None,
    ) -> dict:
        url = f"{self.base_url}/documents_info"
        request = R2RDocumentsInfoRequest(
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
        url = f"{self.base_url}/document_chunks"
        request = R2RDocumentChunksRequest(document_id=document_id)
        response = requests.post(url, json=json.loads(request.json()))
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    client = R2RClient(base_url="http://localhost:8000")
    fire.Fire(client)
