import json
from typing import Any, Dict, List, Optional, Union

import httpx
import requests


class R2RClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def upload_and_process_file(
        self,
        document_id: str,
        file_path: str,
        metadata: Optional[dict] = None,
        settings: Optional[dict] = None,
    ):
        url = f"{self.base_url}/upload_and_process_file/"
        with open(file_path, "rb") as file:
            files = {
                "file": (file_path.split("/")[-1], file, "application/pdf")
            }
            data = {
                "document_id": document_id,
                "metadata": (
                    json.dumps(metadata) if metadata else json.dumps({})
                ),
                "settings": (
                    json.dumps(settings) if settings else json.dumps({})
                ),
            }
            response = requests.post(
                url,
                files=files,
                data=data,
            )
        return response.json()

    def add_entry(
        self,
        document_id: str,
        blobs: Dict[str, str],
        metadata: Optional[Dict[str, Any]] = None,
        do_upsert: Optional[bool] = False,
        settings: Optional[Dict[str, Any]] = None,
    ):
        url = f"{self.base_url}/add_entry/"
        json_data = {
            "entry": {
                "document_id": document_id,
                "blobs": blobs,
                "metadata": metadata or {},
            },
            "settings": settings
            or {"embedding_settings": {"do_upsert": do_upsert}},
        }
        print("posting to url = ", url)
        response = requests.post(url, json=json_data)
        return response.json()

    def add_entries(
        self,
        entries: List[Dict[str, Any]],
        do_upsert: Optional[bool] = False,
        settings: Optional[Dict[str, Any]] = None,
    ):
        url = f"{self.base_url}/add_entries/"
        json_data = {
            "entries": entries,
            "settings": settings
            or {"embedding_settings": {"do_upsert": do_upsert}},
        }
        response = requests.post(url, json=json_data)
        return response.json()

    def search(
        self,
        query: str,
        search_limit: Optional[int] = 25,
        rerank_limit: Optional[int] = 15,
        filters: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ):
        url = f"{self.base_url}/search/"
        json_data = {
            "message": query,
            "filters": filters or {},
            "search_limit": search_limit,
            "rerank_limit": rerank_limit,
            "settings": settings or {},
        }
        response = requests.post(url, json=json_data)
        return response.json()

    # TODO - Cleanup redundant code in the following methods
    # TODO - Consider how to improve `rag_completion` and
    # `stream_rag_completion` workflows.
    def rag_completion(
        self,
        message: str,
        search_limit: Optional[int] = 25,
        rerank_limit: Optional[int] = 15,
        filters: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
    ):
        if not generation_config:
            generation_config = {}
        stream = generation_config.get("stream", False)

        if stream:
            raise ValueError(
                "To stream, use the `stream_rag_completion` method."
            )

        url = f"{self.base_url}/rag_completion/"
        json_data = {
            "message": message,
            "filters": filters or {},
            "search_limit": search_limit,
            "rerank_limit": rerank_limit,
            "settings": settings or {},
            "generation_config": generation_config or {},
        }
        response = requests.post(url, json=json_data)
        return response.json()

    def eval(
        self,
        message: str,
        context: str,
        completion_text: str,
        run_id: str,
        settings: Optional[Dict[str, Any]] = None,
    ):
        url = f"{self.base_url}/eval/"
        payload = {
            "message": message,
            "context": context,
            "completion_text": completion_text,
            "run_id": run_id,
            "settings": settings or {},
        }
        response = requests.post(url, json=payload)
        return response.json()

    async def stream_rag_completion(
        self,
        message: str,
        search_limit: Optional[int] = 25,
        rerank_limit: Optional[int] = 15,
        filters: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        timeout: int = 300,
    ):
        if not generation_config:
            generation_config = {}
        stream = generation_config.get("stream", False)
        if not stream:
            raise ValueError(
                "`stream_rag_completion` method is only for streaming."
            )

        url = f"{self.base_url}/rag_completion/"

        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        json_data = {
            "message": message,
            "filters": filters or {},
            "search_limit": search_limit,
            "rerank_limit": rerank_limit,
            "settings": settings or {},
            "generation_config": generation_config or {},
        }
        timeout_config = httpx.Timeout(timeout)  # Configure the timeout

        async with httpx.AsyncClient(timeout=timeout_config) as client:
            async with client.stream(
                "POST", url, headers=headers, json=json_data
            ) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk.decode()

    def filtered_deletion(self, key: str, value: Union[bool, int, str]):
        url = f"{self.base_url}/filtered_deletion/"
        response = requests.delete(url, params={"key": key, "value": value})
        return response.json()

    def get_logs(self, pipeline_type=None):
        params = {}
        if pipeline_type:
            params["pipeline_type"] = pipeline_type
        response = requests.get(f"{self.base_url}/logs", params=params)
        return response.json()

    def get_logs_summary(self, pipeline_type=None):
        params = {}
        if pipeline_type:
            params["pipeline_type"] = pipeline_type
        response = requests.get(f"{self.base_url}/logs_summary", params=params)
        return response.json()

    def get_user_ids(self):
        url = f"{self.base_url}/get_user_ids/"
        response = requests.get(url)
        return response.json()

    def get_user_documents(self, user_id: str):
        url = f"{self.base_url}/get_user_documents/"
        response = requests.get(url, params={"user_id": user_id})
        return response.json()
