import asyncio
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
        raise TypeError("Bytes serialization is not yet supported.")
    raise TypeError(f"Type {type(obj)} not serializable.")


class R2RClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict] = None,
    ) -> dict:
        url = f"{self.base_url}/update_prompt"
        data = {
            "name": name,
            "template": template,
            "input_types": input_types,
        }
        response = requests.post(
            url,
            data=json.dumps(data, default=default_serializer),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    def ingest_documents(self, documents: list[dict]) -> dict:
        url = f"{self.base_url}/ingest_documents"
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
        files: list[str],
        metadatas: Optional[list[dict]] = None,
        ids: Optional[list[str]] = None,
        user_ids: Optional[list[str]] = None,
    ) -> dict:
        url = f"{self.base_url}/ingest_files"
        files_to_upload = [
            ("files", (file, open(file, "rb"), "application/octet-stream"))
            for file in files
        ]
        data = {
            "metadatas": (
                None
                if metadatas is None
                else json.dumps(metadatas, default=default_serializer)
            ),
            "document_ids": (
                None
                if ids is None
                else json.dumps(ids, default=default_serializer)
            ),
            "user_ids": (
                None
                if user_ids is None
                else json.dumps(user_ids, default=default_serializer)
            ),
        }
        response = requests.post(url, files=files_to_upload, data=data)
        response.raise_for_status()
        return response.json()

    def update_documents(self, documents: list[dict]) -> dict:
        url = f"{self.base_url}/update_documents"
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
        files: list[str],
        ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> dict:
        url = f"{self.base_url}/update_files"
        files_to_upload = [
            ("files", (file, open(file, "rb"), "application/octet-stream"))
            for file in files
        ]
        data = {
            "metadatas": (
                None
                if metadatas is None
                else json.dumps(metadatas, default=default_serializer)
            ),
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
        do_hybrid_search: bool = False,
    ) -> dict:
        url = f"{self.base_url}/search"
        data = {
            "query": query,
            "search_filters": json.dumps(search_filters or {}),
            "search_limit": search_limit,
            "do_hybrid_search": do_hybrid_search,
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
            try:
                url = f"{self.base_url}/rag"
                data = {
                    "message": message,
                    "search_filters": (
                        json.dumps(search_filters) if search_filters else None
                    ),
                    "search_limit": search_limit,
                    "rag_generation_config": (
                        json.dumps(rag_generation_config)
                        if rag_generation_config
                        else None
                    ),
                    "streaming": streaming,
                }

                response = requests.post(url, json=data)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                raise e

    async def _stream_rag(
        self,
        message: str,
        search_filters: Optional[dict] = None,
        search_limit: int = 10,
        rag_generation_config: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/rag"
        data = {
            "message": message,
            "search_filters": (
                json.dumps(search_filters) if search_filters else None
            ),
            "search_limit": search_limit,
            "rag_generation_config": (
                json.dumps(rag_generation_config)
                if rag_generation_config
                else None
            ),
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
        async def run_async_generator():
            async for chunk in self._stream_rag(
                message=message,
                search_filters=search_filters,
                search_limit=search_limit,
                rag_generation_config=rag_generation_config,
            ):
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
        data = {"keys": keys, "values": values}
        response = requests.request("DELETE", url, json=data)
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

    def documents_info(
        self,
        document_ids: Optional[list[str]] = None,
        user_ids: Optional[list[str]] = None,
    ) -> dict:
        url = f"{self.base_url}/documents_info"
        params = {}
        if document_ids is not None:
            params["document_ids"] = ",".join(document_ids)
        if user_ids is not None:
            params["user_ids"] = ",".join(user_ids)
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def analytics(self, filter_criteria: dict, analysis_types: dict) -> dict:
        url = f"{self.base_url}/analytics"
        data = {
            "filter_criteria": filter_criteria,
            "analysis_types": analysis_types,
        }

        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if e.response is None:
                raise requests.exceptions.RequestException(
                    f"Error occurred while calling analytics API. {str(e)}"
                ) from e
            status_code = e.response.status_code
            error_message = e.response.text
            raise requests.exceptions.RequestException(
                f"Error occurred while calling analytics API. Status Code: {status_code}, Error Message: {error_message}"
            ) from e

    def users_stats(self, user_ids: Optional[list[str]] = None) -> dict:
        url = f"{self.base_url}/users_stats"
        params = {}
        if user_ids is not None:
            params["user_ids"] = ",".join(user_ids)
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def documents_info(
        self,
        document_ids: Optional[str] = None,
        user_ids: Optional[str] = None,
    ) -> dict:
        url = f"{self.base_url}/documents_info"
        params = {}
        params["document_ids"] = (
            json.dumps(document_ids) if document_ids else None
        )
        params["user_ids"] = json.dumps(user_ids) if user_ids else None
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def document_chunks(self, document_id: str) -> dict:
        url = f"{self.base_url}/document_chunks"
        params = {"document_id": document_id}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def users_stats(self, user_ids: Optional[list[str]] = None) -> dict:
        url = f"{self.base_url}/users_stats"
        params = {}
        if user_ids is not None:
            params["user_ids"] = ",".join(user_ids)
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
