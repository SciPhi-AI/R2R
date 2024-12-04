import copy
import json
import logging
import time
import uuid
from typing import Any, Optional, TypedDict
from uuid import UUID

import numpy as np

from core.base import (
    ChunkHandler,
    ChunkSearchResult,
    IndexArgsHNSW,
    IndexArgsIVFFlat,
    IndexMeasure,
    IndexMethod,
    R2RException,
    SearchSettings,
    VectorEntry,
    VectorQuantizationType,
    VectorTableName,
)

from .base import PostgresConnectionManager
from .vecs.exc import ArgError, FilterError

logger = logging.getLogger()
from core.base.utils import _decorate_vector_type


def psql_quote_literal(value: str) -> str:
    """
    Safely quote a string literal for PostgreSQL to prevent SQL injection.
    This is a simple implementation - in production, you should use proper parameterization
    or your database driver's quoting functions.
    """
    return "'" + value.replace("'", "''") + "'"


def index_measure_to_ops(
    measure: IndexMeasure,
    quantization_type: VectorQuantizationType = VectorQuantizationType.FP32,
):
    return _decorate_vector_type(measure.ops, quantization_type)


def quantize_vector_to_binary(
    vector: list[float] | np.ndarray,
    threshold: float = 0.0,
) -> bytes:
    """
    Quantizes a float vector to a binary vector string for PostgreSQL bit type.
    Used when quantization_type is INT1.

    Args:
        vector (List[float] | np.ndarray): Input vector of floats
        threshold (float, optional): Threshold for binarization. Defaults to 0.0.

    Returns:
        str: Binary string representation for PostgreSQL bit type
    """
    # Convert input to numpy array if it isn't already
    if not isinstance(vector, np.ndarray):
        vector = np.array(vector)

    # Convert to binary (1 where value > threshold, 0 otherwise)
    binary_vector = (vector > threshold).astype(int)

    # Convert to string of 1s and 0s
    # Convert to string of 1s and 0s, then to bytes
    binary_string = "".join(map(str, binary_vector))
    return binary_string.encode("ascii")


class HybridSearchIntermediateResult(TypedDict):
    semantic_rank: int
    full_text_rank: int
    data: ChunkSearchResult
    rrf_score: float


