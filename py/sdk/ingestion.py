import json
import os
from contextlib import ExitStack
from typing import Optional, Union
from uuid import UUID


class IngestionMethods:
    @staticmethod
    async def ingest_files(
        client,
        file_paths: list[str],
        document_ids: Optional[list[Union[str, UUID]]] = None,
        metadatas: Optional[list[dict]] = None,
        ingestion_config: Optional[dict] = None,
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
                data["run_with_orchestration"] = str(run_with_orchestration)

            return await client._make_request(
                "POST", "ingest_files", data=data, files=files_tuples
            )

    @staticmethod
    async def update_files(
        client,
        file_paths: list[str],
        document_ids: Optional[list[Union[str, UUID]]] = None,
        metadatas: Optional[list[dict]] = None,
        ingestion_config: Optional[dict] = None,
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

            return await client._make_request(
                "POST", "update_files", data=data, files=files
            )

    @staticmethod
    async def ingest_chunks(
        client,
        chunks: list[dict],
        document_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
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
        return await client._make_request("POST", "ingest_chunks", json=data)
