import asyncio
import json
import os
from inspect import getmembers, isasyncgenfunction, iscoroutinefunction
from io import BytesIO
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from ..base.base_client import sync_generator_wrapper, sync_wrapper


class DocumentsSDK:
    """
    SDK for interacting with documents in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        file_path: Optional[str] = None,
        content: Optional[str] = None,
        id: Optional[Union[str, UUID]] = None,
        metadata: Optional[dict] = None,
        ingestion_config: Optional[dict] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> dict:
        """
        Create a new document from either a file or content.
        """
        if not file_path and not content:
            raise ValueError("Either file_path or content must be provided")
        if file_path and content:
            raise ValueError("Cannot provide both file_path and content")

        data = {}
        files = None

        if id:
            data["id"] = json.dumps(str(id))
        if metadata:
            data["metadata"] = json.dumps(metadata)
        if ingestion_config:
            data["ingestion_config"] = json.dumps(ingestion_config)
        if run_with_orchestration is not None:
            data["run_with_orchestration"] = str(run_with_orchestration)

        if file_path:
            # Create a new file instance that will remain open during the request
            file_instance = open(file_path, "rb")
            files = [
                (
                    "file",
                    (file_path, file_instance, "application/octet-stream"),
                )
            ]
            try:
                result = await self.client._make_request(
                    "POST", "documents", data=data, files=files
                )
            finally:
                # Ensure we close the file after the request is complete
                file_instance.close()
            return result
        else:
            data["content"] = content  # type: ignore
            return await self.client._make_request(
                "POST", "documents", data=data
            )

    async def update(
        self,
        id: Union[str, UUID],
        file_path: Optional[str] = None,
        content: Optional[str] = None,
        metadata: Optional[dict] = None,
        ingestion_config: Optional[dict] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> dict:
        """
        Update an existing document.

        Args:
            id (Union[str, UUID]): ID of document to update
            file_path (Optional[str]): Path to the new file
            content (Optional[str]): New text content
            metadata (Optional[dict]): Updated metadata
            ingestion_config (Optional[dict]): Custom ingestion configuration
            run_with_orchestration (Optional[bool]): Whether to run with orchestration

        Returns:
            dict: Update results containing processed document information
        """
        if not file_path and not content:
            raise ValueError("Either file_path or content must be provided")
        if file_path and content:
            raise ValueError("Cannot provide both file_path and content")

        data = {}
        files = None

        if metadata:
            data["metadata"] = json.dumps([metadata])
        if ingestion_config:
            data["ingestion_config"] = json.dumps(ingestion_config)
        if run_with_orchestration is not None:
            data["run_with_orchestration"] = str(run_with_orchestration)

        if file_path:
            # Create a new file instance that will remain open during the request
            file_instance = open(file_path, "rb")
            files = [
                (
                    "file",
                    (file_path, file_instance, "application/octet-stream"),
                )
            ]
            try:
                result = await self.client._make_request(
                    "POST",
                    f"documents/{str(id)}",
                    data=data,
                    files=files,
                )
            finally:
                # Ensure we close the file after the request is complete
                file_instance.close()
            return result
        else:
            data["content"] = content  # type: ignore
            return await self.client._make_request(
                "POST", f"documents/{str(id)}", data=data
            )

    async def retrieve(
        self,
        id: Union[str, UUID],
    ) -> dict:
        """
        Get a specific document by ID.

        Args:
            id (Union[str, UUID]): ID of document to retrieve

        Returns:
            dict: Document information
        """
        return await self.client._make_request("GET", f"documents/{str(id)}")

    async def list(
        self,
        ids: Optional[List[Union[str, UUID]]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> dict:
        """
        List documents with pagination.

        Args:
            ids (Optional[List[Union[str, UUID]]]): Optional list of document IDs to filter by
            offset (Optional[int]): Pagination offset
            limit (Optional[int]): Maximum number of documents to return

        Returns:
            dict: List of documents and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
        }
        if ids:
            params["ids"] = [str(doc_id) for doc_id in ids]  # type: ignore

        return await self.client._make_request(
            "GET", "documents", params=params
        )

    async def download(
        self,
        id: Union[str, UUID],
    ) -> BytesIO:
        """
        Download a document's file content.

        Args:
            id (Union[str, UUID]): ID of document to download

        Returns:
            BytesIO: File content as a binary stream
        """
        return await self.client._make_request(
            "GET", f"documents/{str(id)}/download"
        )

    async def delete(
        self,
        id: Union[str, UUID],
    ) -> None:
        """
        Delete a specific document.

        Args:
            id (Union[str, UUID]): ID of document to delete
        """
        await self.client._make_request("DELETE", f"documents/{str(id)}")

    async def list_chunks(
        self,
        id: Union[str, UUID],
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        include_vectors: Optional[bool] = False,
    ) -> dict:
        """
        Get chunks for a specific document.

        Args:
            id (Union[str, UUID]): ID of document to retrieve chunks for
            offset (Optional[int]): Pagination offset
            limit (Optional[int]): Maximum number of chunks to return
            include_vectors (Optional[bool]): Whether to include vector embeddings in the response

        Returns:
            dict: List of document chunks and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
            "include_vectors": include_vectors,
        }

        return await self.client._make_request(
            "GET", f"documents/{str(id)}/chunks", params=params
        )

    async def list_collections(
        self,
        id: Union[str, UUID],
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        include_vectors: Optional[bool] = False,
    ) -> dict:
        """
        Get chunks for a specific document.

        Args:
            id (Union[str, UUID]): ID of document to retrieve chunks for
            offset (Optional[int]): Pagination offset
            limit (Optional[int]): Maximum number of chunks to return
            include_vectors (Optional[bool]): Whether to include vector embeddings in the response

        Returns:
            dict: List of document chunks and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
            "include_vectors": include_vectors,
        }

        return await self.client._make_request(
            "GET", f"documents/{str(id)}/collections", params=params
        )

    async def delete_by_filter(
        self,
        filters: Dict[str, Any],
    ) -> None:
        """
        Delete documents based on filters.

        Args:
            filters (Dict[str, Any]): Filters to apply when selecting documents to delete
        """
        filters_json = json.dumps(filters)
        await self.client._make_request(
            "DELETE", "documents/by-filter", params={"filters": filters_json}
        )


class SyncDocumentSDK:
    """Synchronous wrapper for DocumentsSDK"""

    def __init__(self, async_sdk: DocumentsSDK):
        self._async_sdk = async_sdk

        # Get all attributes from the instance
        for name in dir(async_sdk):
            if not name.startswith("_"):  # Skip private methods
                attr = getattr(async_sdk, name)
                # Check if it's a method and if it's async
                if callable(attr) and (
                    iscoroutinefunction(attr) or isasyncgenfunction(attr)
                ):
                    if isasyncgenfunction(attr):
                        setattr(self, name, sync_generator_wrapper(attr))
                    else:
                        setattr(self, name, sync_wrapper(attr))
