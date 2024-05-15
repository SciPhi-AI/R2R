import json

import requests

from ..abstractions.document import Document


class R2RClient:
    def __init__(self, base_url):
        self.base_url = base_url

    def ingest_documents(self, documents: list[Document]):
        url = f"{self.base_url}/ingest_documents/"

        json_docs = [json.loads(doc.json()) for doc in documents]
        response = requests.post(url, json=json_docs)
        return response.json()

    def ingest_files(self, metadata: dict, ids: list, files: list):
        url = f"{self.base_url}/ingest_files/"

        # Prepare the files payload
        files_payload = [
            (
                "files",
                (
                    file["filename"],
                    open(file["filepath"], "rb"),
                    file["content_type"],
                ),
            )
            for file in files
        ]

        # Prepare the data payload
        data_payload = {
            "metadata": json.dumps(metadata),
            "ids": json.dumps(ids),
        }

        # Send the request
        response = requests.post(url, data=data_payload, files=files_payload)
        return response.json()

    def search(self, query: str, search_filters=None, search_limit=10):
        url = f"{self.base_url}/search/"
        payload = {
            "query": query,
            "search_filters": search_filters or "{}",
            "search_limit": str(search_limit),
        }
        response = requests.post(url, json=payload)
        return response.json()

    def rag(
        self,
        query,
        search_filters=None,
        search_limit=10,
        generation_config=None,
        streaming=False,
    ):
        url = f"{self.base_url}/rag/"
        payload = {
            "query": query,
            "search_filters": search_filters,
            "search_limit": search_limit,
            "generation_config": generation_config,
            "streaming": streaming,
        }
        response = requests.post(url, json=payload)
        return response.json()

    # def ingest_documents(self, documents: list[Document]):
    #     url = f"{self.base_url}/ingest_documents/"
    #     response = requests.post(url, json={"documents": [ele.dict() for ele in documents]})
    #     return response.json()

    # def ingest_files(self, files, metadata: str = "{}", ids: str = "[]"):
    #     url = f"{self.base_url}/ingest_files/"
    #     files_payload = [('files', (file['filename'], open(file['filepath'], 'rb'), file['content_type'])) for file in files]
    #     data_payload = {
    #         'metadata': json.dumps(metadata),
    #         'ids': json.dumps(ids)
    #     }
    #     response = requests.post(url, data=data_payload, files=files_payload)
    #     return response.json()

    # def search(self, query, search_filters=None, search_limit=10):
    #     url = f"{self.base_url}/search/"
    #     payload = {
    #         'query': query,
    #         'search_filters': search_filters,
    #         'search_limit': search_limit
    #     }
    #     response = requests.post(url, json=payload)
    #     return response.json()

    # def rag(self, query, search_filters=None, search_limit=10, generation_config=None, streaming=False):
    #     url = f"{self.base_url}/rag/"
    #     payload = {
    #         'query': query,
    #         'search_filters': search_filters,
    #         'search_limit': search_limit,
    #         'generation_config': generation_config,
    #         'streaming': streaming
    #     }
    #     response = requests.post(url, json=payload)
    #     return response.json()


# import json
# from typing import Any, Dict, List, Optional, Union

# import httpx
# import requests


# class R2RClient:
#     def __init__(self, base_url: str):
#         self.base_url = base_url

#     def ingest_file(
#         self,
#         document_id: str,
#         file_path: str,
#         metadata: Optional[dict] = None,
#         settings: Optional[dict] = None,
#     ):
#         url = f"{self.base_url}/ingest_file/"
#         with open(file_path, "rb") as file:
#             files = {
#                 "file": (file_path.split("/")[-1], file, "application/pdf")
#             }
#             data = {
#                 "document_id": document_id,
#                 "metadata": (
#                     json.dumps(metadata) if metadata else json.dumps({})
#                 ),
#                 "settings": (
#                     json.dumps(settings) if settings else json.dumps({})
#                 ),
#             }
#             response = requests.post(
#                 url,
#                 files=files,
#                 data=data,
#             )
#         return response.json()

#     def add_entry(
#         self,
#         document_id: str,
#         blobs: Dict[str, str],
#         metadata: Optional[Dict[str, Any]] = None,
#         do_upsert: Optional[bool] = False,
#         settings: Optional[Dict[str, Any]] = None,
#     ):
#         url = f"{self.base_url}/add_entry/"
#         json_data = {
#             "entry": {
#                 "document_id": document_id,
#                 "blobs": blobs,
#                 "metadata": metadata or {},
#             },
#             "settings": settings
#             or {"embedding_settings": {"do_upsert": do_upsert}},
#         }
#         response = requests.post(url, json=json_data)
#         return response.json()

