import copy
import json
import logging
import time
import uuid
from typing import Any, Optional, Tuple, TypedDict, Union
from uuid import UUID

from core.base import (
    IndexArgsHNSW,
    IndexArgsIVFFlat,
    IndexMeasure,
    IndexMethod,
    VectorEntry,
    VectorHandler,
    VectorQuantizationType,
    VectorSearchResult,
    VectorSearchSettings,
    VectorTableName,
)

from .base import PostgresConnectionManager
from .vecs.exc import ArgError, FilterError

logger = logging.getLogger()
from core.base.utils import _decorate_vector_type


def index_measure_to_ops(
    measure: IndexMeasure,
    quantization_type: VectorQuantizationType = VectorQuantizationType.FP32,
):
    return _decorate_vector_type(measure.ops, quantization_type)


class HybridSearchIntermediateResult(TypedDict):
    semantic_rank: int
    full_text_rank: int
    data: VectorSearchResult
    rrf_score: float


class PostgresVectorHandler(VectorHandler):
    TABLE_NAME = VectorTableName.VECTORS

    COLUMN_VARS = [
        "extraction_id",
        "document_id",
        "user_id",
        "collection_ids",
    ]

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        dimension: int,
        enable_fts: bool = False,
    ):
        super().__init__(project_name, connection_manager)
        self.dimension = dimension
        self.enable_fts = enable_fts

    async def create_tables(self):
        # Check for old table name first
        check_query = f"""
        SELECT EXISTS (
            SELECT FROM pg_tables
            WHERE schemaname = $1
            AND tablename = $2
        );
        """
        old_table_exists = await self.connection_manager.fetch_query(
            check_query, (self.project_name, self.project_name)
        )

        if len(old_table_exists) > 0 and old_table_exists[0]["exists"]:
            raise ValueError(
                f"Found old vector table '{self.project_name}.{self.project_name}'. "
                "Please run `r2r db upgrade` with the CLI, or to run manually, "
                "run in R2R/py/migrations with 'alembic upgrade head' to update "
                "your database schema to the new version."
            )

        # TODO - Move ids to `UUID` type
        # Create the vector table if it doesn't exist
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresVectorHandler.TABLE_NAME)} (
            extraction_id UUID PRIMARY KEY,
            document_id UUID,
            user_id UUID,
            collection_ids UUID[],
            vec vector({self.dimension}),
            text TEXT,
            metadata JSONB
            {",fts tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED" if self.enable_fts else ""}
        );
        CREATE INDEX IF NOT EXISTS idx_vectors_document_id ON {self._get_table_name(PostgresVectorHandler.TABLE_NAME)} (document_id);
        CREATE INDEX IF NOT EXISTS idx_vectors_user_id ON {self._get_table_name(PostgresVectorHandler.TABLE_NAME)} (user_id);
        CREATE INDEX IF NOT EXISTS idx_vectors_collection_ids ON {self._get_table_name(PostgresVectorHandler.TABLE_NAME)} USING GIN (collection_ids);
        CREATE INDEX IF NOT EXISTS idx_vectors_text ON {self._get_table_name(PostgresVectorHandler.TABLE_NAME)} USING GIN (to_tsvector('english', text));
        """
        if self.enable_fts:
            query += f"""
            CREATE INDEX IF NOT EXISTS idx_vectors_text ON {self._get_table_name(PostgresVectorHandler.TABLE_NAME)} USING GIN (to_tsvector('english', text));
            """

        await self.connection_manager.execute_query(query)

    async def upsert(self, entry: VectorEntry) -> None:
        query = f"""
        INSERT INTO {self._get_table_name(PostgresVectorHandler.TABLE_NAME)}
        (extraction_id, document_id, user_id, collection_ids, vec, text, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (extraction_id) DO UPDATE SET
        document_id = EXCLUDED.document_id,
        user_id = EXCLUDED.user_id,
        collection_ids = EXCLUDED.collection_ids,
        vec = EXCLUDED.vec,
        text = EXCLUDED.text,
        metadata = EXCLUDED.metadata;
        """
        await self.connection_manager.execute_query(
            query,
            (
                entry.extraction_id,
                entry.document_id,
                entry.user_id,
                entry.collection_ids,
                str(entry.vector.data),
                entry.text,
                json.dumps(entry.metadata),
            ),
        )

    async def upsert_entries(self, entries: list[VectorEntry]) -> None:
        query = f"""
        INSERT INTO {self._get_table_name(PostgresVectorHandler.TABLE_NAME)}
        (extraction_id, document_id, user_id, collection_ids, vec, text, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (extraction_id) DO UPDATE SET
        document_id = EXCLUDED.document_id,
        user_id = EXCLUDED.user_id,
        collection_ids = EXCLUDED.collection_ids,
        vec = EXCLUDED.vec,
        text = EXCLUDED.text,
        metadata = EXCLUDED.metadata;
        """
        params = [
            (
                entry.extraction_id,
                entry.document_id,
                entry.user_id,
                entry.collection_ids,
                str(entry.vector.data),
                entry.text,
                json.dumps(entry.metadata),
            )
            for entry in entries
        ]
        await self.connection_manager.execute_many(query, params)

    async def semantic_search(
        self, query_vector: list[float], search_settings: VectorSearchSettings
    ) -> list[VectorSearchResult]:
        try:
            imeasure_obj = IndexMeasure(search_settings.index_measure)
        except ValueError:
            raise ValueError("Invalid index measure")

        table_name = self._get_table_name(PostgresVectorHandler.TABLE_NAME)
        cols = [
            f"{table_name}.extraction_id",
            f"{table_name}.document_id",
            f"{table_name}.user_id",
            f"{table_name}.collection_ids",
            f"{table_name}.text",
        ]

        # Use cosine distance calculation
        distance_calc = f"{table_name}.vec <=> $1::vector"

        if search_settings.include_values:
            cols.append(f"({distance_calc}) AS distance")

        if search_settings.include_metadatas:
            cols.append(f"{table_name}.metadata")

        select_clause = ", ".join(cols)

        where_clause = ""
        params: list[Union[str, int]] = [str(query_vector)]
        if search_settings.filters:
            where_clause = self._build_filters(search_settings.filters, params)
            where_clause = f"WHERE {where_clause}"

        query = f"""
        SELECT {select_clause}
        FROM {table_name}
        {where_clause}
        ORDER BY {distance_calc}
        LIMIT ${len(params) + 1}
        OFFSET ${len(params) + 2}
        """

        params.extend([search_settings.search_limit, search_settings.offset])

        results = await self.connection_manager.fetch_query(query, params)

        return [
            VectorSearchResult(
                extraction_id=UUID(str(result["extraction_id"])),
                document_id=UUID(str(result["document_id"])),
                user_id=UUID(str(result["user_id"])),
                collection_ids=result["collection_ids"],
                text=result["text"],
                score=(
                    (1 - float(result["distance"]))
                    if search_settings.include_values
                    else -1
                ),
                metadata=(
                    json.loads(result["metadata"])
                    if search_settings.include_metadatas
                    else {}
                ),
            )
            for result in results
        ]

    async def full_text_search(
        self, query_text: str, search_settings: VectorSearchSettings
    ) -> list[VectorSearchResult]:
        if not self.enable_fts:
            raise ValueError(
                "Full-text search is not enabled for this collection."
            )

        where_clauses = []
        params: list[Union[str, int]] = [query_text]

        if search_settings.filters:
            filters_clause = self._build_filters(
                search_settings.filters, params
            )
            where_clauses.append(filters_clause)

        if where_clauses:
            where_clause = (
                "WHERE "
                + " AND ".join(where_clauses)
                + " AND fts @@ websearch_to_tsquery('english', $1)"
            )
        else:
            where_clause = "WHERE fts @@ websearch_to_tsquery('english', $1)"

        query = f"""
            SELECT
                extraction_id, document_id, user_id, collection_ids, text, metadata,
                ts_rank(fts, websearch_to_tsquery('english', $1), 32) as rank
            FROM {self._get_table_name(PostgresVectorHandler.TABLE_NAME)}
            {where_clause}
        """

        query += f"""
            ORDER BY rank DESC
            OFFSET ${len(params)+1} LIMIT ${len(params)+2}
        """
        params.extend(
            [
                search_settings.offset,
                search_settings.hybrid_search_settings.full_text_limit,
            ]
        )

        results = await self.connection_manager.fetch_query(query, params)
        return [
            VectorSearchResult(
                extraction_id=UUID(str(r["extraction_id"])),
                document_id=UUID(str(r["document_id"])),
                user_id=UUID(str(r["user_id"])),
                collection_ids=r["collection_ids"],
                text=r["text"],
                score=float(r["rank"]),
                metadata=json.loads(r["metadata"]),
            )
            for r in results
        ]

    async def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        search_settings: VectorSearchSettings,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        if search_settings.hybrid_search_settings is None:
            raise ValueError(
                "Please provide a valid `hybrid_search_settings` in the `search_settings`."
            )
        if (
            search_settings.hybrid_search_settings.full_text_limit
            < search_settings.search_limit
        ):
            raise ValueError(
                "The `full_text_limit` must be greater than or equal to the `search_limit`."
            )

        semantic_settings = copy.deepcopy(search_settings)
        semantic_settings.search_limit += search_settings.offset

        full_text_settings = copy.deepcopy(search_settings)
        full_text_settings.hybrid_search_settings.full_text_limit += (
            search_settings.offset
        )

        semantic_results: list[VectorSearchResult] = (
            await self.semantic_search(query_vector, semantic_settings)
        )
        full_text_results: list[VectorSearchResult] = (
            await self.full_text_search(query_text, full_text_settings)
        )

        semantic_limit = search_settings.search_limit
        full_text_limit = (
            search_settings.hybrid_search_settings.full_text_limit
        )
        semantic_weight = (
            search_settings.hybrid_search_settings.semantic_weight
        )
        full_text_weight = (
            search_settings.hybrid_search_settings.full_text_weight
        )
        rrf_k = search_settings.hybrid_search_settings.rrf_k

        combined_results: dict[uuid.UUID, HybridSearchIntermediateResult] = {}

        for rank, result in enumerate(semantic_results, 1):
            combined_results[result.extraction_id] = {
                "semantic_rank": rank,
                "full_text_rank": full_text_limit,
                "data": result,
                "rrf_score": 0.0,  # Initialize with 0, will be calculated later
            }

        for rank, result in enumerate(full_text_results, 1):
            if result.extraction_id in combined_results:
                combined_results[result.extraction_id]["full_text_rank"] = rank
            else:
                combined_results[result.extraction_id] = {
                    "semantic_rank": semantic_limit,
                    "full_text_rank": rank,
                    "data": result,
                    "rrf_score": 0.0,  # Initialize with 0, will be calculated later
                }

        combined_results = {
            k: v
            for k, v in combined_results.items()
            if v["semantic_rank"] <= semantic_limit * 2
            and v["full_text_rank"] <= full_text_limit * 2
        }

        for hyb_result in combined_results.values():
            semantic_score = 1 / (rrf_k + hyb_result["semantic_rank"])
            full_text_score = 1 / (rrf_k + hyb_result["full_text_rank"])
            hyb_result["rrf_score"] = (
                semantic_score * semantic_weight
                + full_text_score * full_text_weight
            ) / (semantic_weight + full_text_weight)

        sorted_results = sorted(
            combined_results.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )
        offset_results = sorted_results[
            search_settings.offset : search_settings.offset
            + search_settings.search_limit
        ]

        return [
            VectorSearchResult(
                extraction_id=result["data"].extraction_id,
                document_id=result["data"].document_id,
                user_id=result["data"].user_id,
                collection_ids=result["data"].collection_ids,
                text=result["data"].text,
                score=result["rrf_score"],
                metadata={
                    **result["data"].metadata,
                    "semantic_rank": result["semantic_rank"],
                    "full_text_rank": result["full_text_rank"],
                },
            )
            for result in offset_results
        ]

    async def delete(
        self, filters: dict[str, Any]
    ) -> dict[str, dict[str, str]]:
        params: list[Union[str, int]] = []
        where_clause = self._build_filters(filters, params)

        query = f"""
        DELETE FROM {self._get_table_name(PostgresVectorHandler.TABLE_NAME)}
        WHERE {where_clause}
        RETURNING extraction_id, document_id, text;
        """

        results = await self.connection_manager.fetch_query(query, params)

        return {
            str(result["extraction_id"]): {
                "status": "deleted",
                "extraction_id": str(result["extraction_id"]),
                "document_id": str(result["document_id"]),
                "text": result["text"],
            }
            for result in results
        }

    async def assign_document_to_collection_vector(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        query = f"""
        UPDATE {self._get_table_name(PostgresVectorHandler.TABLE_NAME)}
        SET collection_ids = array_append(collection_ids, $1)
        WHERE document_id = $2 AND NOT ($1 = ANY(collection_ids));
        """
        await self.connection_manager.execute_query(
            query, (str(collection_id), str(document_id))
        )

    async def remove_document_from_collection_vector(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        query = f"""
        UPDATE {self._get_table_name(PostgresVectorHandler.TABLE_NAME)}
        SET collection_ids = array_remove(collection_ids, $1)
        WHERE document_id = $2;
        """
        await self.connection_manager.execute_query(
            query, (collection_id, document_id)
        )

    async def delete_user_vector(self, user_id: UUID) -> None:
        query = f"""
        DELETE FROM {self._get_table_name(PostgresVectorHandler.TABLE_NAME)}
        WHERE user_id = $1;
        """
        await self.connection_manager.execute_query(query, (user_id,))

    async def delete_collection_vector(self, collection_id: UUID) -> None:
        query = f"""
         DELETE FROM {self._get_table_name(PostgresVectorHandler.TABLE_NAME)}
         WHERE $1 = ANY(collection_ids)
         RETURNING collection_ids
         """
        results = await self.connection_manager.fetchrow_query(
            query, (collection_id,)
        )
        return None

    async def get_document_chunks(
        self,
        document_id: UUID,
        offset: int = 0,
        limit: int = -1,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        vector_select = ", vec" if include_vectors else ""
        limit_clause = f"LIMIT {limit}" if limit > -1 else ""

        query = f"""
        SELECT extraction_id, document_id, user_id, collection_ids, text, metadata{vector_select}, COUNT(*) OVER() AS total
        FROM {self._get_table_name(PostgresVectorHandler.TABLE_NAME)}
        WHERE document_id = $1
        ORDER BY (metadata->>'chunk_order')::integer
        OFFSET $2
        {limit_clause};
        """

        params = [document_id, offset]

        results = await self.connection_manager.fetch_query(query, params)

        chunks = []
        total = 0
        if results:
            total = results[0].get("total", 0)
            chunks = [
                {
                    "extraction_id": result["extraction_id"],
                    "document_id": result["document_id"],
                    "user_id": result["user_id"],
                    "collection_ids": result["collection_ids"],
                    "text": result["text"],
                    "metadata": json.loads(result["metadata"]),
                    "vector": (
                        json.loads(result["vec"]) if include_vectors else None
                    ),
                }
                for result in results
            ]

        return {"results": chunks, "total_entries": total}

    async def get_chunk(self, extraction_id: UUID) -> Optional[dict[str, Any]]:
        query = f"""
        SELECT extraction_id, document_id, user_id, collection_ids, text, metadata
        FROM {self._get_table_name(PostgresVectorHandler.TABLE_NAME)}
        WHERE extraction_id = $1;
        """

        result = await self.connection_manager.fetchrow_query(
            query, (extraction_id,)
        )

        if result:
            return {
                "extraction_id": result["extraction_id"],
                "document_id": result["document_id"],
                "user_id": result["user_id"],
                "collection_ids": result["collection_ids"],
                "text": result["text"],
                "metadata": json.loads(result["metadata"]),
            }
        return None

    async def create_index(
        self,
        table_name: Optional[VectorTableName] = None,
        index_measure: IndexMeasure = IndexMeasure.cosine_distance,
        index_method: IndexMethod = IndexMethod.auto,
        index_arguments: Optional[
            Union[IndexArgsIVFFlat, IndexArgsHNSW]
        ] = None,
        index_name: Optional[str] = None,
        concurrently: bool = True,
    ) -> None:
        """
        Creates an index for the collection.

        Note:
            When `vecs` creates an index on a pgvector column in PostgreSQL, it uses a multi-step
            process that enables performant indexes to be built for large collections with low end
            database hardware.

            Those steps are:

            - Creates a new table with a different name
            - Randomly selects records from the existing table
            - Inserts the random records from the existing table into the new table
            - Creates the requested vector index on the new table
            - Upserts all data from the existing table into the new table
            - Drops the existing table
            - Renames the new table to the existing tables name

            If you create dependencies (like views) on the table that underpins
            a `vecs.Collection` the `create_index` step may require you to drop those dependencies before
            it will succeed.

        Args:
            index_measure (IndexMeasure, optional): The measure to index for. Defaults to 'cosine_distance'.
            index_method (IndexMethod, optional): The indexing method to use. Defaults to 'auto'.
            index_arguments: (IndexArgsIVFFlat | IndexArgsHNSW, optional): Index type specific arguments
            index_name (str, optional): The name of the index to create. Defaults to None.
            concurrently (bool, optional): Whether to create the index concurrently. Defaults to True.
        Raises:
            ArgError: If an invalid index method is used, or if *replace* is False and an index already exists.
        """

        if table_name == VectorTableName.VECTORS:
            table_name_str = f"{self.project_name}.{VectorTableName.VECTORS}"  # TODO - Fix bug in vector table naming convention
            col_name = "vec"
        elif table_name == VectorTableName.ENTITIES_DOCUMENT:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.ENTITIES_DOCUMENT}"
            )
            col_name = "description_embedding"
        elif table_name == VectorTableName.ENTITIES_COLLECTION:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.ENTITIES_COLLECTION}"
            )
            col_name = "description_embedding"
        elif table_name == VectorTableName.COMMUNITIES:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.COMMUNITIES}"
            )
            col_name = "embedding"
        else:
            raise ArgError("invalid table name")
        if index_method not in (
            IndexMethod.ivfflat,
            IndexMethod.hnsw,
            IndexMethod.auto,
        ):
            raise ArgError("invalid index method")

        if index_arguments:
            # Disallow case where user submits index arguments but uses the
            # IndexMethod.auto index (index build arguments should only be
            # used with a specific index)
            if index_method == IndexMethod.auto:
                raise ArgError(
                    "Index build parameters are not allowed when using the IndexMethod.auto index."
                )
            # Disallow case where user specifies one index type but submits
            # index build arguments for the other index type
            if (
                isinstance(index_arguments, IndexArgsHNSW)
                and index_method != IndexMethod.hnsw
            ) or (
                isinstance(index_arguments, IndexArgsIVFFlat)
                and index_method != IndexMethod.ivfflat
            ):
                raise ArgError(
                    f"{index_arguments.__class__.__name__} build parameters were supplied but {index_method} index was specified."
                )

        if index_method == IndexMethod.auto:
            index_method = IndexMethod.hnsw

        ops = index_measure_to_ops(
            index_measure  # , quantization_type=self.quantization_type
        )

        if ops is None:
            raise ArgError("Unknown index measure")

        concurrently_sql = "CONCURRENTLY" if concurrently else ""

        index_name = (
            index_name
            or f"ix_{ops}_{index_method}__{time.strftime('%Y%m%d%H%M%S')}"
        )

        create_index_sql = f"""
        CREATE INDEX {concurrently_sql} {index_name}
        ON {table_name_str}
        USING {index_method} ({col_name} {ops}) {self._get_index_options(index_method, index_arguments)};
        """

        try:
            if concurrently:
                async with (
                    self.connection_manager.pool.get_connection() as conn  # type: ignore
                ):
                    # Disable automatic transaction management
                    await conn.execute(
                        "SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL READ COMMITTED"
                    )
                    await conn.execute(create_index_sql)
            else:
                # Non-concurrent index creation can use normal query execution
                await self.connection_manager.execute_query(create_index_sql)
        except Exception as e:
            raise Exception(f"Failed to create index: {e}")
        return None

    def _build_filters(
        self, filters: dict, parameters: list[Union[str, int]]
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
                        raise FilterError(
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
                        raise FilterError("unknown operator")

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
                            raise FilterError(
                                "argument to $in filter must be a list"
                            )
                        parameters.append(json.dumps(clause))
                        return f"{json_col}->'{key}' = ANY(SELECT jsonb_array_elements(${len(parameters)}::jsonb))"
                    elif op == "$contains":
                        if not isinstance(clause, (int, str, float, list)):
                            raise FilterError(
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

    async def list_indices(
        self, table_name: Optional[VectorTableName] = None
    ) -> list[dict[str, Any]]:
        """
        Lists all vector indices for the specified table.

        Args:
            table_name (VectorTableName, optional): The table to list indices for.
                If None, defaults to VECTORS table.

        Returns:
            List[dict]: List of indices with their properties

        Raises:
            ArgError: If an invalid table name is provided
        """
        if table_name == VectorTableName.VECTORS:
            table_name_str = f"{self.project_name}.{VectorTableName.VECTORS}"
            col_name = "vec"
        elif table_name == VectorTableName.ENTITIES_DOCUMENT:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.ENTITIES_DOCUMENT}"
            )
            col_name = "description_embedding"
        elif table_name == VectorTableName.ENTITIES_COLLECTION:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.ENTITIES_COLLECTION}"
            )
        elif table_name == VectorTableName.COMMUNITIES:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.COMMUNITIES}"
            )
            col_name = "embedding"
        else:
            raise ArgError("invalid table name")

        query = """
        SELECT
            i.indexname as name,
            i.indexdef as definition,
            am.amname as method,
            pg_relation_size(c.oid) as size_in_bytes,
            COALESCE(psat.idx_scan, 0) as number_of_scans,
            COALESCE(psat.idx_tup_read, 0) as tuples_read,
            COALESCE(psat.idx_tup_fetch, 0) as tuples_fetched
        FROM pg_indexes i
        JOIN pg_class c ON c.relname = i.indexname
        JOIN pg_am am ON c.relam = am.oid
        LEFT JOIN pg_stat_user_indexes psat ON psat.indexrelname = i.indexname
            AND psat.schemaname = i.schemaname
        WHERE i.schemaname || '.' || i.tablename = $1
        AND i.indexdef LIKE $2;
        """

        results = await self.connection_manager.fetch_query(
            query, (table_name_str, f"%({col_name}%")
        )

        return [
            {
                "name": result["name"],
                "definition": result["definition"],
                "method": result["method"],
                "size_in_bytes": result["size_in_bytes"],
                "number_of_scans": result["number_of_scans"],
                "tuples_read": result["tuples_read"],
                "tuples_fetched": result["tuples_fetched"],
            }
            for result in results
        ]

    async def delete_index(
        self,
        index_name: str,
        table_name: Optional[VectorTableName] = None,
        concurrently: bool = True,
    ) -> None:
        """
        Deletes a vector index.

        Args:
            index_name (str): Name of the index to delete
            table_name (VectorTableName, optional): Table the index belongs to
            concurrently (bool): Whether to drop the index concurrently

        Raises:
            ArgError: If table name is invalid or index doesn't exist
            Exception: If index deletion fails
        """
        # Validate table name and get column name
        if table_name == VectorTableName.VECTORS:
            table_name_str = f"{self.project_name}.{VectorTableName.VECTORS}"
            col_name = "vec"
        elif table_name == VectorTableName.ENTITIES_DOCUMENT:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.ENTITIES_DOCUMENT}"
            )
            col_name = "description_embedding"
        elif table_name == VectorTableName.ENTITIES_COLLECTION:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.ENTITIES_COLLECTION}"
            )
            col_name = "description_embedding"
        elif table_name == VectorTableName.COMMUNITIES:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.COMMUNITIES}"
            )
            col_name = "embedding"
        else:
            raise ArgError("invalid table name")

        # Extract schema and base table name
        schema_name, base_table_name = table_name_str.split(".")

        # Verify index exists and is a vector index
        query = """
        SELECT indexdef
        FROM pg_indexes
        WHERE indexname = $1
        AND schemaname = $2
        AND tablename = $3
        AND indexdef LIKE $4
        """

        result = await self.connection_manager.fetchrow_query(
            query, (index_name, schema_name, base_table_name, f"%({col_name}%")
        )

        if not result:
            raise ArgError(
                f"Vector index '{index_name}' does not exist on table {table_name_str}"
            )

        # Drop the index
        concurrently_sql = "CONCURRENTLY" if concurrently else ""
        drop_query = (
            f"DROP INDEX {concurrently_sql} {schema_name}.{index_name}"
        )

        try:
            if concurrently:
                async with (
                    self.connection_manager.pool.get_connection() as conn  # type: ignore
                ):
                    # Disable automatic transaction management
                    await conn.execute(
                        "SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL READ COMMITTED"
                    )
                    await conn.execute(drop_query)
            else:
                await self.connection_manager.execute_query(drop_query)
        except Exception as e:
            raise Exception(f"Failed to delete index: {e}")

    async def get_semantic_neighbors(
        self,
        document_id: UUID,
        chunk_id: UUID,
        limit: int = 10,
        similarity_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:

        table_name = self._get_table_name(PostgresVectorHandler.TABLE_NAME)
        query = f"""
        WITH target_vector AS (
            SELECT vec FROM {table_name}
            WHERE document_id = $1 AND extraction_id = $2
        )
        SELECT t.extraction_id, t.text, t.metadata, t.document_id, (t.vec <=> tv.vec) AS similarity
        FROM {table_name} t, target_vector tv
        WHERE (t.vec <=> tv.vec) >= $3
            AND t.document_id = $1
            AND t.extraction_id != $2
        ORDER BY similarity ASC
        LIMIT $4
        """
        results = await self.connection_manager.fetch_query(
            query,
            (str(document_id), str(chunk_id), similarity_threshold, limit),
        )

        return [
            {
                "extraction_id": str(r["extraction_id"]),
                "text": r["text"],
                "metadata": json.loads(r["metadata"]),
                "document_id": str(r["document_id"]),
                "similarity": float(r["similarity"]),
            }
            for r in results
        ]

    def _get_index_options(
        self,
        method: IndexMethod,
        index_arguments: Optional[Union[IndexArgsIVFFlat, IndexArgsHNSW]],
    ) -> str:
        if method == IndexMethod.ivfflat:
            if isinstance(index_arguments, IndexArgsIVFFlat):
                return f"WITH (lists={index_arguments.n_lists})"
            else:
                # Default value if no arguments provided
                return "WITH (lists=100)"
        elif method == IndexMethod.hnsw:
            if isinstance(index_arguments, IndexArgsHNSW):
                return f"WITH (m={index_arguments.m}, ef_construction={index_arguments.ef_construction})"
            else:
                # Default values if no arguments provided
                return "WITH (m=16, ef_construction=64)"
        else:
            return ""  # No options for other methods

    def _get_index_type(self, method: IndexMethod) -> str:
        if method == IndexMethod.ivfflat:
            return "ivfflat"
        elif method == IndexMethod.hnsw:
            return "hnsw"
        elif method == IndexMethod.auto:
            # Here you might want to implement logic to choose between ivfflat and hnsw
            return "hnsw"

    def _get_index_operator(self, measure: IndexMeasure) -> str:
        if measure == IndexMeasure.l2_distance:
            return "vector_l2_ops"
        elif measure == IndexMeasure.max_inner_product:
            return "vector_ip_ops"
        elif measure == IndexMeasure.cosine_distance:
            return "vector_cosine_ops"

    def _get_distance_function(self, imeasure_obj: IndexMeasure) -> str:
        if imeasure_obj == IndexMeasure.cosine_distance:
            return "<=>"
        elif imeasure_obj == IndexMeasure.l2_distance:
            return "l2_distance"
        elif imeasure_obj == IndexMeasure.max_inner_product:
            return "max_inner_product"
