from __future__ import annotations  # for Python 3.10+

import json
import os
from contextlib import ExitStack
from typing import Optional, Union
from uuid import UUID

from typing_extensions import deprecated

from shared.abstractions import IndexMeasure, IndexMethod, VectorTableName


class IngestionMixins:
    @deprecated("Use client.documents.create() instead")
    async def ingest_files(
        self,
        file_paths: list[str],
        document_ids: Optional[list[Union[str, UUID]]] = None,
        metadatas: Optional[list[dict]] = None,
        ingestion_config: Optional[dict] = None,
        collection_ids: Optional[list[list[Union[str, UUID]]]] = None,
        run_with_orchestration: Optional[bool] = None,
    ) -> dict:
        """
        Ingest files into your R2R deployment

        Args:
            file_paths (List[str]): List of file paths to ingest.
            document_ids (Optional[List[str]]): List of document IDs.
            metadatas (Optional[List[dict]]): List of metadata dictionaries for each file.
            ingestion_config (Optional[Union[dict]]): Custom chunking configuration.

        Returns:
            dict: Ingestion results containing processed, failed, and skipped documents.
        """
        if document_ids is not None and len(file_paths) != len(document_ids):
            raise ValueError(
                "Number of file paths must match number of document IDs."
            )
        if metadatas is not None and len(file_paths) != len(metadatas):
            raise ValueError(
                "Number of metadatas must match number of document IDs."
            )

        with ExitStack() as stack:
            all_file_paths: list[str] = []
            for path in file_paths:
                if os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        all_file_paths.extend(
                            os.path.join(root, file) for file in files
                        )
                else:
                    all_file_paths.append(path)

            with ExitStack() as stack:
                files_tuples = [
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

                data = {}
                if document_ids:
                    data["document_ids"] = json.dumps(
                        [str(doc_id) for doc_id in document_ids]
                    )
                if metadatas:
                    data["metadatas"] = json.dumps(metadatas)

                if ingestion_config:
                    data["ingestion_config"] = json.dumps(ingestion_config)

                if run_with_orchestration is not None:
                    data["run_with_orchestration"] = str(
                        run_with_orchestration
                    )

                if collection_ids:
                    data["collection_ids"] = json.dumps(
                        [
                            [
                                str(collection_id)
                                for collection_id in doc_collection_ids
                            ]
                            for doc_collection_ids in collection_ids
                        ]
                    )

                return await self._make_request(  # type: ignore
                    "POST", "ingest_files", data=data, files=files_tuples
                )

    @deprecated("Use client.documents.update() instead")
    async def update_files(
        self,
        file_paths: list[str],
        document_ids: Optional[list[Union[str, UUID]]] = None,
        metadatas: Optional[list[dict]] = None,
        ingestion_config: Optional[dict] = None,
        collection_ids: Optional[list[list[Union[str, UUID]]]] = None,
        run_with_orchestration: Optional[bool] = None,
    ) -> dict:
        """
        Update existing files in your R2R deployment.

        Args:
            file_paths (List[str]): List of file paths to update.
            document_ids (List[str]): List of document IDs to update.
            metadatas (Optional[List[dict]]): List of updated metadata dictionaries for each file.
            ingestion_config (Optional[Union[dict]]): Custom chunking configuration.

        Returns:
            dict: Update results containing processed, failed, and skipped documents.
        """
        if document_ids is not None and len(file_paths) != len(document_ids):
            raise ValueError(
                "Number of file paths must match number of document IDs."
            )
        if metadatas is not None and len(file_paths) != len(metadatas):
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

            data = {}
            if document_ids:
                data["document_ids"] = json.dumps(
                    [str(doc_id) for doc_id in document_ids]
                )
            if metadatas:
                data["metadatas"] = json.dumps(metadatas)
            if ingestion_config:
                data["ingestion_config"] = json.dumps(ingestion_config)

            if run_with_orchestration is not None:
                data["run_with_orchestration"] = str(run_with_orchestration)

            if collection_ids:
                data["collection_ids"] = json.dumps(
                    [
                        [
                            str(collection_id)
                            for collection_id in doc_collection_ids
                        ]
                        for doc_collection_ids in collection_ids
                    ]
                )
            return await self._make_request(  # type: ignore
                "POST", "update_files", data=data, files=files
            )

    @deprecated("Use client.chunks.create() instead")
    async def ingest_chunks(
        self,
        chunks: list[dict],
        document_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
        collection_ids: Optional[list[list[Union[str, UUID]]]] = None,
        run_with_orchestration: Optional[bool] = None,
    ) -> dict:
        """
        Ingest files into your R2R deployment

        Args:
            chunks (List[dict]): List of dictionaries containing chunk data.
            document_id (Optional[UUID]): The ID of the document to ingest chunks into.
            metadata (Optional[dict]): Metadata dictionary for the document

        Returns:
            dict: Ingestion results containing processed, failed, and skipped documents.
        """

        data = {
            "chunks": chunks,
            "document_id": document_id,
            "metadata": metadata,
        }
        if run_with_orchestration is not None:
            data["run_with_orchestration"] = str(run_with_orchestration)  # type: ignore

        if collection_ids:
            data["collection_ids"] = json.dumps(  # type: ignore
                [
                    [
                        str(collection_id)
                        for collection_id in doc_collection_ids
                    ]
                    for doc_collection_ids in collection_ids
                ]
            )

        return await self._make_request("POST", "ingest_chunks", json=data)  # type: ignore

    @deprecated("Use client.chunks.update() instead")
    async def update_chunks(
        self,
        document_id: UUID,
        chunk_id: UUID,
        text: str,
        metadata: Optional[dict] = None,
        run_with_orchestration: Optional[bool] = None,
    ) -> dict:
        """
        Update the content of an existing chunk.

        Args:
            document_id (UUID): The ID of the document containing the chunk.
            chunk_id (UUID): The ID of the chunk to update.
            text (str): The new text content of the chunk.
            metadata (Optional[dict]): Metadata dictionary for the chunk.
            run_with_orchestration (Optional[bool]): Whether to run the update through orchestration.

        Returns:
            dict: Update results containing processed, failed, and skipped documents.
        """

        data = {
            "text": text,
            "metadata": metadata,
            "run_with_orchestration": run_with_orchestration,
        }

        # Remove None values from payload
        data = {k: v for k, v in data.items() if v is not None}

        return await self._make_request("PUT", f"update_chunk/{document_id}/{chunk_id}", json=data)  # type: ignore

    @deprecated("Use client.indices.create() instead")
    async def create_vector_index(
        self,
        table_name: VectorTableName = VectorTableName.CHUNKS,
        index_method: IndexMethod = IndexMethod.hnsw,
        index_measure: IndexMeasure = IndexMeasure.cosine_distance,
        index_arguments: Optional[dict] = None,
        index_name: Optional[str] = None,
        index_column: Optional[list[str]] = None,
        concurrently: bool = True,
    ) -> dict:
        """
        Create a vector index for a given table.

        Args:
            table_name (VectorTableName): Name of the table to create index on
            index_method (IndexMethod): Method to use for indexing (hnsw or ivf_flat)
            index_measure (IndexMeasure): Distance measure to use
            index_arguments (Optional[dict]): Additional arguments for the index
            index_name (Optional[str]): Custom name for the index
            concurrently (bool): Whether to create the index concurrently

        Returns:
            dict: Response containing the creation status
        """
        data = {
            "table_name": table_name,
            "index_method": index_method,
            "index_measure": index_measure,
            "index_arguments": index_arguments,
            "index_name": index_name,
            "index_column": index_column,
            "concurrently": concurrently,
        }
        return await self._make_request(  # type: ignore
            "POST", "create_vector_index", json=data
        )

    @deprecated("Use client.indices.list() instead")
    async def list_vector_indices(
        self,
        table_name: VectorTableName = VectorTableName.CHUNKS,
    ) -> dict:
        """
        List all vector indices for a given table.

        Args:
            table_name (VectorTableName): Name of the table to list indices from

        Returns:
            dict: Response containing the list of indices
        """
        params = {"table_name": table_name}
        return await self._make_request(  # type: ignore
            "GET", "list_vector_indices", params=params
        )

    @deprecated("Use client.indices.delete() instead")
    async def delete_vector_index(
        self,
        index_name: str,
        table_name: VectorTableName = VectorTableName.CHUNKS,
        concurrently: bool = True,
    ) -> dict:
        """
        Delete a vector index from a given table.

        Args:
            index_name (str): Name of the index to delete
            table_name (VectorTableName): Name of the table containing the index
            concurrently (bool): Whether to delete the index concurrently

        Returns:
            dict: Response containing the deletion status
        """
        data = {
            "index_name": index_name,
            "table_name": table_name,
            "concurrently": concurrently,
        }
        return await self._make_request(  # type: ignore
            "DELETE", "delete_vector_index", json=data
        )

    @deprecated("Use client.documents.update() instead")
    async def update_document_metadata(
        self,
        document_id: Union[str, UUID],
        metadata: dict,
    ) -> dict:
        """
        Update the metadata of an existing document.

        Args:
            document_id (Union[str, UUID]): The ID of the document to update.
            metadata (dict): The new metadata to merge with existing metadata.
            run_with_orchestration (Optional[bool]): Whether to run the update through orchestration.

        Returns:
            dict: Update results containing the status of the metadata update.
        """
        data = {
            "metadata": metadata,
        }

        # Remove None values from payload
        data = {k: v for k, v in data.items() if v is not None}

        return await self._make_request(  # type: ignore
            "POST", f"update_document_metadata/{document_id}", json=metadata
        )
