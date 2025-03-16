import asyncio
import copy
import csv
import json
import logging
import math
import tempfile
from typing import IO, Any, Optional
from uuid import UUID

import asyncpg
from fastapi import HTTPException

from core.base import (
    DocumentResponse,
    DocumentType,
    GraphConstructionStatus,
    GraphExtractionStatus,
    Handler,
    IngestionStatus,
    R2RException,
    SearchSettings,
)

from .base import PostgresConnectionManager
from .filters import apply_filters

logger = logging.getLogger()


def transform_filter_fields(filters: dict[str, Any]) -> dict[str, Any]:
    """Recursively transform filter field names by replacing 'document_id' with
    'id'. Handles nested logical operators like $and, $or, etc.

    Args:
        filters (dict[str, Any]): The original filters dictionary

    Returns:
        dict[str, Any]: A new dictionary with transformed field names
    """
    if not filters:
        return {}

    transformed = {}

    for key, value in filters.items():
        # Handle logical operators recursively
        if key in ("$and", "$or", "$not"):
            if isinstance(value, list):
                transformed[key] = [
                    transform_filter_fields(item) for item in value
                ]
            else:
                transformed[key] = transform_filter_fields(value)  # type: ignore
            continue

        # Replace 'document_id' with 'id'
        new_key = "id" if key == "document_id" else key

        # Handle nested dictionary cases (e.g., for operators like $eq, $gt, etc.)
        if isinstance(value, dict):
            transformed[new_key] = transform_filter_fields(value)  # type: ignore
        else:
            transformed[new_key] = value

    logger.debug(f"Transformed filters from {filters} to {transformed}")
    return transformed


