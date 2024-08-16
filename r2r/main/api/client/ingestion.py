import json
import os
import uuid
from contextlib import ExitStack
from typing import List, Optional, Union

from r2r.base import ChunkingConfig, Document, DocumentType


class IngestionMethods:
    @staticmethod
    async def ingest_documents(
        client,
        documents: List[Document],
        versions: Optional[List[str]] = None,
        chunking_config_override: Optional[Union[dict, ChunkingConfig]] = None,
    ) -> dict:
        """
        Ingest a list of documents into the system.

        Args:
            documents (List[Document]): List of Document objects to ingest.
            versions (Optional[List[str]]): List of version strings for each document.
            chunking_config_override (Optional[Union[dict, ChunkingConfig]]): Custom chunking configuration.

        Returns:
            dict: Ingestion results containing processed, failed, and skipped documents.
        """
        data = {
            "documents": [doc.dict() for doc in documents],
            "versions": versions,
            "chunking_config_override": (
                chunking_config_override.dict()
                if isinstance(chunking_config_override, ChunkingConfig)
                else chunking_config_override
            ),
        }
        return await client._make_request(
            "POST", "ingest_documents", json=data
        )

    @staticmethod
    async def ingest_files(
        client,
        file_paths: List[str],
        metadatas: Optional[List[dict]] = None,
        document_ids: Optional[List[Union[uuid.UUID, str]]] = None,
        versions: Optional[List[str]] = None,
        chunking_config_override: Optional[Union[dict, ChunkingConfig]] = None,
    ) -> dict:
        """
        Ingest files into the system.

        Args:
            file_paths (List[str]): List of file paths to ingest.
            metadatas (Optional[List[dict]]): List of metadata dictionaries for each file.
            document_ids (Optional[List[Union[uuid.UUID, str]]]): List of document IDs.
            versions (Optional[List[str]]): List of version strings for each file.
            chunking_config_override (Optional[Union[dict, ChunkingConfig]]): Custom chunking configuration.

        Returns:
            dict: Ingestion results containing processed, failed, and skipped documents.
        """
        all_file_paths = []
        for path in file_paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    all_file_paths.extend(
                        os.path.join(root, file) for file in files
                    )
            else:
                all_file_paths.append(path)

        with ExitStack() as stack:
            files = [
                (
                    "files",
                    (
                        os.path.basename(file),
                        stack.enter_context(open(file, "rb")),
                        "application/octet-stream",
                    ),
                )
                for file in all_file_paths
            ]

            data = {
                "metadatas": json.dumps(metadatas) if metadatas else None,
                "document_ids": (
                    json.dumps([str(doc_id) for doc_id in document_ids])
                    if document_ids
                    else None
                ),
                "versions": json.dumps(versions) if versions else None,
                "chunking_config_override": (
                    json.dumps(
                        chunking_config_override.dict()
                        if isinstance(chunking_config_override, ChunkingConfig)
                        else chunking_config_override
                    )
                    if chunking_config_override
                    else None
                ),
            }

            return await client._make_request(
                "POST", "ingest_files", data=data, files=files
            )

    @staticmethod
    async def update_files(
        client,
        file_paths: List[str],
        document_ids: List[str],
        metadatas: Optional[List[dict]] = None,
        chunking_config_override: Optional[Union[dict, ChunkingConfig]] = None,
    ) -> dict:
        """
        Update existing files in the system.

        Args:
            file_paths (List[str]): List of file paths to update.
            document_ids (List[str]): List of document IDs to update.
            metadatas (Optional[List[dict]]): List of updated metadata dictionaries for each file.
            chunking_config_override (Optional[Union[dict, ChunkingConfig]]): Custom chunking configuration.

        Returns:
            dict: Update results containing processed, failed, and skipped documents.
        """
        if len(file_paths) != len(document_ids):
            raise ValueError(
                "Number of file paths must match number of document IDs."
            )

        with ExitStack() as stack:
            files = [
                (
                    "files",
                    (
                        os.path.basename(file),
                        stack.enter_context(open(file, "rb")),
                        "application/octet-stream",
                    ),
                )
                for file in file_paths
            ]

            data = {
                "document_ids": json.dumps(document_ids),
                "metadatas": json.dumps(metadatas) if metadatas else None,
                "chunking_config_override": (
                    json.dumps(
                        chunking_config_override.dict()
                        if isinstance(chunking_config_override, ChunkingConfig)
                        else chunking_config_override
                    )
                    if chunking_config_override
                    else None
                ),
            }

            return await client._make_request(
                "POST", "update_files", data=data, files=files
            )

    @staticmethod
    async def get_document_info(client, document_id: str) -> dict:
        """
        Retrieve information about a specific document.

        Args:
            document_id (str): The ID of the document to retrieve information for.

        Returns:
            dict: Document information including metadata, status, and version.
        """
        return await client._make_request(
            "GET", f"document_info/{document_id}"
        )

    @staticmethod
    async def delete_document(client, document_id: str) -> dict:
        """
        Delete a specific document from the system.

        Args:
            document_id (str): The ID of the document to delete.

        Returns:
            dict: Confirmation of document deletion.
        """
        return await client._make_request(
            "DELETE", f"delete_document/{document_id}"
        )

    @staticmethod
    async def list_documents(
        client,
        user_id: Optional[str] = None,
        group_ids: Optional[List[str]] = None,
        document_type: Optional[DocumentType] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """
        List documents based on various filters.

        Args:
            user_id (Optional[str]): Filter by user ID.
            group_ids (Optional[List[str]]): Filter by group IDs.
            document_type (Optional[DocumentType]): Filter by document type.
            status (Optional[str]): Filter by document status.
            page (int): Page number for pagination.
            page_size (int): Number of items per page.

        Returns:
            dict: List of documents matching the specified filters.
        """
        params = {
            "user_id": user_id,
            "group_ids": json.dumps(group_ids) if group_ids else None,
            "document_type": document_type.value if document_type else None,
            "status": status,
            "page": page,
            "page_size": page_size,
        }
        return await client._make_request(
            "GET", "list_documents", params=params
        )
