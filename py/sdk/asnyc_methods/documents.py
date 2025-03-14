import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

import aiofiles

from shared.api.models import (
    WrappedBooleanResponse,
    WrappedChunksResponse,
    WrappedCollectionsResponse,
    WrappedDocumentResponse,
    WrappedDocumentSearchResponse,
    WrappedDocumentsResponse,
    WrappedEntitiesResponse,
    WrappedGenericMessageResponse,
    WrappedIngestionResponse,
    WrappedRelationshipsResponse,
)

from ..models import IngestionMode, SearchMode, SearchSettings


class DocumentsSDK:
    """SDK for interacting with documents in the v3 API."""

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        file_path: Optional[str] = None,
        raw_text: Optional[str] = None,
        chunks: Optional[list[str]] = None,
        id: Optional[str | UUID] = None,
        ingestion_mode: Optional[str] = None,
        collection_ids: Optional[list[str | UUID]] = None,
        metadata: Optional[dict] = None,
        ingestion_config: Optional[dict | IngestionMode] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedIngestionResponse:
        """Create a new document from either a file or content.

        Args:
            file_path (Optional[str]): The file to upload, if any
            content (Optional[str]): Optional text content to upload, if no file path is provided
            id (Optional[str | UUID]): Optional ID to assign to the document
            collection_ids (Optional[list[str | UUID]]): Collection IDs to associate with the document. If none are provided, the document will be assigned to the user's default collection.
            metadata (Optional[dict]): Optional metadata to assign to the document
            ingestion_config (Optional[dict]): Optional ingestion configuration to use
            run_with_orchestration (Optional[bool]): Whether to run with orchestration

        Returns:
            WrappedIngestionResponse
        """
        if not file_path and not raw_text and not chunks:
            raise ValueError(
                "Either `file_path`, `raw_text` or `chunks` must be provided"
            )
        if (
            (file_path and raw_text)
            or (file_path and chunks)
            or (raw_text and chunks)
        ):
            raise ValueError(
                "Only one of `file_path`, `raw_text` or `chunks` may be provided"
            )

        data: dict[str, Any] = {}
        files = None

        if id:
            data["id"] = str(id)
        if metadata:
            data["metadata"] = json.dumps(metadata)
        if ingestion_config:
            if isinstance(ingestion_config, IngestionMode):
                ingestion_config = {"mode": ingestion_config.value}
            app_config: dict[str, Any] = (
                {}
                if isinstance(ingestion_config, dict)
                else ingestion_config["app"]
            )
            ingestion_config = dict(ingestion_config)
            ingestion_config["app"] = app_config
            data["ingestion_config"] = json.dumps(ingestion_config)
        if collection_ids:
            collection_ids = [
                str(collection_id) for collection_id in collection_ids
            ]  # type: ignore
            data["collection_ids"] = json.dumps(collection_ids)
        if run_with_orchestration is not None:
            data["run_with_orchestration"] = str(run_with_orchestration)
        if ingestion_mode is not None:
            data["ingestion_mode"] = ingestion_mode
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
                response_dict = await self.client._make_request(
                    "POST",
                    "documents",
                    data=data,
                    files=files,
                    version="v3",
                )
            finally:
                # Ensure we close the file after the request is complete
                file_instance.close()
        elif raw_text:
            data["raw_text"] = raw_text  # type: ignore
            response_dict = await self.client._make_request(
                "POST",
                "documents",
                data=data,
                version="v3",
            )
        else:
            data["chunks"] = json.dumps(chunks)
            response_dict = await self.client._make_request(
                "POST",
                "documents",
                data=data,
                version="v3",
            )

        return WrappedIngestionResponse(**response_dict)

    async def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedDocumentResponse:
        """Get a specific document by ID.

        Args:
            id (str | UUID): ID of document to retrieve

        Returns:
            WrappedDocumentResponse
        """
        response_dict = await self.client._make_request(
            "GET",
            f"documents/{str(id)}",
            version="v3",
        )

        return WrappedDocumentResponse(**response_dict)

    async def download(
        self,
        id: str | UUID,
    ) -> BytesIO:
        response = await self.client._make_request(
            "GET",
            f"documents/{str(id)}/download",
            version="v3",
        )
        if not isinstance(response, BytesIO):
            raise ValueError("Expected BytesIO response")
        return response

    async def download_zip(
        self,
        document_ids: Optional[list[str | UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        output_path: Optional[str | Path] = None,
    ) -> BytesIO | None:
        """Download multiple documents as a zip file."""
        params: dict[str, Any] = {}
        if document_ids:
            params["document_ids"] = [str(doc_id) for doc_id in document_ids]
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()

        response = await self.client._make_request(
            "GET",
            "documents/download_zip",
            params=params,
            version="v3",
        )

        if not isinstance(response, BytesIO):
            raise ValueError("Expected BytesIO response")

        if output_path:
            output_path = (
                Path(output_path)
                if isinstance(output_path, str)
                else output_path
            )
            async with aiofiles.open(output_path, "wb") as f:
                await f.write(response.getvalue())
            return None

        return response

    async def export(
        self,
        output_path: str | Path,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> None:
        """Export documents to a CSV file, streaming the results directly to
        disk.

        Args:
            output_path (str | Path): Local path where the CSV file should be saved
            columns (Optional[list[str]]): Specific columns to export. If None, exports default columns
            filters (Optional[dict]): Optional filters to apply when selecting documents
            include_header (bool): Whether to include column headers in the CSV (default: True)

        Returns:
            None
        """
        # Convert path to string if it's a Path object
        output_path = (
            str(output_path) if isinstance(output_path, Path) else output_path
        )

        data: dict[str, Any] = {"include_header": include_header}
        if columns:
            data["columns"] = columns
        if filters:
            data["filters"] = filters

        # Stream response directly to file
        async with aiofiles.open(output_path, "wb") as f:
            async with self.client.session.post(
                f"{self.client.base_url}/v3/documents/export",
                json=data,
                headers={
                    "Accept": "text/csv",
                    **self.client._get_auth_header(),
                },
            ) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Export failed with status {response.status}",
                        response,
                    )

                async for chunk in response.content.iter_chunks():
                    if chunk:
                        await f.write(chunk[0])

    async def export_entities(
        self,
        id: str | UUID,
        output_path: str | Path,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> None:
        """Export documents to a CSV file, streaming the results directly to
        disk.

        Args:
            output_path (str | Path): Local path where the CSV file should be saved
            columns (Optional[list[str]]): Specific columns to export. If None, exports default columns
            filters (Optional[dict]): Optional filters to apply when selecting documents
            include_header (bool): Whether to include column headers in the CSV (default: True)

        Returns:
            None
        """
        # Convert path to string if it's a Path object
        output_path = (
            str(output_path) if isinstance(output_path, Path) else output_path
        )

        # Prepare request data
        data: dict[str, Any] = {"include_header": include_header}
        if columns:
            data["columns"] = columns
        if filters:
            data["filters"] = filters

        # Stream response directly to file
        async with aiofiles.open(output_path, "wb") as f:
            async with self.client.session.post(
                f"{self.client.base_url}/v3/documents/{str(id)}/entities/export",
                json=data,
                headers={
                    "Accept": "text/csv",
                    **self.client._get_auth_header(),
                },
            ) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Export failed with status {response.status}",
                        response,
                    )

                async for chunk in response.content.iter_chunks():
                    if chunk:
                        await f.write(chunk[0])

    async def export_relationships(
        self,
        id: str | UUID,
        output_path: str | Path,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> None:
        """Export document relationships to a CSV file, streaming the results
        directly to disk.

        Args:
            output_path (str | Path): Local path where the CSV file should be saved
            columns (Optional[list[str]]): Specific columns to export. If None, exports default columns
            filters (Optional[dict]): Optional filters to apply when selecting documents
            include_header (bool): Whether to include column headers in the CSV (default: True)

        Returns:
            None
        """
        # Convert path to string if it's a Path object
        output_path = (
            str(output_path) if isinstance(output_path, Path) else output_path
        )

        # Prepare request data
        data: dict[str, Any] = {"include_header": include_header}
        if columns:
            data["columns"] = columns
        if filters:
            data["filters"] = filters

        # Stream response directly to file
        async with aiofiles.open(output_path, "wb") as f:
            async with self.client.session.post(
                f"{self.client.base_url}/v3/documents/{str(id)}/relationships/export",
                json=data,
                headers={
                    "Accept": "text/csv",
                    **self.client._get_auth_header(),
                },
            ) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Export failed with status {response.status}",
                        response,
                    )

                async for chunk in response.content.iter_chunks():
                    if chunk:
                        await f.write(chunk[0])

    async def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Delete a specific document.

        Args:
            id (str | UUID): ID of document to delete

        Returns:
            WrappedBooleanResponse
        """
        response_dict = await self.client._make_request(
            "DELETE",
            f"documents/{str(id)}",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    async def list_chunks(
        self,
        id: str | UUID,
        include_vectors: Optional[bool] = False,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedChunksResponse:
        """Get chunks for a specific document.

        Args:
            id (str | UUID): ID of document to retrieve chunks for
            include_vectors (Optional[bool]): Whether to include vector embeddings in the response
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedChunksResponse
        """
        params = {
            "offset": offset,
            "limit": limit,
            "include_vectors": include_vectors,
        }
        response_dict = await self.client._make_request(
            "GET",
            f"documents/{str(id)}/chunks",
            params=params,
            version="v3",
        )

        return WrappedChunksResponse(**response_dict)

    async def list_collections(
        self,
        id: str | UUID,
        include_vectors: Optional[bool] = False,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedCollectionsResponse:
        """List collections for a specific document.

        Args:
            id (str | UUID): ID of document to retrieve collections for
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedCollectionsResponse
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        response_dict = await self.client._make_request(
            "GET",
            f"documents/{str(id)}/collections",
            params=params,
            version="v3",
        )

        return WrappedCollectionsResponse(**response_dict)

    async def delete_by_filter(
        self,
        filters: dict,
    ) -> WrappedBooleanResponse:
        """Delete documents based on filters.

        Args:
            filters (dict): Filters to apply when selecting documents to delete

        Returns:
            WrappedBooleanResponse
        """
        filters_json = json.dumps(filters)
        response_dict = await self.client._make_request(
            "DELETE",
            "documents/by-filter",
            data=filters_json,
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    async def extract(
        self,
        id: str | UUID,
        settings: Optional[dict] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedGenericMessageResponse:
        """Extract entities and relationships from a document.

        Args:
            id (str, UUID): ID of document to extract from
            settings (Optional[dict]): Settings for extraction process
            run_with_orchestration (Optional[bool]): Whether to run with orchestration

        Returns:
            WrappedGenericMessageResponse
        """
        data: dict[str, Any] = {}
        if settings:
            data["settings"] = json.dumps(settings)
        if run_with_orchestration is not None:
            data["run_with_orchestration"] = str(run_with_orchestration)

        response_dict = await self.client._make_request(
            "POST",
            f"documents/{str(id)}/extract",
            params=data,
            version="v3",
        )
        return WrappedGenericMessageResponse(**response_dict)

    async def list_entities(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        include_embeddings: Optional[bool] = False,
    ) -> WrappedEntitiesResponse:
        """List entities extracted from a document.

        Args:
            id (str | UUID): ID of document to get entities from
            offset (Optional[int]): Number of items to skip
            limit (Optional[int]): Max number of items to return
            include_embeddings (Optional[bool]): Whether to include embeddings

        Returns:
            WrappedEntitiesResponse
        """
        params = {
            "offset": offset,
            "limit": limit,
            "include_embeddings": include_embeddings,
        }
        response_dict = await self.client._make_request(
            "GET",
            f"documents/{str(id)}/entities",
            params=params,
            version="v3",
        )

        return WrappedEntitiesResponse(**response_dict)

    async def list_relationships(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        entity_names: Optional[list[str]] = None,
        relationship_types: Optional[list[str]] = None,
    ) -> WrappedRelationshipsResponse:
        """List relationships extracted from a document.

        Args:
            id (str | UUID): ID of document to get relationships from
            offset (Optional[int]): Number of items to skip
            limit (Optional[int]): Max number of items to return
            entity_names (Optional[list[str]]): Filter by entity names
            relationship_types (Optional[list[str]]): Filter by relationship types

        Returns:
            WrappedRelationshipsResponse
        """
        params: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
        }
        if entity_names:
            params["entity_names"] = entity_names
        if relationship_types:
            params["relationship_types"] = relationship_types

        response_dict = await self.client._make_request(
            "GET",
            f"documents/{str(id)}/relationships",
            params=params,
            version="v3",
        )

        return WrappedRelationshipsResponse(**response_dict)

    async def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedDocumentsResponse:
        """List documents with pagination.

        Args:
            ids (Optional[list[str | UUID]]): Optional list of document IDs to filter by
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedDocumentsResponse
        """
        params = {
            "offset": offset,
            "limit": limit,
        }
        if ids:
            params["ids"] = [str(doc_id) for doc_id in ids]  # type: ignore

        response_dict = await self.client._make_request(
            "GET",
            "documents",
            params=params,
            version="v3",
        )

        return WrappedDocumentsResponse(**response_dict)

    async def search(
        self,
        query: str,
        search_mode: Optional[str | SearchMode] = "custom",
        search_settings: Optional[dict | SearchSettings] = None,
    ) -> WrappedDocumentSearchResponse:
        """Conduct a vector and/or graph search.

        Args:
            query (str): The query to search for.
            search_settings (Optional[dict, SearchSettings]]): Vector search settings.

        Returns:
            WrappedDocumentSearchResponse
        """
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()
        data: dict[str, Any] = {
            "query": query,
            "search_settings": search_settings,
        }
        if search_mode:
            data["search_mode"] = search_mode

        response_dict = await self.client._make_request(
            "POST",
            "documents/search",
            json=data,
            version="v3",
        )

        return WrappedDocumentSearchResponse(**response_dict)

    async def deduplicate(
        self,
        id: str | UUID,
        settings: Optional[dict] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedGenericMessageResponse:
        """Deduplicate entities and relationships from a document.

        Args:
            id (str, UUID): ID of document to extract from
            settings (Optional[dict]): Settings for extraction process
            run_with_orchestration (Optional[bool]): Whether to run with orchestration

        Returns:
            WrappedGenericMessageResponse
        """
        data: dict[str, Any] = {}
        if settings:
            data["settings"] = json.dumps(settings)
        if run_with_orchestration is not None:
            data["run_with_orchestration"] = str(run_with_orchestration)

        response_dict = await self.client._make_request(
            "POST",
            f"documents/{str(id)}/deduplicate",
            params=data,
            version="v3",
        )

        return WrappedGenericMessageResponse(**response_dict)