class PostgresDocumentsHandler(Handler):
    TABLE_NAME = "documents"

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        dimension: int | float,
    ):
        self.dimension = dimension
        super().__init__(project_name, connection_manager)

    async def create_tables(self):
        logger.info(
            f"Creating table, if it does not exist: {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}"
        )

        vector_dim = (
            "" if math.isnan(self.dimension) else f"({self.dimension})"
        )
        vector_type = f"vector{vector_dim}"

        try:
            query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)} (
                id UUID PRIMARY KEY,
                collection_ids UUID[],
                owner_id UUID,
                type TEXT,
                metadata JSONB,
                title TEXT,
                summary TEXT NULL,
                summary_embedding {vector_type} NULL,
                version TEXT,
                size_in_bytes INT,
                ingestion_status TEXT DEFAULT 'pending',
                extraction_status TEXT DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                ingestion_attempt_number INT DEFAULT 0,
                raw_tsvector tsvector GENERATED ALWAYS AS (
                    setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
                    setweight(to_tsvector('english', COALESCE(summary, '')), 'B') ||
                    setweight(to_tsvector('english', COALESCE((metadata->>'description')::text, '')), 'C')
                ) STORED,
                total_tokens INT DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_collection_ids_{self.project_name}
            ON {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)} USING GIN (collection_ids);

            -- Full text search index
            CREATE INDEX IF NOT EXISTS idx_doc_search_{self.project_name}
            ON {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}
            USING GIN (raw_tsvector);
            """
            await self.connection_manager.execute_query(query)

            # ---------------------------------------------------------------
            # Now check if total_tokens column exists in the 'documents' table
            # ---------------------------------------------------------------
            # 1) See what columns exist
            # column_check_query = f"""
            # SELECT column_name
            # FROM information_schema.columns
            # WHERE table_name = '{self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}'
            # AND table_schema = CURRENT_SCHEMA()
            # """
            # existing_columns = await self.connection_manager.fetch_query(column_check_query)
            # 2) Parse the table name for schema checks
            table_full_name = self._get_table_name(
                PostgresDocumentsHandler.TABLE_NAME
            )
            parsed_schema = "public"
            parsed_table_name = table_full_name
            if "." in table_full_name:
                parts = table_full_name.split(".", maxsplit=1)
                parsed_schema = parts[0].replace('"', "").strip()
                parsed_table_name = parts[1].replace('"', "").strip()
            else:
                parsed_table_name = parsed_table_name.replace('"', "").strip()

            # 3) Check columns
            column_check_query = f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = '{parsed_table_name}'
            AND table_schema = '{parsed_schema}'
            """
            existing_columns = await self.connection_manager.fetch_query(
                column_check_query
            )

            existing_column_names = {
                row["column_name"] for row in existing_columns
            }

            if "total_tokens" not in existing_column_names:
                # 2) If missing, see if the table already has data
                # doc_count_query = f"SELECT COUNT(*) FROM {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}"
                # doc_count = await self.connection_manager.fetchval(doc_count_query)
                doc_count_query = f"SELECT COUNT(*) AS doc_count FROM {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}"
                row = await self.connection_manager.fetchrow_query(
                    doc_count_query
                )
                if row is None:
                    doc_count = 0
                else:
                    doc_count = row[
                        "doc_count"
                    ]  # or row[0] if you prefer positional indexing

                if doc_count > 0:
                    # We already have documents, but no total_tokens column
                    # => ask user to run r2r db migrate
                    logger.warning(
                        "Adding the missing 'total_tokens' column to the 'documents' table, this will impact existing files."
                    )

                create_tokens_col = f"""
                ALTER TABLE {table_full_name}
                ADD COLUMN total_tokens INT DEFAULT 0
                """
                await self.connection_manager.execute_query(create_tokens_col)

        except Exception as e:
            logger.warning(f"Error {e} when creating document table.")
            raise e

    async def upsert_documents_overview(
        self, documents_overview: DocumentResponse | list[DocumentResponse]
    ) -> None:
        if isinstance(documents_overview, DocumentResponse):
            documents_overview = [documents_overview]

        # TODO: make this an arg
        max_retries = 20
        for document in documents_overview:
            retries = 0
            while retries < max_retries:
                try:
                    async with (
                        self.connection_manager.pool.get_connection() as conn  # type: ignore
                    ):
                        async with conn.transaction():
                            # Lock the row for update
                            check_query = f"""
                            SELECT ingestion_attempt_number, ingestion_status FROM {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}
                            WHERE id = $1 FOR UPDATE
                            """
                            existing_doc = await conn.fetchrow(
                                check_query, document.id
                            )

                            db_entry = document.convert_to_db_entry()

                            if existing_doc:
                                db_version = existing_doc[
                                    "ingestion_attempt_number"
                                ]
                                db_status = existing_doc["ingestion_status"]
                                new_version = db_entry[
                                    "ingestion_attempt_number"
                                ]

                                # Only increment version if status is changing to 'success' or if it's a new version
                                if (
                                    db_status != "success"
                                    and db_entry["ingestion_status"]
                                    == "success"
                                ) or (new_version > db_version):
                                    new_attempt_number = db_version + 1
                                else:
                                    new_attempt_number = db_version

                                db_entry["ingestion_attempt_number"] = (
                                    new_attempt_number
                                )

                                update_query = f"""
                                UPDATE {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}
                                SET collection_ids = $1,
                                    owner_id = $2,
                                    type = $3,
                                    metadata = $4,
                                    title = $5,
                                    version = $6,
                                    size_in_bytes = $7,
                                    ingestion_status = $8,
                                    extraction_status = $9,
                                    updated_at = $10,
                                    ingestion_attempt_number = $11,
                                    summary = $12,
                                    summary_embedding = $13,
                                    total_tokens = $14
                                WHERE id = $15
                                """

                                await conn.execute(
                                    update_query,
                                    db_entry["collection_ids"],
                                    db_entry["owner_id"],
                                    db_entry["document_type"],
                                    db_entry["metadata"],
                                    db_entry["title"],
                                    db_entry["version"],
                                    db_entry["size_in_bytes"],
                                    db_entry["ingestion_status"],
                                    db_entry["extraction_status"],
                                    db_entry["updated_at"],
                                    db_entry["ingestion_attempt_number"],
                                    db_entry["summary"],
                                    db_entry["summary_embedding"],
                                    db_entry[
                                        "total_tokens"
                                    ],  # pass the new field here
                                    document.id,
                                )
                            else:
                                insert_query = f"""
                                INSERT INTO {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}
                                (id, collection_ids, owner_id, type, metadata, title, version,
                                size_in_bytes, ingestion_status, extraction_status, created_at,
                                updated_at, ingestion_attempt_number, summary, summary_embedding, total_tokens)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                                """
                                await conn.execute(
                                    insert_query,
                                    db_entry["id"],
                                    db_entry["collection_ids"],
                                    db_entry["owner_id"],
                                    db_entry["document_type"],
                                    db_entry["metadata"],
                                    db_entry["title"],
                                    db_entry["version"],
                                    db_entry["size_in_bytes"],
                                    db_entry["ingestion_status"],
                                    db_entry["extraction_status"],
                                    db_entry["created_at"],
                                    db_entry["updated_at"],
                                    db_entry["ingestion_attempt_number"],
                                    db_entry["summary"],
                                    db_entry["summary_embedding"],
                                    db_entry["total_tokens"],
                                )

                    break  # Success, exit the retry loop
                except (
                    asyncpg.exceptions.UniqueViolationError,
                    asyncpg.exceptions.DeadlockDetectedError,
                ) as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(
                            f"Failed to update document {document.id} after {max_retries} attempts. Error: {str(e)}"
                        )
                        raise
                    else:
                        wait_time = 0.1 * (2**retries)  # Exponential backoff
                        await asyncio.sleep(wait_time)

    async def delete(
        self, document_id: UUID, version: Optional[str] = None
    ) -> None:
        query = f"""
        DELETE FROM {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}
        WHERE id = $1
        """

        params = [str(document_id)]

        if version:
            query += " AND version = $2"
            params.append(version)

        await self.connection_manager.execute_query(query=query, params=params)

    async def _get_status_from_table(
        self,
        ids: list[UUID],
        table_name: str,
        status_type: str,
        column_name: str,
    ):
        """Get the workflow status for a given document or list of documents.

        Args:
            ids (list[UUID]): The document IDs.
            table_name (str): The table name.
            status_type (str): The type of status to retrieve.

        Returns:
            The workflow status for the given document or list of documents.
        """
        query = f"""
            SELECT {status_type} FROM {self._get_table_name(table_name)}
            WHERE {column_name} = ANY($1)
        """
        return [
            row[status_type]
            for row in await self.connection_manager.fetch_query(query, [ids])
        ]

    async def _get_ids_from_table(
        self,
        status: list[str],
        table_name: str,
        status_type: str,
        collection_id: Optional[UUID] = None,
    ):
        """Get the IDs from a given table.

        Args:
            status (str | list[str]): The status or list of statuses to retrieve.
            table_name (str): The table name.
            status_type (str): The type of status to retrieve.
        """
        query = f"""
            SELECT id FROM {self._get_table_name(table_name)}
            WHERE {status_type} = ANY($1) and $2 = ANY(collection_ids)
        """
        records = await self.connection_manager.fetch_query(
            query, [status, collection_id]
        )
        return [record["id"] for record in records]

    async def _set_status_in_table(
        self,
        ids: list[UUID],
        status: str,
        table_name: str,
        status_type: str,
        column_name: str,
    ):
        """Set the workflow status for a given document or list of documents.

        Args:
            ids (list[UUID]): The document IDs.
            status (str): The status to set.
            table_name (str): The table name.
            status_type (str): The type of status to set.
            column_name (str): The column name in the table to update.
        """
        query = f"""
            UPDATE {self._get_table_name(table_name)}
            SET {status_type} = $1
            WHERE {column_name} = Any($2)
        """
        await self.connection_manager.execute_query(query, [status, ids])

    def _get_status_model(self, status_type: str):
        """Get the status model for a given status type.

        Args:
            status_type (str): The type of status to retrieve.

        Returns:
            The status model for the given status type.
        """
        if status_type == "ingestion":
            return IngestionStatus
        elif status_type == "extraction_status":
            return GraphExtractionStatus
        elif status_type in {"graph_cluster_status", "graph_sync_status"}:
            return GraphConstructionStatus
        else:
            raise R2RException(
                status_code=400, message=f"Invalid status type: {status_type}"
            )

    async def get_workflow_status(
        self, id: UUID | list[UUID], status_type: str
    ):
        """Get the workflow status for a given document or list of documents.

        Args:
            id (UUID | list[UUID]): The document ID or list of document IDs.
            status_type (str): The type of status to retrieve.

        Returns:
            The workflow status for the given document or list of documents.
        """

        ids = [id] if isinstance(id, UUID) else id
        out_model = self._get_status_model(status_type)
        result = await self._get_status_from_table(
            ids,
            out_model.table_name(),
            status_type,
            out_model.id_column(),
        )

        result = [out_model[status.upper()] for status in result]
        return result[0] if isinstance(id, UUID) else result

    async def set_workflow_status(
        self, id: UUID | list[UUID], status_type: str, status: str
    ):
        """Set the workflow status for a given document or list of documents.

        Args:
            id (UUID | list[UUID]): The document ID or list of document IDs.
            status_type (str): The type of status to set.
            status (str): The status to set.
        """
        ids = [id] if isinstance(id, UUID) else id
        out_model = self._get_status_model(status_type)

        return await self._set_status_in_table(
            ids,
            status,
            out_model.table_name(),
            status_type,
            out_model.id_column(),
        )

    async def get_document_ids_by_status(
        self,
        status_type: str,
        status: str | list[str],
        collection_id: Optional[UUID] = None,
    ):
        """Get the IDs for a given status.

        Args:
            ids_key (str): The key to retrieve the IDs.
            status_type (str): The type of status to retrieve.
            status (str | list[str]): The status or list of statuses to retrieve.
        """

        if isinstance(status, str):
            status = [status]

        out_model = self._get_status_model(status_type)
        return await self._get_ids_from_table(
            status, out_model.table_name(), status_type, collection_id
        )

    async def get_documents_overview(
        self,
        offset: int,
        limit: int,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_collection_ids: Optional[list[UUID]] = None,
        include_summary_embedding: Optional[bool] = True,
        filters: Optional[dict[str, Any]] = None,
        sort_order: str = "DESC",  # Add this parameter with a default of DESC
    ) -> dict[str, Any]:
        """Fetch overviews of documents with optional offset/limit pagination.

        You can use either:
          - Traditional filters: `filter_user_ids`, `filter_document_ids`, `filter_collection_ids`
          - A `filters` dict (e.g., like we do in semantic search), which will be passed to `apply_filters`.

        If both the `filters` dict and any of the traditional filter arguments are provided,
        this method will raise an error.
        """

        filters = copy.deepcopy(filters)
        filters = transform_filter_fields(filters)  # type: ignore

        # Safety check: We do not allow mixing the old filter arguments with the new `filters` dict.
        # This keeps the query logic unambiguous.
        if filters and any(
            [
                filter_user_ids,
                filter_document_ids,
                filter_collection_ids,
            ]
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot use both the 'filters' dictionary "
                    "and the 'filter_*_ids' parameters simultaneously."
                ),
            )

        conditions = []
        params: list[Any] = []
        param_index = 1

        # -------------------------------------------
        # 1) If using the new `filters` dict approach
        # -------------------------------------------
        if filters:
            # Apply the filters to generate a WHERE clause
            filter_condition, filter_params = apply_filters(
                filters, params, mode="condition_only"
            )
            if filter_condition:
                conditions.append(filter_condition)
            # Make sure we keep adding to the same params list
            # params.extend(filter_params)
            param_index += len(filter_params)

        # -------------------------------------------
        # 2) If using the old filter_*_ids approach
        # -------------------------------------------
        else:
            # Handle document IDs with AND
            if filter_document_ids:
                conditions.append(f"id = ANY(${param_index})")
                params.append(filter_document_ids)
                param_index += 1

            # For owner/collection filters, we used OR logic previously
            # so we combine them into a single sub-condition in parentheses
            or_conditions = []
            if filter_user_ids:
                or_conditions.append(f"owner_id = ANY(${param_index})")
                params.append(filter_user_ids)
                param_index += 1

            if filter_collection_ids:
                or_conditions.append(f"collection_ids && ${param_index}")
                params.append(filter_collection_ids)
                param_index += 1

            if or_conditions:
                conditions.append(f"({' OR '.join(or_conditions)})")

        # -------------------------
        # Build the full query
        # -------------------------
        base_query = (
            f"FROM {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}"
        )
        if conditions:
            # Combine everything with AND
            base_query += " WHERE " + " AND ".join(conditions)

        # Construct SELECT fields (including total_entries via window function)
        select_fields = """
            SELECT
                id,
                collection_ids,
                owner_id,
                type,
                metadata,
                title,
                version,
                size_in_bytes,
                ingestion_status,
                extraction_status,
                created_at,
                updated_at,
                summary,
                summary_embedding,
                total_tokens,
                COUNT(*) OVER() AS total_entries
        """

        query = f"""
            {select_fields}
            {base_query}
            ORDER BY created_at {sort_order}
            OFFSET ${param_index}
        """
        params.append(offset)
        param_index += 1

        if limit != -1:
            query += f" LIMIT ${param_index}"
            params.append(limit)
            param_index += 1

        try:
            results = await self.connection_manager.fetch_query(query, params)
            total_entries = results[0]["total_entries"] if results else 0

            documents = []
            for row in results:
                # Safely handle the embedding
                embedding = None
                if (
                    "summary_embedding" in row
                    and row["summary_embedding"] is not None
                ):
                    try:
                        # The embedding is stored as a string like "[0.1, 0.2, ...]"
                        embedding_str = row["summary_embedding"]
                        if embedding_str.startswith(
                            "["
                        ) and embedding_str.endswith("]"):
                            embedding = [
                                float(x)
                                for x in embedding_str[1:-1].split(",")
                                if x
                            ]
                    except Exception as e:
                        logger.warning(
                            f"Failed to parse embedding for document {row['id']}: {e}"
                        )

                documents.append(
                    DocumentResponse(
                        id=row["id"],
                        collection_ids=row["collection_ids"],
                        owner_id=row["owner_id"],
                        document_type=DocumentType(row["type"]),
                        metadata=json.loads(row["metadata"]),
                        title=row["title"],
                        version=row["version"],
                        size_in_bytes=row["size_in_bytes"],
                        ingestion_status=IngestionStatus(
                            row["ingestion_status"]
                        ),
                        extraction_status=GraphExtractionStatus(
                            row["extraction_status"]
                        ),
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        summary=row["summary"] if "summary" in row else None,
                        summary_embedding=(
                            embedding if include_summary_embedding else None
                        ),
                        total_tokens=row["total_tokens"],
                    )
                )
            return {"results": documents, "total_entries": total_entries}
        except Exception as e:
            logger.error(f"Error in get_documents_overview: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Database query failed",
            ) from e

    async def semantic_document_search(
        self, query_embedding: list[float], search_settings: SearchSettings
    ) -> list[DocumentResponse]:
        """Search documents using semantic similarity with their summary
        embeddings."""

        where_clauses = ["summary_embedding IS NOT NULL"]
        params: list[str | int | bytes] = [str(query_embedding)]

        vector_dim = (
            "" if math.isnan(self.dimension) else f"({self.dimension})"
        )
        filters = copy.deepcopy(search_settings.filters)
        if filters:
            filter_condition, params = apply_filters(
                transform_filter_fields(filters), params, mode="condition_only"
            )
            if filter_condition:
                where_clauses.append(filter_condition)

        where_clause = " AND ".join(where_clauses)

        query = f"""
        WITH document_scores AS (
            SELECT
                id,
                collection_ids,
                owner_id,
                type,
                metadata,
                title,
                version,
                size_in_bytes,
                ingestion_status,
                extraction_status,
                created_at,
                updated_at,
                summary,
                summary_embedding,
                total_tokens,
                (summary_embedding <=> $1::vector({vector_dim})) as semantic_distance
            FROM {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}
            WHERE {where_clause}
            ORDER BY semantic_distance ASC
            LIMIT ${len(params) + 1}
            OFFSET ${len(params) + 2}
        )
        SELECT *,
            1.0 - semantic_distance as semantic_score
        FROM document_scores
        """

        params.extend([search_settings.limit, search_settings.offset])

        results = await self.connection_manager.fetch_query(query, params)

        return [
            DocumentResponse(
                id=row["id"],
                collection_ids=row["collection_ids"],
                owner_id=row["owner_id"],
                document_type=DocumentType(row["type"]),
                metadata={
                    **(
                        json.loads(row["metadata"])
                        if search_settings.include_metadatas
                        else {}
                    ),
                    "search_score": float(row["semantic_score"]),
                    "search_type": "semantic",
                },
                title=row["title"],
                version=row["version"],
                size_in_bytes=row["size_in_bytes"],
                ingestion_status=IngestionStatus(row["ingestion_status"]),
                extraction_status=GraphExtractionStatus(
                    row["extraction_status"]
                ),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                summary=row["summary"],
                summary_embedding=[
                    float(x)
                    for x in row["summary_embedding"][1:-1].split(",")
                    if x
                ],
                total_tokens=row["total_tokens"],
            )
            for row in results
        ]

    async def full_text_document_search(
        self, query_text: str, search_settings: SearchSettings
    ) -> list[DocumentResponse]:
        """Enhanced full-text search using generated tsvector."""

        where_clauses = ["raw_tsvector @@ websearch_to_tsquery('english', $1)"]
        params: list[str | int | bytes] = [query_text]

        filters = copy.deepcopy(search_settings.filters)
        if filters:
            filter_condition, params = apply_filters(
                transform_filter_fields(filters), params, mode="condition_only"
            )
            if filter_condition:
                where_clauses.append(filter_condition)

        where_clause = " AND ".join(where_clauses)

        query = f"""
        WITH document_scores AS (
            SELECT
                id,
                collection_ids,
                owner_id,
                type,
                metadata,
                title,
                version,
                size_in_bytes,
                ingestion_status,
                extraction_status,
                created_at,
                updated_at,
                summary,
                summary_embedding,
                total_tokens,
                ts_rank_cd(raw_tsvector, websearch_to_tsquery('english', $1), 32) as text_score
            FROM {self._get_table_name(PostgresDocumentsHandler.TABLE_NAME)}
            WHERE {where_clause}
            ORDER BY text_score DESC
            LIMIT ${len(params) + 1}
            OFFSET ${len(params) + 2}
        )
        SELECT * FROM document_scores
        """

        params.extend([search_settings.limit, search_settings.offset])

        results = await self.connection_manager.fetch_query(query, params)

        return [
            DocumentResponse(
                id=row["id"],
                collection_ids=row["collection_ids"],
                owner_id=row["owner_id"],
                document_type=DocumentType(row["type"]),
                metadata={
                    **(
                        json.loads(row["metadata"])
                        if search_settings.include_metadatas
                        else {}
                    ),
                    "search_score": float(row["text_score"]),
                    "search_type": "full_text",
                },
                title=row["title"],
                version=row["version"],
                size_in_bytes=row["size_in_bytes"],
                ingestion_status=IngestionStatus(row["ingestion_status"]),
                extraction_status=GraphExtractionStatus(
                    row["extraction_status"]
                ),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                summary=row["summary"],
                summary_embedding=(
                    [
                        float(x)
                        for x in row["summary_embedding"][1:-1].split(",")
                        if x
                    ]
                    if row["summary_embedding"]
                    else None
                ),
                total_tokens=row["total_tokens"],
            )
            for row in results
        ]

    async def hybrid_document_search(
        self,
        query_text: str,
        query_embedding: list[float],
        search_settings: SearchSettings,
    ) -> list[DocumentResponse]:
        """Search documents using both semantic and full-text search with RRF
        fusion."""

        # Get more results than needed for better fusion
        extended_settings = copy.deepcopy(search_settings)
        extended_settings.limit = search_settings.limit * 3

        # Get results from both search methods
        semantic_results = await self.semantic_document_search(
            query_embedding, extended_settings
        )
        full_text_results = await self.full_text_document_search(
            query_text, extended_settings
        )

        # Combine results using RRF
        doc_scores: dict[str, dict] = {}

        # Process semantic results
        for rank, result in enumerate(semantic_results, 1):
            doc_id = str(result.id)
            doc_scores[doc_id] = {
                "semantic_rank": rank,
                "full_text_rank": len(full_text_results)
                + 1,  # Default rank if not found
                "data": result,
            }

        # Process full-text results
        for rank, result in enumerate(full_text_results, 1):
            doc_id = str(result.id)
            if doc_id in doc_scores:
                doc_scores[doc_id]["full_text_rank"] = rank
            else:
                doc_scores[doc_id] = {
                    "semantic_rank": len(semantic_results)
                    + 1,  # Default rank if not found
                    "full_text_rank": rank,
                    "data": result,
                }

        # Calculate RRF scores using hybrid search settings
        rrf_k = search_settings.hybrid_settings.rrf_k
        semantic_weight = search_settings.hybrid_settings.semantic_weight
        full_text_weight = search_settings.hybrid_settings.full_text_weight

        for scores in doc_scores.values():
            semantic_score = 1 / (rrf_k + scores["semantic_rank"])
            full_text_score = 1 / (rrf_k + scores["full_text_rank"])

            # Weighted combination
            combined_score = (
                semantic_score * semantic_weight
                + full_text_score * full_text_weight
            ) / (semantic_weight + full_text_weight)

            scores["final_score"] = combined_score

        # Sort by final score and apply offset/limit
        sorted_results = sorted(
            doc_scores.values(), key=lambda x: x["final_score"], reverse=True
        )[
            search_settings.offset : search_settings.offset
            + search_settings.limit
        ]

        return [
            DocumentResponse(
                **{
                    **result["data"].__dict__,
                    "metadata": {
                        **(
                            result["data"].metadata
                            if search_settings.include_metadatas
                            else {}
                        ),
                        "search_score": result["final_score"],
                        "semantic_rank": result["semantic_rank"],
                        "full_text_rank": result["full_text_rank"],
                        "search_type": "hybrid",
                    },
                }
            )
            for result in sorted_results
        ]

    async def search_documents(
        self,
        query_text: str,
        query_embedding: Optional[list[float]] = None,
        settings: Optional[SearchSettings] = None,
    ) -> list[DocumentResponse]:
        """Main search method that delegates to the appropriate search method
        based on settings."""
        if settings is None:
            settings = SearchSettings()

        if (
            settings.use_semantic_search and settings.use_fulltext_search
        ) or settings.use_hybrid_search:
            if query_embedding is None:
                raise ValueError(
                    "query_embedding is required for hybrid search"
                )
            return await self.hybrid_document_search(
                query_text, query_embedding, settings
            )
        elif settings.use_semantic_search:
            if query_embedding is None:
                raise ValueError(
                    "query_embedding is required for vector search"
                )
            return await self.semantic_document_search(
                query_embedding, settings
            )
        else:
            return await self.full_text_document_search(query_text, settings)

    async def export_to_csv(
        self,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        """Creates a CSV file from the PostgreSQL data and returns the path to
        the temp file."""
        valid_columns = {
            "id",
            "collection_ids",
            "owner_id",
            "type",
            "metadata",
            "title",
            "summary",
            "version",
            "size_in_bytes",
            "ingestion_status",
            "extraction_status",
            "created_at",
            "updated_at",
            "total_tokens",
        }
        filters = copy.deepcopy(filters)
        filters = transform_filter_fields(filters)  # type: ignore

        if not columns:
            columns = list(valid_columns)
        elif invalid_cols := set(columns) - valid_columns:
            raise ValueError(f"Invalid columns: {invalid_cols}")

        select_stmt = f"""
            SELECT
                id::text,
                collection_ids::text,
                owner_id::text,
                type::text,
                metadata::text AS metadata,
                title,
                summary,
                version,
                size_in_bytes,
                ingestion_status,
                extraction_status,
                to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at,
                total_tokens
            FROM {self._get_table_name(self.TABLE_NAME)}
        """

        conditions = []
        params: list[Any] = []
        param_index = 1

        if filters:
            for field, value in filters.items():
                if field not in valid_columns:
                    continue

                if isinstance(value, dict):
                    for op, val in value.items():
                        if op == "$eq":
                            conditions.append(f"{field} = ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$gt":
                            conditions.append(f"{field} > ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$lt":
                            conditions.append(f"{field} < ${param_index}")
                            params.append(val)
                            param_index += 1
                else:
                    # Direct equality
                    conditions.append(f"{field} = ${param_index}")
                    params.append(value)
                    param_index += 1

        if conditions:
            select_stmt = f"{select_stmt} WHERE {' AND '.join(conditions)}"

        select_stmt = f"{select_stmt} ORDER BY created_at DESC"

        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", delete=True, suffix=".csv"
            )
            writer = csv.writer(temp_file, quoting=csv.QUOTE_ALL)

            async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
                async with conn.transaction():
                    cursor = await conn.cursor(select_stmt, *params)

                    if include_header:
                        writer.writerow(columns)

                    chunk_size = 1000
                    while True:
                        rows = await cursor.fetch(chunk_size)
                        if not rows:
                            break
                        for row in rows:
                            row_dict = {
                                "id": row[0],
                                "collection_ids": row[1],
                                "owner_id": row[2],
                                "type": row[3],
                                "metadata": row[4],
                                "title": row[5],
                                "summary": row[6],
                                "version": row[7],
                                "size_in_bytes": row[8],
                                "ingestion_status": row[9],
                                "extraction_status": row[10],
                                "created_at": row[11],
                                "updated_at": row[12],
                                "total_tokens": row[13],
                            }
                            writer.writerow([row_dict[col] for col in columns])

            temp_file.flush()
            return temp_file.name, temp_file

        except Exception as e:
            if temp_file:
                temp_file.close()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to export data: {str(e)}",
            ) from e
