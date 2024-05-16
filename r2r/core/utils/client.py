import json
from typing import Dict, List, Optional

import requests


class R2RClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def ingest_documents(self, documents: List[Dict]) -> Dict:
        url = f"{self.base_url}/ingest_documents/"
        data = {"documents": documents}
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def ingest_files(
        self,
        metadatas: List[Dict],
        files: List[str],
        ids: Optional[List[str]] = None,
    ) -> Dict:
        url = f"{self.base_url}/ingest_files/"
        files_to_upload = [
            ("files", (file, open(file, "rb"), "application/octet-stream"))
            for file in files
        ]
        data = {
            "metadatas": json.dumps(metadatas),
            "ids": json.dumps(ids or []),
        }
        response = requests.post(url, files=files_to_upload, data=data)
        response.raise_for_status()
        return response.json()

    def search(
        self, query: str, search_filters: Dict = {}, search_limit: int = 10
    ) -> Dict:
        url = f"{self.base_url}/search/"
        data = {
            "query": query,
            "search_filters": json.dumps(search_filters),
            "search_limit": search_limit,
        }
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def rag(
        self,
        message: str,
        search_filters: Optional[Dict] = None,
        search_limit: int = 10,
        generation_config: Optional[Dict] = None,
        streaming: bool = False,
    ) -> Dict:
        url = f"{self.base_url}/rag/"
        data = {
            "message": message,
            "search_filters": json.dumps(search_filters or {}),
            "search_limit": search_limit,
            "streaming": streaming,
        }
        if generation_config:
            data["generation_config"] = json.dumps(generation_config)
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def delete(self, key: str, value: str) -> Dict:
        url = f"{self.base_url}/delete/"
        data = {"key": key, "value": value}
        response = requests.request("DELETE", url, json=data)
        response.raise_for_status()
        return response.json()

    def get_user_ids(self) -> Dict:
        url = f"{self.base_url}/get_user_ids/"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def get_user_document_data(self, user_id: str) -> Dict:
        url = f"{self.base_url}/get_user_document_data/"
        data = {"user_id": user_id}
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def get_logs(
        self, pipeline_type: Optional[str] = None, filter: Optional[str] = None
    ) -> Dict:
        url = f"{self.base_url}/get_logs/"
        data = {"pipeline_type": pipeline_type, "filter": filter}
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
