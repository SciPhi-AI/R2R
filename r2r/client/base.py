from typing import Any, Dict, List, Optional, Union

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
            import json

            files = {
                "file": (file_path.split("/")[-1], file, "application/pdf")
            }
            data = {
                "document_id": document_id,
                "metadata": json.dumps(metadata)
                if metadata
                else json.dumps({}),
                "settings": json.dumps(settings)
                if settings
                else json.dumps({}),
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
        limit: Optional[int] = 10,
        filters: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ):
        url = f"{self.base_url}/search/"
        json_data = {
            "query": query,
            "filters": filters or {},
            "limit": limit,
            "settings": settings or {},
        }
        response = requests.post(url, json=json_data)
        return response.json()

    def rag_completion(
        self,
        query: str,
        limit: Optional[int] = 10,
        filters: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ):
        url = f"{self.base_url}/rag_completion/"
        json_data = {
            "query": query,
            "filters": filters or {},
            "limit": limit,
            "settings": settings or {},
        }
        response = requests.post(url, json=json_data)
        return response.json()

    def filtered_deletion(self, key: str, value: Union[bool, int, str]):
        url = f"{self.base_url}/filtered_deletion/"
        response = requests.delete(url, params={"key": key, "value": value})
        return response.json()

    def get_logs(self):
        url = f"{self.base_url}/logs"
        response = requests.get(url)
        return response.json()

    def get_logs_summary(self):
        url = f"{self.base_url}/logs_summary"
        response = requests.get(url)
        return response.json()
