"""Module for the R2RClient class."""

import asyncio
import base64
import json
import uuid
from typing import AsyncGenerator, Generator, Optional, Union

import httpx
import nest_asyncio
import requests

from r2r.core import DocumentType

nest_asyncio.apply()


def default_serializer(obj):
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, DocumentType):
        return obj.value
    if isinstance(obj, bytes):
        # return base64.b64encode(obj).decode('utf-8')
        raise TypeError("Bytes serialization is not yet supported.")
    raise TypeError(f"Type {type(obj)} not serializable.")


class R2RClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def ingest_documents(self, documents: list[dict]) -> dict:
        url = f"{self.base_url}/ingest_documents/"
        data = {"documents": documents}
        serialized_data = json.dumps(data, default=default_serializer)
        response = requests.post(
            url,
            data=serialized_data,
            headers={"Content-Type": "application/json"},
        )

        response.raise_for_status()
        return response.json()

    def ingest_files(
        self,
        metadatas: Optional[list[dict]],
        files: list[str],
        ids: Optional[list[str]] = None,
    ) -> dict:
        url = f"{self.base_url}/ingest_files/"
        files_to_upload = [
            ("files", (file, open(file, "rb"), "application/octet-stream"))
            for file in files
        ]
        data = {
            "metadatas": None
            if metadatas is None
            else json.dumps(metadatas, default=default_serializer),
            "ids": None
            if ids is None
            else json.dumps(ids, default=default_serializer),
        }
        response = requests.post(url, files=files_to_upload, data=data)
        response.raise_for_status()
        return response.json()

    def update_documents(self, documents: list[dict]) -> dict:
        url = f"{self.base_url}/update_documents/"
        data = {"documents": documents}
        serialized_data = json.dumps(data, default=default_serializer)
        response = requests.post(
            url,
            data=serialized_data,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    def update_files(
        self,
        metadatas: Optional[list[dict]],
        files: list[str],
        ids: list[str],
    ) -> dict:
        url = f"{self.base_url}/update_files/"
        files_to_upload = [
            ("files", (file, open(file, "rb"), "application/octet-stream"))
            for file in files
        ]
        data = {
            "metadatas": None
            if metadatas is None
            else json.dumps(metadatas, default=default_serializer),
            "ids": json.dumps(ids, default=default_serializer),
        }
        response = requests.post(url, files=files_to_upload, data=data)
        response.raise_for_status()
        return response.json()

    def search(
        self,
        query: str,
        search_filters: Optional[dict] = None,
        search_limit: int = 10,
    ) -> dict:
        url = f"{self.base_url}/search/"
        data = {
            "query": query,
            "search_filters": json.dumps(search_filters or {}),
            "search_limit": search_limit,
        }
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def rag(
        self,
        message: str,
        search_filters: Optional[dict] = None,
        search_limit: int = 10,
        rag_generation_config: Optional[dict] = None,
        streaming: bool = False,
    ) -> Union[dict, Generator[str, None, None]]:
        if streaming:
            return self._stream_rag_sync(
                message=message,
                search_filters=search_filters,
                search_limit=search_limit,
                rag_generation_config=rag_generation_config,
            )
        else:
            url = f"{self.base_url}/rag/"
            data = {
                "message": message,
                "search_filters": json.dumps(search_filters)
                if search_filters
                else None,
                "search_limit": search_limit,
                "rag_generation_config": json.dumps(rag_generation_config)
                if rag_generation_config
                else None,
                "streaming": streaming,
            }
            response = requests.post(url, json=data)
            response.raise_for_status()
            return response.json()

    async def _stream_rag(
        self,
        message: str,
        search_filters: Optional[dict] = None,
        search_limit: int = 10,
        rag_generation_config: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/rag/"
        data = {
            "message": message,
            "search_filters": json.dumps(search_filters)
            if search_filters
            else None,
            "search_limit": search_limit,
            "rag_generation_config": json.dumps(rag_generation_config)
            if rag_generation_config
            else None,
            "streaming": True,
        }
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, json=data) as response:
                response.raise_for_status()
                async for chunk in response.aiter_text():
                    yield chunk

    def _stream_rag_sync(
        self,
        message: str,
        search_filters: Optional[dict] = None,
        search_limit: int = 10,
        rag_generation_config: Optional[dict] = None,
    ) -> Generator[str, None, None]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async_gen = self._stream_rag(
            message=message,
            search_filters=search_filters,
            search_limit=search_limit,
            rag_generation_config=rag_generation_config,
        )
        for chunk in loop.run_until_complete(
            self._iterate_async_gen(async_gen)
        ):
            yield chunk

    async def _iterate_async_gen(
        self, async_gen: AsyncGenerator[str, None]
    ) -> list[str]:
        chunks = []
        async for chunk in async_gen:
            chunks.append(chunk)
        return chunks

    def delete(
        self, keys: list[str], values: list[Union[bool, int, str]]
    ) -> dict:
        url = f"{self.base_url}/delete/"
        data = {"keys": keys, "values": values}
        response = requests.request("DELETE", url, json=data)
        response.raise_for_status()
        return response.json()

    def get_user_ids(self) -> dict:
        url = f"{self.base_url}/get_user_ids/"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def get_user_documents_metadata(self, user_id: str) -> dict:
        url = f"{self.base_url}/get_user_documents_metadata/"
        data = {"user_id": user_id}
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def get_document_data(self, document_id: str) -> dict:
        url = f"{self.base_url}/get_document_data/"
        data = {"document_id": document_id}
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def get_logs(self, log_type_filter: Optional[str] = None) -> dict:
        url = f"{self.base_url}/get_logs/"
        data = {"log_type_filter": log_type_filter}
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
