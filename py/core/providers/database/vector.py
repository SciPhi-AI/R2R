import copy
import json
import logging
import time
import uuid
from typing import Any, Optional, Tuple, TypedDict, Union
from uuid import UUID

from core.base import VectorEntry, VectorQuantizationType, VectorSearchResult
from core.base.abstractions import VectorSearchSettings
from shared.abstractions.vector import (
    IndexArgsHNSW,
    IndexArgsIVFFlat,
    IndexMeasure,
    IndexMethod,
    VectorTableName,
)

from .base import DatabaseMixin
from .vecs.exc import ArgError, FilterError

logger = logging.getLogger()
from shared.utils import _decorate_vector_type


def index_measure_to_ops(
    measure: IndexMeasure, quantization_type: VectorQuantizationType
):
    return _decorate_vector_type(measure.ops, quantization_type)


class HybridSearchIntermediateResult(TypedDict):
    semantic_rank: int
    full_text_rank: int
    data: VectorSearchResult
    rrf_score: float


class VectorDBMixin(DatabaseMixin):
    TABLE_NAME = "vector"

    COLUMN_VARS = [
        "extraction_id",
        "document_id",
        "user_id",
        "collection_ids",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def create_table(self):
        # TODO - Move ids to `UUID` type
        # Create the vector table if it doesn't exist
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(VectorDBMixin.TABLE_NAME)} (
            extraction_id UUID PRIMARY KEY,
            document_id UUID,
            user_id UUID,
            collection_ids UUID[],
            vec vector({self.dimension}),
            text TEXT,
            metadata JSONB
            {",fts tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED" if self.enable_fts else ""}
        );
        CREATE INDEX IF NOT EXISTS idx_vectors_document_id ON {self._get_table_name(VectorDBMixin.TABLE_NAME)} (document_id);
        CREATE INDEX IF NOT EXISTS idx_vectors_user_id ON {self._get_table_name(VectorDBMixin.TABLE_NAME)} (user_id);
        CREATE INDEX IF NOT EXISTS idx_vectors_collection_ids ON {self._get_table_name(VectorDBMixin.TABLE_NAME)} USING GIN (collection_ids);
        CREATE INDEX IF NOT EXISTS idx_vectors_text ON {self._get_table_name(VectorDBMixin.TABLE_NAME)} USING GIN (to_tsvector('english', text));
        """
        if self.enable_fts:
            query += f"""
            CREATE INDEX IF NOT EXISTS idx_vectors_text ON {self._get_table_name(VectorDBMixin.TABLE_NAME)} USING GIN (to_tsvector('english', text));
            """

        await self.execute_query(query)

    async def upsert(self, entry: VectorEntry) -> None:
        query = f"""
        INSERT INTO {self._get_table_name(VectorDBMixin.TABLE_NAME)}
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
        await self.execute_query(
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
        INSERT INTO {self._get_table_name(VectorDBMixin.TABLE_NAME)}
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
        await self.execute_many(query, params)

    async def semantic_search(
        self, query_vector: list[float], search_settings: VectorSearchSettings
    ) -> list[VectorSearchResult]:
        try:
            imeasure_obj = IndexMeasure(search_settings.index_measure)
        except ValueError:
            raise ValueError("Invalid index measure")

        table_name = self._get_table_name(VectorDBMixin.TABLE_NAME)
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
        params = [str(query_vector)]
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

        results = await self.fetch_query(query, params)

        return [
            VectorSearchResult(
                extraction_id=str(result["extraction_id"]),
                document_id=str(result["document_id"]),
                user_id=str(result["user_id"]),
                collection_ids=result["collection_ids"],
                text=result["text"],
                score=(
                    (1 - float(result["distance"]))
                    if search_settings.include_values
                    else None
                ),
                metadata=(
                    json.loads(result["metadata"])
                    if search_settings.include_metadatas
                    else None
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
        params = [query_text]

        if search_settings.filters:
            filters_clause = self._build_filters(search_settings.filters, params)
            where_clauses.append(filters_clause)

        if where_clauses:
            where_clause = "WHERE " + " AND ".join(where_clauses) + " AND fts @@ websearch_to_tsquery('english', $1)"
        else:
            where_clause = "WHERE fts @@ websearch_to_tsquery('english', $1)"

        query = f"""
            SELECT
                extraction_id, document_id, user_id, collection_ids, text, metadata,
                ts_rank(fts, websearch_to_tsquery('english', $1), 32) as rank
            FROM {self._get_table_name(VectorDBMixin.TABLE_NAME)}
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

        results = await self.fetch_query(query, params)
        return [
            VectorSearchResult(
                extraction_id=str(r["extraction_id"]),
                document_id=str(r["document_id"]),
                user_id=str(r["user_id"]),
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
        params = []
        where_clause = self._build_filters(filters, params)

        query = f"""
        DELETE FROM {self._get_table_name(VectorDBMixin.TABLE_NAME)}
        WHERE {where_clause}
        RETURNING extraction_id, document_id, text;
        """

        results = await self.fetch_query(query, params)

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
        self, document_id: str, collection_id: str
    ) -> None:
        query = f"""
        UPDATE {self._get_table_name(VectorDBMixin.TABLE_NAME)}
        SET collection_ids = array_append(collection_ids, $1)
        WHERE document_id = $2 AND NOT ($1 = ANY(collection_ids));
        """
        await self.execute_query(query, (str(collection_id), str(document_id)))

    async def remove_document_from_collection_vector(
        self, document_id: str, collection_id: str
    ) -> None:
        query = f"""
        UPDATE {self._get_table_name(VectorDBMixin.TABLE_NAME)}
        SET collection_ids = array_remove(collection_ids, $1)
        WHERE document_id = $2;
        """
        await self.execute_query(query, (collection_id, document_id))

    async def delete_user_vector(self, user_id: str) -> None:
        query = f"""
        DELETE FROM {self._get_table_name(VectorDBMixin.TABLE_NAME)}
        WHERE user_id = $1;
        """
        await self.execute_query(query, (user_id,))

    async def delete_collection_vector(self, collection_id: str) -> None:
        query = f"""
         DELETE FROM {self._get_table_name(VectorDBMixin.TABLE_NAME)}
         WHERE $1 = ANY(collection_ids)
         RETURNING collection_ids
         """
        results = await self.fetchrow_query(query, (collection_id,))
        deleted_count = len(results)
        return deleted_count

    async def get_document_chunks(
        self,
        document_id: str,
        offset: int = 0,
        limit: int = -1,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        vector_select = ", vec" if include_vectors else ""
        limit_clause = f"LIMIT {limit}" if limit > -1 else ""

        query = f"""
        SELECT extraction_id, document_id, user_id, collection_ids, text, metadata{vector_select}, COUNT(*) OVER() AS total
        FROM {self._get_table_name(VectorDBMixin.TABLE_NAME)}
        WHERE document_id = $1
        OFFSET $2
        {limit_clause};
        """

        params = [document_id, offset]

        results = await self.fetch_query(query, params)

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

    async def create_index(
        self,
        table_name: Optional[VectorTableName] = None,
        measure: IndexMeasure = IndexMeasure.cosine_distance,
        method: IndexMethod = IndexMethod.auto,
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
            measure (IndexMeasure, optional): The measure to index for. Defaults to 'cosine_distance'.
            method (IndexMethod, optional): The indexing method to use. Defaults to 'auto'.
            index_arguments: (IndexArgsIVFFlat | IndexArgsHNSW, optional): Index type specific arguments
            replace (bool, optional): Whether to replace the existing index. Defaults to True.
            concurrently (bool, optional): Whether to create the index concurrently. Defaults to True.
        Raises:
            ArgError: If an invalid index method is used, or if *replace* is False and an index already exists.
        """

        if table_name == VectorTableName.RAW_CHUNKS:
            table_name_str = f"{self.project_name}.{VectorTableName.RAW_CHUNKS}"  # TODO - Fix bug in vector table naming convention
            col_name = "vec"
        elif table_name == VectorTableName.ENTITIES_DOCUMENT:
            table_name_str = f"{self.project_name}.{VectorTableName.ENTITIES_DOCUMENT}"
            col_name = "description_embedding"
        elif table_name == VectorTableName.ENTITIES_COLLECTION:
            table_name_str = f"{self.project_name}.{VectorTableName.ENTITIES_COLLECTION}"
            col_name = "description_embedding"
        elif table_name == VectorTableName.COMMUNITIES:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.COMMUNITIES}"
            )
            col_name = "embedding"
        else:
            raise ArgError("invalid table name")
        if method not in (
            IndexMethod.ivfflat,
            IndexMethod.hnsw,
            IndexMethod.auto,
        ):
            raise ArgError("invalid index method")

        if index_arguments:
            # Disallow case where user submits index arguments but uses the
            # IndexMethod.auto index (index build arguments should only be
            # used with a specific index)
            if method == IndexMethod.auto:
                raise ArgError(
                    "Index build parameters are not allowed when using the IndexMethod.auto index."
                )
            # Disallow case where user specifies one index type but submits
            # index build arguments for the other index type
            if (
                isinstance(index_arguments, IndexArgsHNSW)
                and method != IndexMethod.hnsw
            ) or (
                isinstance(index_arguments, IndexArgsIVFFlat)
                and method != IndexMethod.ivfflat
            ):
                raise ArgError(
                    f"{index_arguments.__class__.__name__} build parameters were supplied but {method} index was specified."
                )

        if method == IndexMethod.auto:
            method = IndexMethod.hnsw

        ops = index_measure_to_ops(
            measure, quantization_type=self.quantization_type
        )

        if ops is None:
            raise ArgError("Unknown index measure")

        concurrently_sql = "CONCURRENTLY" if concurrently else ""

        index_name = (
            index_name or f"ix_{ops}_{method}__{time.strftime('%Y%m%d%H%M%S')}"
        )

        create_index_sql = f"""
        CREATE INDEX {concurrently_sql} {index_name}
        ON {table_name_str}
        USING {method} ({col_name} {ops}) {self._get_index_options(method, index_arguments)};
        """

        try:
            if concurrently:
                # For concurrent index creation, we need to execute outside a transaction
                await self.execute_query(
                    create_index_sql, isolation_level="AUTOCOMMIT"
                )
            else:
                await self.execute_query(create_index_sql)
        except Exception as e:
            raise Exception(f"Failed to create index: {e}")

        return None

    def _build_filters(
        self, filters: dict, parameters: list[dict]
    ) -> Tuple[str, list[Any]]:

        def parse_condition(key: str, value: Any) -> str:
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

    async def get_semantic_neighbors(
        self,
        document_id: UUID,
        chunk_id: UUID,
        limit: int = 10,
        similarity_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:

        table_name = self._get_table_name(VectorDBMixin.TABLE_NAME)
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

        results = await self.fetch_query(
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
