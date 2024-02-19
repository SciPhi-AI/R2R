from typing import Any, Dict, List, Optional, Union

import requests


class SciPhiR2RClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def upload_and_process_file(self, file_path: str):
        url = f"{self.base_url}/upload_and_process_file/"
        files = {"file": open(file_path, "rb")}
        response = requests.post(url, files=files)
        return response.json()

    def upsert_entry(
        self,
        document_id: str,
        blob: str,
        type: str,
        metadata: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ):
        url = f"{self.base_url}/upsert_entry/"
        json_data = {
            "entry": {
                "document_id": document_id,
                "blob": blob,
                "type": type,
                "metadata": metadata or {},
            },
            "settings": settings or {},
        }
        response = requests.post(url, json=json_data)
        return response.json()

    def upsert_entries(
        self,
        entries: List[Dict[str, Any]],
        settings: Optional[Dict[str, Any]] = None,
    ):
        url = f"{self.base_url}/upsert_entries/"
        json_data = {"entries": entries, "settings": settings or {}}
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
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = 10,
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