#     def add_entries(
#         self,
#         entries: List[Dict[str, Any]],
#         do_upsert: Optional[bool] = False,
#         settings: Optional[Dict[str, Any]] = None,
#     ):
#         url = f"{self.base_url}/add_entries/"
#         json_data = {
#             "entries": entries,
#             "settings": settings
#             or {"embedding_settings": {"do_upsert": do_upsert}},
#         }
#         response = requests.post(url, json=json_data)
#         return response.json()

#     def search(
#         self,
#         query: str,
#         search_limit: Optional[int] = 25,
#         rerank_limit: Optional[int] = 15,
#         filters: Optional[Dict[str, Any]] = None,
#         settings: Optional[Dict[str, Any]] = None,
#     ):
#         url = f"{self.base_url}/search/"
#         json_data = {
#             "message": query,
#             "filters": filters or {},
#             "search_limit": search_limit,
#             "rerank_limit": rerank_limit,
#             "settings": settings or {},
#         }
#         response = requests.post(url, json=json_data)
#         return response.json()

#     # TODO - Cleanup redundant code in the following methods
#     # TODO - Consider how to improve `rag_completion` and
#     # `stream_rag_completion` workflows.
#     def rag_completion(
#         self,
#         message: str,
#         search_limit: Optional[int] = 25,
#         rerank_limit: Optional[int] = 15,
#         filters: Optional[Dict[str, Any]] = None,
#         settings: Optional[Dict[str, Any]] = None,
#         generation_config: Optional[Dict[str, Any]] = None,
#     ):
#         if not generation_config:
#             generation_config = {}
#         stream = generation_config.get("stream", False)

#         if stream:
#             raise ValueError(
#                 "To stream, use the `stream_rag_completion` method."
#             )

#         url = f"{self.base_url}/rag_completion/"
#         json_data = {
#             "message": message,
#             "filters": filters or {},
#             "search_limit": search_limit,
#             "rerank_limit": rerank_limit,
#             "settings": settings or {},
#             "generation_config": generation_config or {},
#         }
#         response = requests.post(url, json=json_data)
#         return response.json()

#     def eval(
#         self,
#         message: str,
#         context: str,
#         completion_text: str,
#         run_id: str,
#         settings: Optional[Dict[str, Any]] = None,
#     ):
#         url = f"{self.base_url}/eval/"
#         payload = {
#             "message": message,
#             "context": context,
#             "completion_text": completion_text,
#             "run_id": run_id,
#             "settings": settings or {},
#         }
#         response = requests.post(url, json=payload)
#         return response.json()

#     async def stream_rag_completion(
#         self,
#         message: str,
#         search_limit: Optional[int] = 25,
#         rerank_limit: Optional[int] = 15,
#         filters: Optional[Dict[str, Any]] = None,
#         settings: Optional[Dict[str, Any]] = None,
#         generation_config: Optional[Dict[str, Any]] = None,
#         timeout: int = 300,
#     ):
#         if not generation_config:
#             generation_config = {}
#         stream = generation_config.get("stream", False)
#         if not stream:
#             raise ValueError(
#                 "`stream_rag_completion` method is only for streaming."
#             )

#         url = f"{self.base_url}/rag_completion/"

#         headers = {
#             "accept": "application/json",
#             "Content-Type": "application/json",
#         }
#         json_data = {
#             "message": message,
#             "filters": filters or {},
#             "search_limit": search_limit,
#             "rerank_limit": rerank_limit,
#             "settings": settings or {},
#             "generation_config": generation_config or {},
#         }
#         timeout_config = httpx.Timeout(timeout)  # Configure the timeout

#         async with httpx.AsyncClient(timeout=timeout_config) as client:
#             async with client.stream(
#                 "POST", url, headers=headers, json=json_data
#             ) as response:
#                 async for chunk in response.aiter_bytes():
#                     yield chunk.decode()

#     def delete_by_metadata(self, key: str, value: Union[bool, int, str]):
#         url = f"{self.base_url}/delete_by_metadata/"
#         response = requests.delete(url, params={"key": key, "value": value})
#         return response.json()

#     def get_logs(self, type=None):
#         params = {}
#         if type:
#             params["type"] = type
#         response = requests.get(f"{self.base_url}/logs", params=params)
#         return response.json()

#     def get_logs_summary(self, type=None):
#         params = {}
#         if type:
#             params["type"] = type
#         response = requests.get(f"{self.base_url}/logs_summary", params=params)
#         return response.json()

#     def get_user_ids(self):
#         url = f"{self.base_url}/get_user_ids/"
#         response = requests.get(url)
#         return response.json()

#     def get_user_documents(self, user_id: str):
#         url = f"{self.base_url}/get_user_documents/"
#         response = requests.get(url, params={"user_id": user_id})
#         return response.json()
