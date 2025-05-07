import json
import os
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

import requests

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

from ..models import (
    GraphCreationSettings,
    IngestionMode,
    SearchMode,
    SearchSettings,
)


class DocumentsSDK:
    """SDK for interacting with documents in the v3 API."""

    def __init__(self, client):
        self.client = client

    def create(
        self,
        file_path: Optional[str] = None,
        raw_text: Optional[str] = None,
        chunks: Optional[list[str]] = None,
        s3_url: Optional[str] = None,
        id: Optional[str | UUID] = None,
        ingestion_mode: Optional[IngestionMode | str] = None,
        collection_ids: Optional[list[str | UUID]] = None,
        metadata: Optional[dict[str, Any]] = None,
        ingestion_config: Optional[dict | IngestionMode] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedIngestionResponse:
        """Create a new document from either a file, raw text, or chunks.

        Args:
            file_path (Optional[str]): The path to the file to upload, if any.
            raw_text (Optional[str]): Raw text content to upload, if no file path is provided.
            chunks (Optional[list[str]]): Pre-processed text chunks to ingest.
            s3_url (Optional[str]): A presigned S3 URL to upload the file from, if any.
            id (Optional[str | UUID]): Optional ID to assign to the document.
            ingestion_mode (Optional[IngestionMode | str]): The ingestion mode preset ('hi-res', 'ocr', 'fast', 'custom'). Defaults to 'custom'.
            collection_ids (Optional[list[str | UUID]]): Collection IDs to associate. Defaults to user's default collection if None.
            metadata (Optional[dict]): Optional metadata to assign to the document.
            ingestion_config (Optional[dict | IngestionMode]): Optional ingestion config or preset mode enum. Used when ingestion_mode='custom'.
            run_with_orchestration (Optional[bool]): Whether to run with orchestration (default: True).

        Returns:
            WrappedIngestionResponse
        """
        if (
            sum(x is not None for x in [file_path, raw_text, chunks, s3_url])
            != 1
        ):
            raise ValueError(
                "Exactly one of file_path, raw_text, chunks, or s3_url must be provided."
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
            ]
            data["collection_ids"] = json.dumps(collection_ids)
        if run_with_orchestration is not None:
            data["run_with_orchestration"] = str(run_with_orchestration)
        if ingestion_mode is not None:
            data["ingestion_mode"] = (
                ingestion_mode.value
                if isinstance(ingestion_mode, IngestionMode)
                else ingestion_mode
            )
        if file_path:
            # Create a new file instance that will remain open during the request
            file_instance = open(file_path, "rb")
            filename = os.path.basename(file_path)
            files = [
                (
                    "file",
                    (filename, file_instance, "application/octet-stream"),
                )
            ]
            try:
                response_dict = self.client._make_request(
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
            data["raw_text"] = raw_text
            response_dict = self.client._make_request(
                "POST",
                "documents",
                data=data,
                version="v3",
            )
        elif chunks:
            data["chunks"] = json.dumps(chunks)
            response_dict = self.client._make_request(
                "POST",
                "documents",
                data=data,
                version="v3",
            )
        elif s3_url:
            try:
                s3_file = requests.get(s3_url)
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file_path = temp_file.name
                    temp_file.write(s3_file.content)

                # Get the filename from the URL
                filename = os.path.basename(s3_url.split("?")[0]) or "s3_file"
                with open(temp_file_path, "rb") as file_instance:
                    files = [
                        (
                            "file",
                            (
                                filename,
                                file_instance,
                                "application/octet-stream",
                            ),
                        )
                    ]
                    response_dict = self.client._make_request(
                        "POST",
                        "documents",
                        data=data,
                        files=files,
                        version="v3",
                    )
            except requests.RequestException as e:
                raise ValueError(
                    f"Failed to download file from S3 URL: {s3_url}"
                ) from e
            finally:
                # Clean up the temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        return WrappedIngestionResponse(**response_dict)

    def append_metadata(
        self,
        id: str | UUID,
        metadata: list[dict[str, Any]],
    ) -> WrappedDocumentResponse:
        """Append metadata to a document.

        Args:
            id (str | UUID): ID of document to append metadata to
            metadata (list[dict]): Metadata to append

        Returns:
            WrappedDocumentResponse
        """
        data = json.dumps(metadata)
        response_dict = self.client._make_request(
            "PATCH",
            f"documents/{str(id)}/metadata",
            data=data,
            version="v3",
        )

        return WrappedDocumentResponse(**response_dict)

    def replace_metadata(
        self,
        id: str | UUID,
        metadata: list[dict[str, Any]],
    ) -> WrappedDocumentResponse:
        """Replace metadata for a document.

        Args:
            id (str | UUID): ID of document to replace metadata for
            metadata (list[dict]): The metadata that will replace the existing metadata

        Returns:
            WrappedDocumentResponse
        """
        data = json.dumps(metadata)
        response_dict = self.client._make_request(
            "PUT",
            f"documents/{str(id)}/metadata",
            data=data,
            version="v3",
        )

        return WrappedDocumentResponse(**response_dict)

    def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedDocumentResponse:
        """Get a specific document by ID.

        Args:
            id (str | UUID): ID of document to retrieve

        Returns:
            WrappedDocumentResponse
        """
        response_dict = self.client._make_request(
            "GET",
            f"documents/{str(id)}",
            version="v3",
        )

        return WrappedDocumentResponse(**response_dict)

    def download(
        self,
        id: str | UUID,
    ) -> BytesIO:
        """Download a document's original file content.

        Args:
            id (str | UUID): ID of document to download

        Returns:
            BytesIO: In-memory bytes buffer containing the document's file content.
        """
        response = self.client._make_request(
            "GET",
            f"documents/{str(id)}/download",
            version="v3",
        )
        if not isinstance(response, BytesIO):
            raise ValueError(
                f"Expected BytesIO response, got {type(response)}"
            )
        return response

    def download_zip(
        self,
        document_ids: Optional[list[str | UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        output_path: Optional[str | Path] = None,
    ) -> Optional[BytesIO]:
        """Download multiple documents as a zip file.

        Args:
            document_ids (Optional[list[str | UUID]]): IDs to include. May be required for non-superusers.
            start_date (Optional[datetime]): Filter documents created on or after this date.
            end_date (Optional[datetime]): Filter documents created on or before this date.
            output_path (Optional[str | Path]): If provided, save the zip file to this path and return None. Otherwise, return BytesIO.

        Returns:
            Optional[BytesIO]: BytesIO object with zip content if output_path is None, else None.
        """
        params: dict[str, Any] = {}
        if document_ids:
            params["document_ids"] = [str(doc_id) for doc_id in document_ids]
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()

        response = self.client._make_request(
            "GET",
            "documents/download_zip",
            params=params,
            version="v3",
        )

        if not isinstance(response, BytesIO):
            raise ValueError(
                f"Expected BytesIO response, got {type(response)}"
            )

        if output_path:
            output_path = (
                Path(output_path)
                if isinstance(output_path, str)
                else output_path
            )
            with open(output_path, "wb") as f:
                f.write(response.getvalue())
            return None

        return response

    def export(
        self,
        output_path: str | Path,
        columns: Optional[list[str]] = None,
        filters: Optional[dict[str, Any]] = None,
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
        output_path = (
            str(output_path) if isinstance(output_path, Path) else output_path
        )

        data: dict[str, Any] = {"include_header": include_header}
        if columns:
            data["columns"] = columns
        if filters:
            data["filters"] = filters

        with open(output_path, "wb") as f:
            response = self.client.client.post(
                f"{self.client.base_url}/v3/documents/export",
                json=data,
                headers={
                    "Accept": "text/csv",
                    **self.client._get_auth_header(),
                },
            )
            if response.status_code != 200:
                raise ValueError(
                    f"Export failed with status {response.status_code}",
                    response,
                )

            for chunk in response.iter_bytes():
                if chunk:
                    f.write(chunk)

    def export_entities(
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
        with open(output_path, "wb") as f:
            response = self.client.client.post(
                f"{self.client.base_url}/v3/documents/{str(id)}/entities/export",
                json=data,
                headers={
                    "Accept": "text/csv",
                    **self.client._get_auth_header(),
                },
            )
            if response.status_code != 200:
                raise ValueError(
                    f"Export failed with status {response.status_code}",
                    response,
                )

            for chunk in response.iter_bytes():
                if chunk:
                    f.write(chunk)

    def export_relationships(
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
        with open(output_path, "wb") as f:
            response = self.client.client.post(
                f"{self.client.base_url}/v3/documents/{str(id)}/relationships/export",
                json=data,
                headers={
                    "Accept": "text/csv",
                    **self.client._get_auth_header(),
                },
            )
            if response.status_code != 200:
                raise ValueError(
                    f"Export failed with status {response.status_code}",
                    response,
                )

            for chunk in response.iter_bytes():
                if chunk:
                    f.write(chunk)

    def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Delete a specific document.

        Args:
            id (str | UUID): ID of document to delete

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "DELETE",
            f"documents/{str(id)}",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    def list_chunks(
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
        response_dict = self.client._make_request(
            "GET",
            f"documents/{str(id)}/chunks",
            params=params,
            version="v3",
        )

        return WrappedChunksResponse(**response_dict)

    def list_collections(
        self,
        id: str | UUID,
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

        response_dict = self.client._make_request(
            "GET",
            f"documents/{str(id)}/collections",
            params=params,
            version="v3",
        )

        return WrappedCollectionsResponse(**response_dict)

    def delete_by_filter(
        self,
        filters: dict[str, Any],
    ) -> WrappedBooleanResponse:
        """Delete documents based on metadata filters.

        Args:
            filters (dict): Filters to apply (e.g., `{"metadata.year": {"$lt": 2020}}`).

        Returns:
            WrappedBooleanResponse
        """
        filters_json = json.dumps(filters)
        response_dict = self.client._make_request(
            "DELETE",
            "documents/by-filter",
            data=filters_json,
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    def extract(
        self,
        id: str | UUID,
        settings: Optional[dict | GraphCreationSettings] = None,
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

        response_dict = self.client._make_request(
            "POST",
            f"documents/{str(id)}/extract",
            params=data,
            version="v3",
        )

        return WrappedGenericMessageResponse(**response_dict)

    def list_entities(
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
        response_dict = self.client._make_request(
            "GET",
            f"documents/{str(id)}/entities",
            params=params,
            version="v3",
        )

        return WrappedEntitiesResponse(**response_dict)

    def list_relationships(
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

        response_dict = self.client._make_request(
            "GET",
            f"documents/{str(id)}/relationships",
            params=params,
            version="v3",
        )

        return WrappedRelationshipsResponse(**response_dict)

    def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        include_summary_embeddings: Optional[bool] = False,
        owner_only: Optional[bool] = False,
    ) -> WrappedDocumentsResponse:
        """List documents with pagination.

        Args:
            ids (Optional[list[str | UUID]]): Optional list of document IDs to filter by.
            offset (int, optional): Number of objects to skip. Defaults to 0.
            limit (int, optional): Max number of objects to return (1-1000). Defaults to 100.
            include_summary_embeddings (Optional[bool]): Whether to include summary embeddings (default: False).
            owner_only (Optional[bool]): If true, only returns documents owned by the user, not all accessible documents.

        Returns:
            WrappedDocumentsResponse
        """
        params: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
            "include_summary_embeddings": include_summary_embeddings,
            "owner_only": owner_only,
        }
        if ids:
            params["ids"] = [str(doc_id) for doc_id in ids]

        response_dict = self.client._make_request(
            "GET",
            "documents",
            params=params,
            version="v3",
        )

        return WrappedDocumentsResponse(**response_dict)

    def search(
        self,
        query: str,
        search_mode: Optional[str | SearchMode] = SearchMode.custom,
        search_settings: Optional[dict | SearchSettings] = None,
    ) -> WrappedDocumentSearchResponse:
        """Conduct a search query on document summaries.

        Note: Access control (based on user ownership/collection access) is applied to search results.

        Args:
            query (str): The search query.
            search_mode (Optional[str | SearchMode]): Search mode ('basic', 'advanced', 'custom'). Defaults to 'custom'.
            search_settings (Optional[dict | SearchSettings]): Search settings (filters, limits, hybrid options, etc.).

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

        response_dict = self.client._make_request(
            "POST",
            "documents/search",
            json=data,
            version="v3",
        )

        return WrappedDocumentSearchResponse(**response_dict)

    def deduplicate(
        self,
        id: str | UUID,
        settings: Optional[dict | GraphCreationSettings] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedGenericMessageResponse:
        """Deduplicate entities and relationships from a document.

        Args:
            id (str | UUID): ID of document to deduplicate entities for.
            settings (Optional[dict | GraphCreationSettings]): Settings for deduplication process.
            run_with_orchestration (Optional[bool]): Whether to run with orchestration (default: True).

        Returns:
            WrappedGenericMessageResponse: Indicating task status.
        """
        data: dict[str, Any] = {}
        if settings:
            data["settings"] = json.dumps(settings)
        if run_with_orchestration is not None:
            data["run_with_orchestration"] = run_with_orchestration

        response_dict = self.client._make_request(
            "POST",
            f"documents/{str(id)}/deduplicate",
            params=data,
            version="v3",
        )

        return WrappedGenericMessageResponse(**response_dict)
