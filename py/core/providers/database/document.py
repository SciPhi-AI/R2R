import asyncio
import copy
import json
import logging
from typing import Any, Optional
from uuid import UUID

import asyncpg
from fastapi import HTTPException

from core.base import (
    DocumentHandler,
    DocumentResponse,
    DocumentType,
    IngestionStatus,
    KGEnrichmentStatus,
    KGExtractionStatus,
    R2RException,
    SearchSettings,
)

from .base import PostgresConnectionManager

logger = logging.getLogger()


class PostgresDocumentHandler(DocumentHandler):
    TABLE_NAME = "documents"
    COLUMN_VARS = [
        "extraction_id",
        "id",
        "owner_id",
        "collection_ids",
    ]

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        dimension: int,
    ):
        self.dimension = dimension
        super().__init__(project_name, connection_manager)

    async def create_tables(self):
        logger.info(
            f"Creating table, if not exists: {self._get_table_name(PostgresDocumentHandler.TABLE_NAME)}"
        )
        try:
            query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresDocumentHandler.TABLE_NAME)} (
                id UUID PRIMARY KEY,
                collection_ids UUID[],
                owner_id UUID,
                type TEXT,
                metadata JSONB,
                title TEXT,
                summary TEXT NULL,
                summary_embedding vector({self.dimension}) NULL,
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
                ) STORED
            );
            CREATE INDEX IF NOT EXISTS idx_collection_ids_{self.project_name}
            ON {self._get_table_name(PostgresDocumentHandler.TABLE_NAME)} USING GIN (collection_ids);

            -- Full text search index
            CREATE INDEX IF NOT EXISTS idx_doc_search_{self.project_name}
            ON {self._get_table_name(PostgresDocumentHandler.TABLE_NAME)}
            USING GIN (raw_tsvector);
            """
            await self.connection_manager.execute_query(query)
        except Exception as e:
            logger.warning(f"Error {e} when creating document table.")

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
                    async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
                        async with conn.transaction():
                            # Lock the row for update
                            check_query = f"""
                            SELECT ingestion_attempt_number, ingestion_status FROM {self._get_table_name(PostgresDocumentHandler.TABLE_NAME)}
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
                                UPDATE {self._get_table_name(PostgresDocumentHandler.TABLE_NAME)}
                                SET collection_ids = $1, owner_id = $2, type = $3, metadata = $4,
                                    title = $5, version = $6, size_in_bytes = $7, ingestion_status = $8,
                                    extraction_status = $9, updated_at = $10, ingestion_attempt_number = $11,
                                    summary = $12, summary_embedding = $13
                                WHERE id = $14
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
                                    new_attempt_number,
                                    db_entry["summary"],
                                    db_entry["summary_embedding"],
                                    document.id,
                                )
                            else:

                                insert_query = f"""
                                INSERT INTO {self._get_table_name(PostgresDocumentHandler.TABLE_NAME)}
                                (id, collection_ids, owner_id, type, metadata, title, version,
                                size_in_bytes, ingestion_status, extraction_status, created_at,
                                updated_at, ingestion_attempt_number, summary, summary_embedding)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
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

    async def delete_from_documents_overview(
        self, document_id: UUID, version: Optional[str] = None
    ) -> None:
        query = f"""
        DELETE FROM {self._get_table_name(PostgresDocumentHandler.TABLE_NAME)}
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
        """
        Get the workflow status for a given document or list of documents.

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
        """
        Get the IDs from a given table.

        Args:
            status (Union[str, list[str]]): The status or list of statuses to retrieve.
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
        """
        Set the workflow status for a given document or list of documents.

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
        """
        Get the status model for a given status type.

        Args:
            status_type (str): The type of status to retrieve.

        Returns:
            The status model for the given status type.
        """
        if status_type == "ingestion":
            return IngestionStatus
        elif status_type == "extraction_status":
            return KGExtractionStatus
        elif status_type == "graph_cluster_status":
            return KGEnrichmentStatus
        elif status_type == "graph_sync_status":
            return KGEnrichmentStatus
        else:
            raise R2RException(
                status_code=400, message=f"Invalid status type: {status_type}"
            )

    async def get_workflow_status(
        self, id: UUID | list[UUID], status_type: str
    ):
        """
        Get the workflow status for a given document or list of documents.

        Args:
            id (Union[UUID, list[UUID]]): The document ID or list of document IDs.
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
        """
        Set the workflow status for a given document or list of documents.

        Args:
            id (Union[UUID, list[UUID]]): The document ID or list of document IDs.
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
        """
        Get the IDs for a given status.

        Args:
            ids_key (str): The key to retrieve the IDs.
            status_type (str): The type of status to retrieve.
            status (Union[str, list[str]]): The status or list of statuses to retrieve.
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
    ) -> dict[str, Any]:
        conditions = []
        params: list[Any] = []
        param_index = 1

        if filter_document_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(filter_document_ids)
            param_index += 1

        if filter_user_ids:
            conditions.append(f"owner_id = ANY(${param_index})")
            params.append(filter_user_ids)
            param_index += 1

        if filter_collection_ids:
            conditions.append(f"collection_ids && ${param_index}")
            params.append(filter_collection_ids)
            param_index += 1

        base_query = f"""
            FROM {self._get_table_name(PostgresDocumentHandler.TABLE_NAME)}
        """

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        # Construct the SELECT part of the query based on column existence
        select_fields = """
            SELECT id, collection_ids, owner_id, type, metadata, title, version,
                size_in_bytes, ingestion_status, extraction_status, created_at, updated_at,
                summary, summary_embedding,
                COUNT(*) OVER() AS total_entries
        """

        query = f"""
            {select_fields}
            {base_query}
            ORDER BY created_at DESC
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
                        # Parse the vector string returned by Postgres
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
                        extraction_status=KGExtractionStatus(
                            row["extraction_status"]
                        ),
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        summary=row["summary"] if "summary" in row else None,
                        summary_embedding=embedding,
                    )
                )
            return {"results": documents, "total_entries": total_entries}
        except Exception as e:
            logger.error(f"Error in get_documents_overview: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Database query failed",
            )

    async def semantic_document_search(
        self, query_embedding: list[float], search_settings: SearchSettings
    ) -> list[DocumentResponse]:
        """Search documents using semantic similarity with their summary embeddings."""

        where_clauses = ["summary_embedding IS NOT NULL"]
        params: list[str | int | bytes] = [str(query_embedding)]

        # Handle filters
        if search_settings.filters:
            filter_clause = self._build_filters(
                search_settings.filters, params
            )
            where_clauses.append(filter_clause)

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
                (summary_embedding <=> $1::vector({self.dimension})) as semantic_distance
            FROM {self._get_table_name(PostgresDocumentHandler.TABLE_NAME)}
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
                extraction_status=KGExtractionStatus(row["extraction_status"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                summary=row["summary"],
                summary_embedding=[
                    float(x)
                    for x in row["summary_embedding"][1:-1].split(",")
                    if x
                ],
            )
            for row in results
        ]

    async def full_text_document_search(
        self, query_text: str, search_settings: SearchSettings
    ) -> list[DocumentResponse]:
        """Enhanced full-text search using generated tsvector."""

        where_clauses = ["raw_tsvector @@ websearch_to_tsquery('english', $1)"]
        params: list[str | int | bytes] = [query_text]

        # Handle filters
        if search_settings.filters:
            filter_clause = self._build_filters(
                search_settings.filters, params
            )
            where_clauses.append(filter_clause)

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
                ts_rank_cd(raw_tsvector, websearch_to_tsquery('english', $1), 32) as text_score
            FROM {self._get_table_name(PostgresDocumentHandler.TABLE_NAME)}
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
                extraction_status=KGExtractionStatus(row["extraction_status"]),
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
            )
            for row in results
        ]

    async def hybrid_document_search(
        self,
        query_text: str,
        query_embedding: list[float],
        search_settings: SearchSettings,
    ) -> list[DocumentResponse]:
        """Search documents using both semantic and full-text search with RRF fusion."""

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
        search_settings: Optional[SearchSettings] = None,
    ) -> list[DocumentResponse]:
        """
        Main search method that delegates to the appropriate search method based on settings.
        """
        if search_settings is None:
            search_settings = SearchSettings()

        if (
            search_settings.use_semantic_search
            and search_settings.use_fulltext_search
        ) or search_settings.use_hybrid_search:
            if query_embedding is None:
                raise ValueError(
                    "query_embedding is required for hybrid search"
                )
            return await self.hybrid_document_search(
                query_text, query_embedding, search_settings
            )
        elif search_settings.use_semantic_search:
            if query_embedding is None:
                raise ValueError(
                    "query_embedding is required for vector search"
                )
            return await self.semantic_document_search(
                query_embedding, search_settings
            )
        else:
            return await self.full_text_document_search(
                query_text, search_settings
            )

    # TODO - Remove copy pasta, consolidate
    def _build_filters(
        self, filters: dict, parameters: list[str | int | bytes]
    ) -> str:

        def parse_condition(key: str, value: Any) -> str:  # type: ignore
            # nonlocal parameters
            if key in self.COLUMN_VARS:
                # Handle column-based filters
                if isinstance(value, dict):
                    op, clause = next(iter(value.items()))
                    if op == "$eq":
                        parameters.append(clause)
                        return f"{key} = ${len(parameters)}"
                    elif op == "$ne":
                        parameters.append(clause)
                        return f"{key} != ${len(parameters)}"
                    elif op == "$in":
                        parameters.append(clause)
                        return f"{key} = ANY(${len(parameters)})"
                    elif op == "$nin":
                        parameters.append(clause)
                        return f"{key} != ALL(${len(parameters)})"
                    elif op == "$overlap":
                        parameters.append(clause)
                        return f"{key} && ${len(parameters)}"
                    elif op == "$contains":
                        parameters.append(clause)
                        return f"{key} @> ${len(parameters)}"
                    elif op == "$any":
                        if key == "collection_ids":
                            parameters.append(f"%{clause}%")
                            return f"array_to_string({key}, ',') LIKE ${len(parameters)}"
                        parameters.append(clause)
                        return f"${len(parameters)} = ANY({key})"
                    else:
                        raise ValueError(
                            f"Unsupported operator for column {key}: {op}"
                        )
                else:
                    # Handle direct equality
                    parameters.append(value)
                    return f"{key} = ${len(parameters)}"
            else:
                # Handle JSON-based filters
                json_col = "metadata"
                if key.startswith("metadata."):
                    key = key.split("metadata.")[1]
                if isinstance(value, dict):
                    op, clause = next(iter(value.items()))
                    if op not in (
                        "$eq",
                        "$ne",
                        "$lt",
                        "$lte",
                        "$gt",
                        "$gte",
                        "$in",
                        "$contains",
                    ):
                        raise ValueError("unknown operator")

                    if op == "$eq":
                        parameters.append(json.dumps(clause))
                        return (
                            f"{json_col}->'{key}' = ${len(parameters)}::jsonb"
                        )
                    elif op == "$ne":
                        parameters.append(json.dumps(clause))
                        return (
                            f"{json_col}->'{key}' != ${len(parameters)}::jsonb"
                        )
                    elif op == "$lt":
                        parameters.append(json.dumps(clause))
                        return f"({json_col}->'{key}')::float < (${len(parameters)}::jsonb)::float"
                    elif op == "$lte":
                        parameters.append(json.dumps(clause))
                        return f"({json_col}->'{key}')::float <= (${len(parameters)}::jsonb)::float"
                    elif op == "$gt":
                        parameters.append(json.dumps(clause))
                        return f"({json_col}->'{key}')::float > (${len(parameters)}::jsonb)::float"
                    elif op == "$gte":
                        parameters.append(json.dumps(clause))
                        return f"({json_col}->'{key}')::float >= (${len(parameters)}::jsonb)::float"
                    elif op == "$in":
                        if not isinstance(clause, list):
                            raise ValueError(
                                "argument to $in filter must be a list"
                            )
                        parameters.append(json.dumps(clause))
                        return f"{json_col}->'{key}' = ANY(SELECT jsonb_array_elements(${len(parameters)}::jsonb))"
                    elif op == "$contains":
                        if not isinstance(clause, (int, str, float, list)):
                            raise ValueError(
                                "argument to $contains filter must be a scalar or array"
                            )
                        parameters.append(json.dumps(clause))
                        return (
                            f"{json_col}->'{key}' @> ${len(parameters)}::jsonb"
                        )

        def parse_filter(filter_dict: dict) -> str:
            filter_conditions = []
            for key, value in filter_dict.items():
                if key == "$and":
                    and_conditions = [
                        parse_filter(f) for f in value if f
                    ]  # Skip empty dictionaries
                    if and_conditions:
                        filter_conditions.append(
                            f"({' AND '.join(and_conditions)})"
                        )
                elif key == "$or":
                    or_conditions = [
                        parse_filter(f) for f in value if f
                    ]  # Skip empty dictionaries
                    if or_conditions:
                        filter_conditions.append(
                            f"({' OR '.join(or_conditions)})"
                        )
                else:
                    filter_conditions.append(parse_condition(key, value))

            # Check if there is only a single condition
            if len(filter_conditions) == 1:
                return filter_conditions[0]
            else:
                return " AND ".join(filter_conditions)

        where_clause = parse_filter(filters)

        return where_clause