class PostgresChunkHandler(ChunkHandler):
    TABLE_NAME = VectorTableName.CHUNKS

    COLUMN_VARS = [
        "id",
        "document_id",
        "owner_id",
        "collection_ids",
    ]

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        dimension: int,
        quantization_type: VectorQuantizationType,
        enable_fts: bool = False,
    ):
        super().__init__(project_name, connection_manager)
        self.dimension = dimension
        self.quantization_type = quantization_type
        self.enable_fts = enable_fts

    async def create_tables(self):
        # Check for old table name first
        check_query = """
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

        binary_col = (
            ""
            if self.quantization_type != VectorQuantizationType.INT1
            else f"vec_binary bit({self.dimension}),"
        )

        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresChunkHandler.TABLE_NAME)} (
            id UUID PRIMARY KEY,
            document_id UUID,
            owner_id UUID,
            collection_ids UUID[],
            vec vector({self.dimension}),
            {binary_col}
            text TEXT,
            metadata JSONB
            {",fts tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED" if self.enable_fts else ""}
        );
        CREATE INDEX IF NOT EXISTS idx_vectors_document_id ON {self._get_table_name(PostgresChunkHandler.TABLE_NAME)} (document_id);
        CREATE INDEX IF NOT EXISTS idx_vectors_owner_id ON {self._get_table_name(PostgresChunkHandler.TABLE_NAME)} (owner_id);
        CREATE INDEX IF NOT EXISTS idx_vectors_collection_ids ON {self._get_table_name(PostgresChunkHandler.TABLE_NAME)} USING GIN (collection_ids);
        """
        if self.enable_fts:
            query += f"""
            CREATE INDEX IF NOT EXISTS idx_vectors_text ON {self._get_table_name(PostgresChunkHandler.TABLE_NAME)} USING GIN (to_tsvector('english', text));
            """

        await self.connection_manager.execute_query(query)

    async def upsert(self, entry: VectorEntry) -> None:
        """
        Upsert function that handles vector quantization only when quantization_type is INT1.
        Matches the table schema where vec_binary column only exists for INT1 quantization.
        """
        # Check the quantization type to determine which columns to use
        if self.quantization_type == VectorQuantizationType.INT1:
            # For quantized vectors, use vec_binary column
            query = f"""
            INSERT INTO {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
            (id, document_id, owner_id, collection_ids, vec, vec_binary, text, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::bit({self.dimension}), $7, $8)
            ON CONFLICT (id) DO UPDATE SET
            document_id = EXCLUDED.document_id,
            owner_id = EXCLUDED.owner_id,
            collection_ids = EXCLUDED.collection_ids,
            vec = EXCLUDED.vec,
            vec_binary = EXCLUDED.vec_binary,
            text = EXCLUDED.text,
            metadata = EXCLUDED.metadata;
            """
            await self.connection_manager.execute_query(
                query,
                (
                    entry.id,
                    entry.document_id,
                    entry.owner_id,
                    entry.collection_ids,
                    str(entry.vector.data),
                    quantize_vector_to_binary(
                        entry.vector.data
                    ),  # Convert to binary
                    entry.text,
                    json.dumps(entry.metadata),
                ),
            )
        else:
            # For regular vectors, use vec column only
            query = f"""
            INSERT INTO {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
            (id, document_id, owner_id, collection_ids, vec, text, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
            document_id = EXCLUDED.document_id,
            owner_id = EXCLUDED.owner_id,
            collection_ids = EXCLUDED.collection_ids,
            vec = EXCLUDED.vec,
            text = EXCLUDED.text,
            metadata = EXCLUDED.metadata;
            """

            await self.connection_manager.execute_query(
                query,
                (
                    entry.id,
                    entry.document_id,
                    entry.owner_id,
                    entry.collection_ids,
                    str(entry.vector.data),
                    entry.text,
                    json.dumps(entry.metadata),
                ),
            )

    async def upsert_entries(self, entries: list[VectorEntry]) -> None:
        """
        Batch upsert function that handles vector quantization only when quantization_type is INT1.
        Matches the table schema where vec_binary column only exists for INT1 quantization.
        """
        if self.quantization_type == VectorQuantizationType.INT1:
            # For quantized vectors, use vec_binary column
            query = f"""
            INSERT INTO {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
            (id, document_id, owner_id, collection_ids, vec, vec_binary, text, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::bit({self.dimension}), $7, $8)
            ON CONFLICT (id) DO UPDATE SET
            document_id = EXCLUDED.document_id,
            owner_id = EXCLUDED.owner_id,
            collection_ids = EXCLUDED.collection_ids,
            vec = EXCLUDED.vec,
            vec_binary = EXCLUDED.vec_binary,
            text = EXCLUDED.text,
            metadata = EXCLUDED.metadata;
            """
            bin_params = [
                (
                    entry.id,
                    entry.document_id,
                    entry.owner_id,
                    entry.collection_ids,
                    str(entry.vector.data),
                    quantize_vector_to_binary(
                        entry.vector.data
                    ),  # Convert to binary
                    entry.text,
                    json.dumps(entry.metadata),
                )
                for entry in entries
            ]
            await self.connection_manager.execute_many(query, bin_params)

        else:
            # For regular vectors, use vec column only
            query = f"""
            INSERT INTO {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
            (id, document_id, owner_id, collection_ids, vec, text, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
            document_id = EXCLUDED.document_id,
            owner_id = EXCLUDED.owner_id,
            collection_ids = EXCLUDED.collection_ids,
            vec = EXCLUDED.vec,
            text = EXCLUDED.text,
            metadata = EXCLUDED.metadata;
            """
            params = [
                (
                    entry.id,
                    entry.document_id,
                    entry.owner_id,
                    entry.collection_ids,
                    str(entry.vector.data),
                    entry.text,
                    json.dumps(entry.metadata),
                )
                for entry in entries
            ]

            await self.connection_manager.execute_many(query, params)

    async def semantic_search(
        self, query_vector: list[float], search_settings: SearchSettings
    ) -> list[ChunkSearchResult]:
        try:
            imeasure_obj = IndexMeasure(
                search_settings.chunk_settings.index_measure
            )
        except ValueError:
            raise ValueError("Invalid index measure")

        table_name = self._get_table_name(PostgresChunkHandler.TABLE_NAME)
        cols = [
            f"{table_name}.id",
            f"{table_name}.document_id",
            f"{table_name}.owner_id",
            f"{table_name}.collection_ids",
            f"{table_name}.text",
        ]

        params: list[str | int | bytes] = []
        # For binary vectors (INT1), implement two-stage search
        if self.quantization_type == VectorQuantizationType.INT1:
            # Convert query vector to binary format
            binary_query = quantize_vector_to_binary(query_vector)
            # TODO - Put depth multiplier in config / settings
            extended_limit = (
                search_settings.limit * 20
            )  # Get 20x candidates for re-ranking
            if (
                imeasure_obj == IndexMeasure.hamming_distance
                or imeasure_obj == IndexMeasure.jaccard_distance
            ):
                binary_search_measure_repr = imeasure_obj.pgvector_repr
            else:
                binary_search_measure_repr = (
                    IndexMeasure.hamming_distance.pgvector_repr
                )

            # Use binary column and binary-specific distance measures for first stage
            stage1_distance = f"{table_name}.vec_binary {binary_search_measure_repr} $1::bit({self.dimension})"
            stage1_param = binary_query

            cols.append(
                f"{table_name}.vec"
            )  # Need original vector for re-ranking
            if search_settings.include_metadatas:
                cols.append(f"{table_name}.metadata")

            select_clause = ", ".join(cols)
            where_clause = ""
            params.append(stage1_param)

            if search_settings.filters:
                where_clause = self._build_filters(
                    search_settings.filters, params
                )
                where_clause = f"WHERE {where_clause}"

            # First stage: Get candidates using binary search
            query = f"""
            WITH candidates AS (
                SELECT {select_clause},
                    ({stage1_distance}) as binary_distance
                FROM {table_name}
                {where_clause}
                ORDER BY {stage1_distance}
                LIMIT ${len(params) + 1}
                OFFSET ${len(params) + 2}
            )
            -- Second stage: Re-rank using original vectors
            SELECT
                id,
                document_id,
                owner_id,
                collection_ids,
                text,
                {"metadata," if search_settings.include_metadatas else ""}
                (vec <=> ${len(params) + 4}::vector({self.dimension})) as distance
            FROM candidates
            ORDER BY distance
            LIMIT ${len(params) + 3}
            """

            params.extend(
                [
                    extended_limit,  # First stage limit
                    search_settings.offset,
                    search_settings.limit,  # Final limit
                    str(query_vector),  # For re-ranking
                ]
            )

        else:
            # Standard float vector handling - unchanged from original
            distance_calc = f"{table_name}.vec {search_settings.chunk_settings.index_measure.pgvector_repr} $1::vector({self.dimension})"
            query_param = str(query_vector)

            if search_settings.include_scores:
                cols.append(f"({distance_calc}) AS distance")
            if search_settings.include_metadatas:
                cols.append(f"{table_name}.metadata")

            select_clause = ", ".join(cols)
            where_clause = ""
            params.append(query_param)

            if search_settings.filters:
                where_clause = self._build_filters(
                    search_settings.filters, params
                )
                where_clause = f"WHERE {where_clause}"

            query = f"""
            SELECT {select_clause}
            FROM {table_name}
            {where_clause}
            ORDER BY {distance_calc}
            LIMIT ${len(params) + 1}
            OFFSET ${len(params) + 2}
            """
            params.extend([search_settings.limit, search_settings.offset])

        results = await self.connection_manager.fetch_query(query, params)

        return [
            ChunkSearchResult(
                id=UUID(str(result["id"])),
                document_id=UUID(str(result["document_id"])),
                owner_id=UUID(str(result["owner_id"])),
                collection_ids=result["collection_ids"],
                text=result["text"],
                score=(
                    (1 - float(result["distance"]))
                    if "distance" in result
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
        self, query_text: str, search_settings: SearchSettings
    ) -> list[ChunkSearchResult]:
        if not self.enable_fts:
            raise ValueError(
                "Full-text search is not enabled for this collection."
            )

        where_clauses = []
        params: list[str | int | bytes] = [query_text]

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
                id, document_id, owner_id, collection_ids, text, metadata,
                ts_rank(fts, websearch_to_tsquery('english', $1), 32) as rank
            FROM {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
            {where_clause}
        """

        query += f"""
            ORDER BY rank DESC
            OFFSET ${len(params)+1} LIMIT ${len(params)+2}
        """
        params.extend(
            [
                search_settings.offset,
                search_settings.hybrid_settings.full_text_limit,
            ]
        )

        results = await self.connection_manager.fetch_query(query, params)
        return [
            ChunkSearchResult(
                id=UUID(str(r["id"])),
                document_id=UUID(str(r["document_id"])),
                owner_id=UUID(str(r["owner_id"])),
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
        search_settings: SearchSettings,
        *args,
        **kwargs,
    ) -> list[ChunkSearchResult]:
        if search_settings.hybrid_settings is None:
            raise ValueError(
                "Please provide a valid `hybrid_settings` in the `search_settings`."
            )
        if (
            search_settings.hybrid_settings.full_text_limit
            < search_settings.limit
        ):
            raise ValueError(
                "The `full_text_limit` must be greater than or equal to the `limit`."
            )

        semantic_settings = copy.deepcopy(search_settings)
        semantic_settings.limit += search_settings.offset

        full_text_settings = copy.deepcopy(search_settings)
        full_text_settings.hybrid_settings.full_text_limit += (
            search_settings.offset
        )

        semantic_results: list[ChunkSearchResult] = await self.semantic_search(
            query_vector, semantic_settings
        )
        full_text_results: list[ChunkSearchResult] = (
            await self.full_text_search(query_text, full_text_settings)
        )

        semantic_limit = search_settings.limit
        full_text_limit = search_settings.hybrid_settings.full_text_limit
        semantic_weight = search_settings.hybrid_settings.semantic_weight
        full_text_weight = search_settings.hybrid_settings.full_text_weight
        rrf_k = search_settings.hybrid_settings.rrf_k

        combined_results: dict[uuid.UUID, HybridSearchIntermediateResult] = {}

        for rank, result in enumerate(semantic_results, 1):
            combined_results[result.id] = {
                "semantic_rank": rank,
                "full_text_rank": full_text_limit,
                "data": result,
                "rrf_score": 0.0,  # Initialize with 0, will be calculated later
            }

        for rank, result in enumerate(full_text_results, 1):
            if result.id in combined_results:
                combined_results[result.id]["full_text_rank"] = rank
            else:
                combined_results[result.id] = {
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
            + search_settings.limit
        ]

        return [
            ChunkSearchResult(
                id=result["data"].id,
                document_id=result["data"].document_id,
                owner_id=result["data"].owner_id,
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
        params: list[str | int | bytes] = []
        where_clause = self._build_filters(filters, params)

        query = f"""
        DELETE FROM {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
        WHERE {where_clause}
        RETURNING id, document_id, text;
        """

        results = await self.connection_manager.fetch_query(query, params)

        return {
            str(result["id"]): {
                "status": "deleted",
                "id": str(result["id"]),
                "document_id": str(result["document_id"]),
                "text": result["text"],
            }
            for result in results
        }

    async def assign_document_to_collection_vector(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        query = f"""
        UPDATE {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
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
        UPDATE {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
        SET collection_ids = array_remove(collection_ids, $1)
        WHERE document_id = $2;
        """
        await self.connection_manager.execute_query(
            query, (collection_id, document_id)
        )

    async def delete_user_vector(self, owner_id: UUID) -> None:
        query = f"""
        DELETE FROM {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
        WHERE owner_id = $1;
        """
        await self.connection_manager.execute_query(query, (owner_id,))

    async def delete_collection_vector(self, collection_id: UUID) -> None:
        query = f"""
         DELETE FROM {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
         WHERE $1 = ANY(collection_ids)
         RETURNING collection_ids
         """
        results = await self.connection_manager.fetchrow_query(
            query, (collection_id,)
        )
        return None

    async def list_document_chunks(
        self,
        document_id: UUID,
        offset: int,
        limit: int,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        vector_select = ", vec" if include_vectors else ""
        limit_clause = f"LIMIT {limit}" if limit > -1 else ""

        query = f"""
        SELECT id, document_id, owner_id, collection_ids, text, metadata{vector_select}, COUNT(*) OVER() AS total
        FROM {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
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
                    "id": result["id"],
                    "document_id": result["document_id"],
                    "owner_id": result["owner_id"],
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

    async def get_chunk(self, id: UUID) -> dict:
        query = f"""
        SELECT id, document_id, owner_id, collection_ids, text, metadata
        FROM {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
        WHERE id = $1;
        """

        result = await self.connection_manager.fetchrow_query(query, (id,))

        if result:
            return {
                "id": result["id"],
                "document_id": result["document_id"],
                "owner_id": result["owner_id"],
                "collection_ids": result["collection_ids"],
                "text": result["text"],
                "metadata": json.loads(result["metadata"]),
            }
        raise R2RException(
            message=f"Chunk with ID {id} not found", status_code=404
        )

    async def create_index(
        self,
        table_name: Optional[VectorTableName] = None,
        index_measure: IndexMeasure = IndexMeasure.cosine_distance,
        index_method: IndexMethod = IndexMethod.auto,
        index_arguments: Optional[IndexArgsIVFFlat | IndexArgsHNSW] = None,
        index_name: Optional[str] = None,
        index_column: Optional[str] = None,
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

        if table_name == VectorTableName.CHUNKS:
            table_name_str = f"{self.project_name}.{VectorTableName.CHUNKS}"  # TODO - Fix bug in vector table naming convention
            if index_column:
                col_name = index_column
            else:
                col_name = (
                    "vec"
                    if (
                        index_measure != IndexMeasure.hamming_distance
                        and index_measure != IndexMeasure.jaccard_distance
                    )
                    else "vec_binary"
                )
        elif table_name == VectorTableName.ENTITIES_DOCUMENT:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.ENTITIES_DOCUMENT}"
            )
            col_name = "description_embedding"
        elif table_name == VectorTableName.GRAPHS_ENTITIES:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.GRAPHS_ENTITIES}"
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
            or f"ix_{ops}_{index_method}__{col_name}_{time.strftime('%Y%m%d%H%M%S')}"
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
        self,
        offset: int,
        limit: int,
        filters: Optional[dict[str, Any]] = None,
    ) -> dict:
        where_clauses = []
        params: list[Any] = [self.project_name]  # Start with schema name
        param_count = 1

        # Handle filtering
        if filters:
            if "table_name" in filters:
                where_clauses.append(f"i.tablename = ${param_count + 1}")
                params.append(filters["table_name"])
                param_count += 1
            if "index_method" in filters:
                where_clauses.append(f"am.amname = ${param_count + 1}")
                params.append(filters["index_method"])
                param_count += 1
            if "index_name" in filters:
                where_clauses.append(
                    f"LOWER(i.indexname) LIKE LOWER(${param_count + 1})"
                )
                params.append(f"%{filters['index_name']}%")
                param_count += 1

        where_clause = " AND ".join(where_clauses) if where_clauses else ""
        if where_clause:
            where_clause = "AND " + where_clause

        query = f"""
        WITH index_info AS (
            SELECT
                i.indexname as name,
                i.tablename as table_name,
                i.indexdef as definition,
                am.amname as method,
                pg_relation_size(c.oid) as size_in_bytes,
                c.reltuples::bigint as row_estimate,
                COALESCE(psat.idx_scan, 0) as number_of_scans,
                COALESCE(psat.idx_tup_read, 0) as tuples_read,
                COALESCE(psat.idx_tup_fetch, 0) as tuples_fetched,
                COUNT(*) OVER() as total_count
            FROM pg_indexes i
            JOIN pg_class c ON c.relname = i.indexname
            JOIN pg_am am ON c.relam = am.oid
            LEFT JOIN pg_stat_user_indexes psat ON psat.indexrelname = i.indexname
                AND psat.schemaname = i.schemaname
            WHERE i.schemaname = $1
            AND i.indexdef LIKE '%vector%'
            {where_clause}
        )
        SELECT *
        FROM index_info
        ORDER BY name
        LIMIT ${param_count + 1}
        OFFSET ${param_count + 2}
        """

        # Add limit and offset to params
        params.extend([limit, offset])

        results = await self.connection_manager.fetch_query(query, params)

        indices = []
        total_entries = 0

        if results:
            total_entries = results[0]["total_count"]
            for result in results:
                index_info = {
                    "name": result["name"],
                    "table_name": result["table_name"],
                    "definition": result["definition"],
                    "size_in_bytes": result["size_in_bytes"],
                    "row_estimate": result["row_estimate"],
                    "number_of_scans": result["number_of_scans"],
                    "tuples_read": result["tuples_read"],
                    "tuples_fetched": result["tuples_fetched"],
                }
                indices.append(index_info)

        # Calculate pagination info
        total_pages = (total_entries + limit - 1) // limit if limit > 0 else 1
        current_page = (offset // limit) + 1 if limit > 0 else 1

        page_info = {
            "total_entries": total_entries,
            "total_pages": total_pages,
            "current_page": current_page,
            "limit": limit,
            "offset": offset,
            "has_previous": offset > 0,
            "has_next": offset + limit < total_entries,
            "previous_offset": max(0, offset - limit) if offset > 0 else None,
            "next_offset": (
                offset + limit if offset + limit < total_entries else None
            ),
        }

        return {"indices": indices, "page_info": page_info}

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
        if table_name == VectorTableName.CHUNKS:
            table_name_str = f"{self.project_name}.{VectorTableName.CHUNKS}"
            col_name = "vec"
        elif table_name == VectorTableName.ENTITIES_DOCUMENT:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.ENTITIES_DOCUMENT}"
            )
            col_name = "description_embedding"
        elif table_name == VectorTableName.GRAPHS_ENTITIES:
            table_name_str = (
                f"{self.project_name}.{VectorTableName.GRAPHS_ENTITIES}"
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
        offset: int,
        limit: int,
        document_id: UUID,
        id: UUID,
        similarity_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:

        table_name = self._get_table_name(PostgresChunkHandler.TABLE_NAME)
        query = f"""
        WITH target_vector AS (
            SELECT vec FROM {table_name}
            WHERE document_id = $1 AND id = $2
        )
        SELECT t.id, t.text, t.metadata, t.document_id, (t.vec <=> tv.vec) AS similarity
        FROM {table_name} t, target_vector tv
        WHERE (t.vec <=> tv.vec) >= $3
            AND t.document_id = $1
            AND t.id != $2
        ORDER BY similarity ASC
        LIMIT $4
        """
        results = await self.connection_manager.fetch_query(
            query,
            (str(document_id), str(id), similarity_threshold, limit),
        )

        return [
            {
                "id": str(r["id"]),
                "text": r["text"],
                "metadata": json.loads(r["metadata"]),
                "document_id": str(r["document_id"]),
                "similarity": float(r["similarity"]),
            }
            for r in results
        ]

    async def list_chunks(
        self,
        offset: int,
        limit: int,
        filters: Optional[dict[str, Any]] = None,
        include_vectors: bool = False,
    ) -> dict[str, Any]:
        """
        List chunks with pagination support.

        Args:
            offset (int, optional): Number of records to skip. Defaults to 0.
            limit (int, optional): Maximum number of records to return. Defaults to 10.
            filters (dict, optional): Dictionary of filters to apply. Defaults to None.
            include_vectors (bool, optional): Whether to include vector data. Defaults to False.

        Returns:
            dict: Dictionary containing:
                - results: List of chunk records
                - total_entries: Total number of chunks matching the filters
                - page_info: Pagination information
        """
        # Validate sort parameters
        valid_sort_columns = {
            "created_at": "metadata->>'created_at'",
            "updated_at": "metadata->>'updated_at'",
            "chunk_order": "metadata->>'chunk_order'",
            "text": "text",
        }

        # Build the select clause
        vector_select = ", vec" if include_vectors else ""
        select_clause = f"""
            id, document_id, owner_id, collection_ids,
            text, metadata{vector_select}, COUNT(*) OVER() AS total
        """

        # Build the where clause if filters are provided
        where_clause = ""
        params: list[str | int | bytes] = []
        if filters:
            where_clause = self._build_filters(filters, params)
            where_clause = f"WHERE {where_clause}"

        # Construct the final query
        query = f"""
        SELECT {select_clause}
        FROM {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
        {where_clause}
        LIMIT $%s
        OFFSET $%s
        """

        # Add pagination parameters
        params.extend([limit, offset])
        param_indices = list(range(1, len(params) + 1))
        formatted_query = query % tuple(param_indices)

        # Execute the query
        results = await self.connection_manager.fetch_query(
            formatted_query, params
        )

        # Process results
        chunks = []
        total = 0
        if results:
            total = results[0].get("total", 0)
            chunks = [
                {
                    "id": str(result["id"]),
                    "document_id": str(result["document_id"]),
                    "owner_id": str(result["owner_id"]),
                    "collection_ids": result["collection_ids"],
                    "text": result["text"],
                    "metadata": json.loads(result["metadata"]),
                    "vector": (
                        json.loads(result["vec"]) if include_vectors else None
                    ),
                }
                for result in results
            ]

        # Calculate pagination info
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        current_page = (offset // limit) + 1 if limit > 0 else 1

        page_info = {
            "total_entries": total,
            "total_pages": total_pages,
            "current_page": current_page,
            "limit": limit,
            "offset": offset,
            "has_previous": offset > 0,
            "has_next": offset + limit < total,
            "previous_offset": max(0, offset - limit) if offset > 0 else None,
            "next_offset": offset + limit if offset + limit < total else None,
        }

        return {"results": chunks, "page_info": page_info}

    async def search_documents(
        self,
        query_text: str,
        settings: SearchSettings,
    ) -> list[dict[str, Any]]:
        """
        Search for documents based on their metadata fields and/or body text.
        Joins with documents table to get complete document metadata.

        Args:
            query_text (str): The search query text
            settings (SearchSettings): Search settings including search preferences and filters

        Returns:
            list[dict[str, Any]]: List of documents with their search scores and complete metadata
        """
        where_clauses = []
        params: list[str | int | bytes] = [query_text]

        # Build the dynamic metadata field search expression
        metadata_fields_expr = " || ' ' || ".join(
            [
                f"COALESCE(v.metadata->>{psql_quote_literal(key)}, '')"
                for key in settings.metadata_keys  # type: ignore
            ]
        )

        query = f"""
            WITH
            -- Metadata search scores
            metadata_scores AS (
                SELECT DISTINCT ON (v.document_id)
                    v.document_id,
                    d.metadata as doc_metadata,
                    CASE WHEN $1 = '' THEN 0.0
                    ELSE
                        ts_rank_cd(
                            setweight(to_tsvector('english', {metadata_fields_expr}), 'A'),
                            websearch_to_tsquery('english', $1),
                            32
                        )
                    END as metadata_rank
                FROM {self._get_table_name(PostgresChunkHandler.TABLE_NAME)} v
                LEFT JOIN {self._get_table_name('documents')} d ON v.document_id = d.id
                WHERE v.metadata IS NOT NULL
            ),
            -- Body search scores
            body_scores AS (
                SELECT
                    document_id,
                    AVG(
                        ts_rank_cd(
                            setweight(to_tsvector('english', COALESCE(text, '')), 'B'),
                            websearch_to_tsquery('english', $1),
                            32
                        )
                    ) as body_rank
                FROM {self._get_table_name(PostgresChunkHandler.TABLE_NAME)}
                WHERE $1 != ''
                {f"AND to_tsvector('english', text) @@ websearch_to_tsquery('english', $1)" if settings.search_over_body else ""}
                GROUP BY document_id
            ),
            -- Combined scores with document metadata
            combined_scores AS (
                SELECT
                    COALESCE(m.document_id, b.document_id) as document_id,
                    m.doc_metadata as metadata,
                    COALESCE(m.metadata_rank, 0) as debug_metadata_rank,
                    COALESCE(b.body_rank, 0) as debug_body_rank,
                    CASE
                        WHEN {str(settings.search_over_metadata).lower()} AND {str(settings.search_over_body).lower()} THEN
                            COALESCE(m.metadata_rank, 0) * {settings.metadata_weight} + COALESCE(b.body_rank, 0) * {settings.title_weight}
                        WHEN {str(settings.search_over_metadata).lower()} THEN
                            COALESCE(m.metadata_rank, 0)
                        WHEN {str(settings.search_over_body).lower()} THEN
                            COALESCE(b.body_rank, 0)
                        ELSE 0
                    END as rank
                FROM metadata_scores m
                FULL OUTER JOIN body_scores b ON m.document_id = b.document_id
                WHERE (
                    ($1 = '') OR
                    ({str(settings.search_over_metadata).lower()} AND m.metadata_rank > 0) OR
                    ({str(settings.search_over_body).lower()} AND b.body_rank > 0)
                )
        """

        # Add any additional filters
        if settings.filters:
            filter_clause = self._build_filters(settings.filters, params)
            where_clauses.append(filter_clause)

        if where_clauses:
            query += f" AND {' AND '.join(where_clauses)}"

        query += """
            )
            SELECT
                document_id,
                metadata,
                rank as score,
                debug_metadata_rank,
                debug_body_rank
            FROM combined_scores
            WHERE rank > 0
            ORDER BY rank DESC
            OFFSET ${offset_param} LIMIT ${limit_param}
        """.format(
            offset_param=len(params) + 1,
            limit_param=len(params) + 2,
        )

        # Add offset and limit to params
        params.extend([settings.offset, settings.limit])

        # Execute query
        results = await self.connection_manager.fetch_query(query, params)

        # Format results with complete document metadata
        return [
            {
                "document_id": str(r["document_id"]),
                "metadata": (
                    json.loads(r["metadata"])
                    if isinstance(r["metadata"], str)
                    else r["metadata"]
                ),
                "score": float(r["score"]),
                "debug_metadata_rank": float(r["debug_metadata_rank"]),
                "debug_body_rank": float(r["debug_body_rank"]),
            }
            for r in results
        ]

    def _get_index_options(
        self,
        method: IndexMethod,
        index_arguments: Optional[IndexArgsIVFFlat | IndexArgsHNSW],
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
