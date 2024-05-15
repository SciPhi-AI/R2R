import requests
import json
from typing import List, Dict, Optional

class R2RClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def ingest_documents(self, documents: List[Dict]) -> Dict:
        url = f"{self.base_url}/ingest_documents/"
        response = requests.post(url, json=documents)
        response.raise_for_status()
        return response.json()

    def ingest_files(self, metadata: Dict, files: List[str], ids: Optional[List[str]] = None) -> Dict:
        url = f"{self.base_url}/ingest_files/"
        files_to_upload = [("files", (file, open(file, "rb"), "application/octet-stream")) for file in files]
        data = {
            "metadata": json.dumps(metadata),
            "ids": json.dumps(ids or [])
        }
        response = requests.post(url, data=data, files=files_to_upload)
        response.raise_for_status()
        return response.json()

    def search(self, query: str, search_filters: Dict = {}, search_limit: int = 10) -> Dict:
        url = f"{self.base_url}/search/"
        data = {
            "query": query,
            "search_filters": json.dumps(search_filters),
            "search_limit": search_limit
        }
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json()

    def rag(self, query: str, search_filters: Optional[Dict] = None, search_limit: int = 10, generation_config: Optional[Dict] = None, streaming: bool = False) -> Dict:
        url = f"{self.base_url}/rag/"
        data = {
            "query": query,
            "search_filters": json.dumps(search_filters or {}),
            "search_limit": search_limit,
            "streaming": streaming
        }
        if generation_config:
            data["generation_config"] = json.dumps(generation_config)
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json()

    def delete(self, key: str, value: str) -> Dict:
        url = f"{self.base_url}/delete/"
        data = {"key": key, "value": value}
        response = requests.request("DELETE", url, data=data)
        response.raise_for_status()
        return response.json()

    def get_user_ids(self) -> Dict:
        url = f"{self.base_url}/get_user_ids/"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def get_user_document_ids(self, user_id: str) -> Dict:
        url = f"{self.base_url}/get_user_document_ids/"
        data = {"user_id": user_id}
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json()

    def get_logs(self, pipeline_type: Optional[str] = None, filter: Optional[str] = None) -> Dict:
        url = f"{self.base_url}/get_logs/"
        data = {"pipeline_type": pipeline_type, "filter": filter}
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json()
