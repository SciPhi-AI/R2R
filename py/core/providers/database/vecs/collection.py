"""
Defines the 'Collection' class

Importing from the `vecs.collection` directly is not supported.
All public classes, enums, and functions are re-exported by the top level `vecs` module.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Iterable, Optional, Union
from uuid import UUID, uuid4

from flupy import flu
from sqlalchemy import (
    Column,
    Index,
    MetaData,
    Table,
    and_,
    cast,
    delete,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import Float, UserDefinedType

from core.base import VectorSearchResult
from core.base.abstractions import VectorSearchSettings

from .adapter import Adapter, AdapterContext, NoOp, Record
from .exc import (
    ArgError,
    CollectionAlreadyExists,
    CollectionNotFound,
    FilterError,
    MismatchedDimension,
)

if TYPE_CHECKING:
    from vecs.client import Client


class IndexMethod(str, Enum):
    """
    An enum representing the index methods available.

    This class currently only supports the 'ivfflat' method but may
    expand in the future.

    Attributes:
        auto (str): Automatically choose the best available index method.
        ivfflat (str): The ivfflat index method.
        hnsw (str): The hnsw index method.
    """

    auto = "auto"
    ivfflat = "ivfflat"
    hnsw = "hnsw"


class IndexMeasure(str, Enum):
    """
    An enum representing the types of distance measures available for indexing.

    Attributes:
        cosine_distance (str): The cosine distance measure for indexing.
        l2_distance (str): The Euclidean (L2) distance measure for indexing.
        max_inner_product (str): The maximum inner product measure for indexing.
    """

    cosine_distance = "cosine_distance"
    l2_distance = "l2_distance"
    max_inner_product = "max_inner_product"


@dataclass
class IndexArgsIVFFlat:
    """
    A class for arguments that can optionally be supplied to the index creation
    method when building an IVFFlat type index.

    Attributes:
        nlist (int): The number of IVF centroids that the index should use
    """

    n_lists: int


@dataclass
class IndexArgsHNSW:
    """
    A class for arguments that can optionally be supplied to the index creation
    method when building an HNSW type index.

    Ref: https://github.com/pgvector/pgvector#index-options

    Both attributes are Optional in case the user only wants to specify one and
    leave the other as default

    Attributes:
        m (int): Maximum number of connections per node per layer (default: 16)
        ef_construction (int): Size of the dynamic candidate list for
            constructing the graph (default: 64)
    """

    m: Optional[int] = 16
    ef_construction: Optional[int] = 64


INDEX_MEASURE_TO_OPS = {
    # Maps the IndexMeasure enum options to the SQL ops string required by
    # the pgvector `create index` statement
    IndexMeasure.cosine_distance: "vector_cosine_ops",
    IndexMeasure.l2_distance: "vector_l2_ops",
    IndexMeasure.max_inner_product: "vector_ip_ops",
}

INDEX_MEASURE_TO_SQLA_ACC = {
    IndexMeasure.cosine_distance: lambda x: x.cosine_distance,
    IndexMeasure.l2_distance: lambda x: x.l2_distance,
    IndexMeasure.max_inner_product: lambda x: x.max_inner_product,
}


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dim=None):
        super(UserDefinedType, self).__init__()
        self.dim = dim

    def get_col_spec(self, **kw):
        return "VECTOR" if self.dim is None else f"VECTOR({self.dim})"

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return value
            if not isinstance(value, list):
                raise ValueError("Expected a list")
            if self.dim is not None and len(value) != self.dim:
                raise ValueError(
                    f"Expected {self.dim} dimensions, not {len(value)}"
                )
            return "[" + ",".join(str(float(v)) for v in value) + "]"

        return process

    def result_processor(self, dialect, coltype):
        return lambda value: (
            value
            if value is None
            else [float(v) for v in value[1:-1].split(",")]
        )

    class comparator_factory(UserDefinedType.Comparator):
        def l2_distance(self, other):
            return self.op("<->", return_type=Float)(other)

        def max_inner_product(self, other):
            return self.op("<#>", return_type=Float)(other)

        def cosine_distance(self, other):
            return self.op("<=>", return_type=Float)(other)


class Collection:
    """
    The `vecs.Collection` class represents a collection of vectors within a PostgreSQL database with pgvector support.
    It provides methods to manage (create, delete, fetch, upsert), index, and perform similarity searches on these vector collections.

    The collections are stored in separate tables in the database, with each vector associated with an identifier and optional metadata.

    Example usage:

        with vecs.create_client(DB_CONNECTION) as vx:
            collection = vx.create_collection(name="docs", dimension=3)
            collection.upsert([("id1", [1, 1, 1], {"key": "value"})])
            # Further operations on 'collection'

    Public Attributes:
        name: The name of the vector collection.
        dimension: The dimension of vectors in the collection.

    Note: Some methods of this class can raise exceptions from the `vecs.exc` module if errors occur.
    """

    COLUMN_VARS = [
        "extraction_id",
        "document_id",
        "user_id",
        "collection_ids",
    ]

    def __init__(
        self,
        name: str,
        dimension: int,
        client: Client,
        adapter: Optional[Adapter] = None,
    ):
        """
        Initializes a new instance of the `Collection` class.

        During expected use, developers initialize instances of `Collection` using the
        `vecs.Client` with `vecs.Client.create_collection(...)` rather than directly.

        Args:
            name (str): The name of the collection.
            dimension (int): The dimension of the vectors in the collection.
            client (Client): The client to use for interacting with the database.
        """
        from core.providers.database.vecs.adapter import Adapter

        self.client = client
        self.name = name
        self.dimension = dimension
        self.table = _build_table(
            client.project_name, name, client.meta, dimension
        )
        self._index: Optional[str] = None
        self.adapter = adapter or Adapter(steps=[NoOp(dimension=dimension)])

        reported_dimensions = set(
            [
                x
                for x in [
                    dimension,
                    adapter.exported_dimension if adapter else None,
                ]
                if x is not None
            ]
        )

        if len(reported_dimensions) == 0:
            raise ArgError(
                "One of dimension or adapter must provide a dimension"
            )
        elif len(reported_dimensions) > 1:
            raise MismatchedDimension(
                "Mismatch in the reported dimensions of the selected vector collection and embedding model. Correct the selected embedding model or specify a new vector collection by modifying the `R2R_PROJECT_NAME` environment variable."
            )

    def __repr__(self):
        """
        Returns a string representation of the `Collection` instance.

        Returns:
            str: A string representation of the `Collection` instance.
        """
        return (
            f'vecs.Collection(name="{self.name}", dimension={self.dimension})'
        )

    def __len__(self) -> int:
        """
        Returns the number of vectors in the collection.

        Returns:
            int: The number of vectors in the collection.
        """
        with self.client.Session() as sess:
            with sess.begin():
                stmt = select(func.count()).select_from(self.table)
                return sess.execute(stmt).scalar() or 0

    def _create_if_not_exists(self):
        """
        PRIVATE

        Creates a new collection in the database if it doesn't already exist

        Returns:
            Collection: The found or created collection.
        """
        query = text(
            f"""
        select
            relname as table_name,
            atttypmod as embedding_dim
        from
            pg_class pc
            join pg_attribute pa
                on pc.oid = pa.attrelid
        where
            pc.relnamespace = '{self.client.project_name}'::regnamespace
            and pc.relkind = 'r'
            and pa.attname = 'vec'
            and not pc.relname ^@ '_'
            and pc.relname = :name
        """
        ).bindparams(name=self.name)
        with self.client.Session() as sess:
            query_result = sess.execute(query).fetchone()

            if query_result:
                _, collection_dimension = query_result
            else:
                collection_dimension = None

        reported_dimensions = set(
            [
                x
                for x in [self.dimension, collection_dimension]
                if x is not None
            ]
        )
        if len(reported_dimensions) > 1:
            raise MismatchedDimension(
                "Mismatch in the reported dimensions of the selected vector collection and embedding model. Correct the selected embedding model or specify a new vector collection by modifying the `R2R_PROJECT_NAME` environment variable."
            )

        if not collection_dimension:
            self.table.create(self.client.engine)

        return self

    def _create(self):
        """
        PRIVATE

        Creates a new collection in the database. Raises a `vecs.exc.CollectionAlreadyExists`
        exception if a collection with the specified name already exists.

        Returns:
            Collection: The newly created collection.
        """

        collection_exists = self.__class__._does_collection_exist(
            self.client, self.name
        )
        if collection_exists:
            raise CollectionAlreadyExists(
                "Collection with requested name already exists"
            )
        self.table.create(self.client.engine)

        unique_string = str(uuid4()).replace("-", "_")[0:7]
        with self.client.Session() as sess:
            sess.execute(
                text(
                    f"""
                    create index ix_meta_{unique_string}
                      on {self.client.project_name}."{self.table.name}"
                      using gin ( metadata jsonb_path_ops )
                    """
                )
            )

            # Create trigger to update fts column
            sess.execute(
                text(
                    f"""
                CREATE TRIGGER tsvector_update_{unique_string} BEFORE INSERT OR UPDATE
                ON {self.client.project_name}."{self.table.name}" FOR EACH ROW EXECUTE FUNCTION
                tsvector_update_trigger(fts, 'pg_catalog.english', text);
            """
                )
            )
        return self

    def _drop(self):
        """
        PRIVATE

        Deletes the collection from the database. Raises a `vecs.exc.CollectionNotFound`
        exception if no collection with the specified name exists.

        Returns:
            Collection: The deleted collection.
        """
        with self.client.Session() as sess:
            sess.execute(text(f"DROP TABLE IF EXISTS {self.name} CASCADE"))
            sess.commit()

        return self

    def upsert(
        self,
        records: Iterable[Record],
    ) -> None:
        chunk_size = 512

        pipeline = flu(self.adapter(records, AdapterContext("upsert"))).chunk(
            chunk_size
        )

        with self.client.Session() as sess:
            with sess.begin():
                for chunk in pipeline:
                    stmt = postgresql.insert(self.table).values(
                        [
                            {
                                "extraction_id": record[0],
                                "document_id": record[1],
                                "user_id": record[2],
                                "collection_ids": record[3],
                                "vec": record[4],
                                "text": record[5],
                                "metadata": record[6],
                                "fts": func.to_tsvector(record[5]),
                            }
                            for record in chunk
                        ]
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[self.table.c.extraction_id],
                        set_=dict(
                            document_id=stmt.excluded.document_id,
                            user_id=stmt.excluded.user_id,
                            collection_ids=stmt.excluded.collection_ids,
                            vec=stmt.excluded.vec,
                            text=stmt.excluded.text,
                            metadata=stmt.excluded.metadata,
                            fts=stmt.excluded.fts,
                        ),
                    )
                    sess.execute(stmt)
        return None

    def fetch(self, ids: Iterable[UUID]) -> list[Record]:
        """
        Fetches vectors from the collection by their identifiers.

        Args:
            ids (Iterable[UUID]): An iterable of vector identifiers.

        Returns:
            list[Record]: A list of the fetched vectors.

        Raises:
            ArgError: If ids is not an iterable of UUIDs.
        """
        if isinstance(ids, (str, UUID)):
            raise ArgError("ids must be an iterable of UUIDs")

        chunk_size = 12
        records = []
        with self.client.Session() as sess:
            with sess.begin():
                for id_chunk in flu(ids).chunk(chunk_size):
                    stmt = select(self.table).where(
                        self.table.c.extraction_id.in_(id_chunk)
                    )
                    chunk_records = sess.execute(stmt)
                    records.extend(chunk_records)
        return records

    def delete(
        self,
        ids: Optional[Iterable[UUID]] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, dict[str, str]]:
        """
        Deletes vectors from the collection by matching filters or ids.

        Args:
            extraction_ids (Optional[Iterable[UUID]], optional): An iterable of vector fragment identifiers.
            filters (Optional[dict], optional): Filters to apply to the search. Defaults to None.

        Returns:
            dict[str, dict[str, str]]: A dictionary of deleted records, where the key is the extraction_id
            and the value is a dictionary containing 'document_id', 'extraction_id', and 'text'.

        Raises:
            ArgError: If neither ids nor filters are provided, or if both are provided.
        """
        if ids is None and filters is None:
            raise ArgError("Either ids or filters must be provided.")

        if ids is not None and filters is not None:
            raise ArgError("Either ids or filters must be provided, not both.")

        if isinstance(ids, (str, UUID)):
            raise ArgError("ids must be an iterable of UUIDs")

        deleted_records = {}

        with self.client.Session() as sess:
            with sess.begin():
                if ids:
                    for id_chunk in flu(ids).chunk(12):
                        delete_stmt = (
                            delete(self.table)
                            .where(self.table.c.extraction_id.in_(id_chunk))
                            .returning(
                                self.table.c.extraction_id,
                                self.table.c.document_id,
                                self.table.c.text,
                            )
                        )
                        result = sess.execute(delete_stmt)
                        for row in result:
                            extraction_id = str(row[0])
                            deleted_records[extraction_id] = {
                                "extraction_id": extraction_id,
                                "document_id": str(row[1]),
                                "text": row[2],
                            }

                if filters:
                    meta_filter = self.build_filters(filters)
                    delete_stmt = (
                        delete(self.table)
                        .where(meta_filter)
                        .returning(
                            self.table.c.extraction_id,
                            self.table.c.document_id,
                            self.table.c.text,
                        )
                    )
                    result = sess.execute(delete_stmt)
                    for row in result:
                        extraction_id = str(row[0])
                        deleted_records[extraction_id] = {
                            "extraction_id": extraction_id,
                            "document_id": str(row[1]),
                            "text": row[2],
                        }
        return deleted_records

    def __getitem__(self, items):
        """
        Fetches a vector from the collection by its identifier.

        Args:
            items (str): The identifier of the vector.

        Returns:
            Record: The fetched vector.
        """
        if not isinstance(items, str):
            raise ArgError("items must be a string id")

        row = self.fetch([items])

        if row == []:
            raise KeyError("no item found with requested id")
        return row[0]

    def semantic_search(
        self,
        vector: list[float],
        search_settings: VectorSearchSettings,
    ) -> Union[list[Record], list[str]]:
        """
        Executes a similarity search in the collection.

        The return type is dependent on arguments *include_value* and *include_metadata*

        Args:
            data (list[float]): The vector to use as the query.
            search_settings (VectorSearchSettings): The search settings to use.

        Returns:
            Union[list[Record], list[str]]: The result of the similarity search.
        """

        try:
            imeasure_obj = IndexMeasure(search_settings.index_measure)
        except ValueError:
            raise ArgError("Invalid index measure")

        if not self.is_indexed_for_measure(imeasure_obj):
            warnings.warn(
                UserWarning(
                    f"Query does not have a covering index for {imeasure_obj}. See Collection.create_index"
                )
            )

        distance_lambda = INDEX_MEASURE_TO_SQLA_ACC.get(imeasure_obj)
        if distance_lambda is None:
            # unreachable
            raise ArgError("invalid distance_measure")  # pragma: no cover

        distance_clause = distance_lambda(self.table.c.vec)(vector)

        cols = [
            self.table.c.extraction_id,
            self.table.c.document_id,
            self.table.c.user_id,
            self.table.c.collection_ids,
            self.table.c.text,
        ]
        if search_settings.include_values:
            cols.append(distance_clause)

        if search_settings.include_metadatas:
            cols.append(self.table.c.metadata)

        stmt = select(*cols)

        if search_settings.filters:
            stmt = stmt.filter(self.build_filters(search_settings.filters))

        stmt = stmt.order_by(distance_clause)
        stmt = stmt.offset(search_settings.offset)
        stmt = stmt.limit(search_settings.search_limit)

        with self.client.Session() as sess:
            with sess.begin():
                # index ignored if greater than n_lists
                sess.execute(
                    text("set local ivfflat.probes = :probes").bindparams(
                        probes=search_settings.probes
                    )
                )
                if self.client._supports_hnsw():
                    sess.execute(
                        text(
                            "set local hnsw.ef_search = :ef_search"
                        ).bindparams(
                            ef_search=max(
                                search_settings.ef_search,
                                search_settings.search_limit,
                            )
                        )
                    )
                if len(cols) == 1:
                    return [str(x) for x in sess.scalars(stmt).fetchall()]
                result = sess.execute(stmt).fetchall()
                return result or []

    def full_text_search(
        self, query_text: str, search_settings: VectorSearchSettings
    ) -> list[VectorSearchResult]:
        # Create a tsquery from the input query
        ts_query = func.websearch_to_tsquery("english", query_text)

        # Use ts_rank for ranking
        rank_function = func.ts_rank(self.table.c.fts, ts_query, 32).label(
            "rank"
        )

        # Build the main query
        stmt = (
            select(
                self.table.c.extraction_id,
                self.table.c.document_id,
                self.table.c.user_id,
                self.table.c.collection_ids,
                self.table.c.text,
                self.table.c.metadata,
                rank_function,
            )
            .where(self.table.c.fts.op("@@")(ts_query))
            .where(self.build_filters(search_settings.filters))
            .order_by(rank_function.desc())
            .offset(search_settings.offset)
            .limit(search_settings.hybrid_search_settings.full_text_limit)
        )

        # Execute the query
        with self.client.Session() as sess:
            results = sess.execute(stmt).fetchall()

        # Convert the results to VectorSearchResult objects
        return [
            VectorSearchResult(
                extraction_id=str(r.extraction_id),
                document_id=str(r.document_id),
                user_id=str(r.user_id),
                collection_ids=r.collection_ids,
                text=r.text,
                score=float(r.rank),
                metadata=r.metadata,
            )
            for r in results
        ]

    def build_filters(self, filters: dict):
        """
        PUBLIC

        Builds filters for SQL query based on provided dictionary.

        Args:
            filters (dict): The dictionary specifying filter conditions.

        Raises:
            FilterError: If filter conditions are not correctly formatted.

        Returns:
            The filter clause for the SQL query.
        """

        if not isinstance(filters, dict):
            raise FilterError("filters must be a dict")

        def parse_condition(key, value):
            if key in Collection.COLUMN_VARS:
                # Handle column-based filters
                column = getattr(self.table.c, key)
                if isinstance(value, dict):
                    op, clause = next(iter(value.items()))

                    if op == "$eq":
                        return column == clause
                    elif op == "$ne":
                        return column != clause
                    elif op == "$in":
                        return column.in_(clause)
                    elif op == "$nin":
                        return ~column.in_(clause)
                    elif op == "$overlap":
                        return column.overlap(clause)
                    elif op == "$contains":
                        return column.contains(clause)
                    elif op == "$any":
                        if key == "collection_ids":
                            # Use ANY for UUID array comparison
                            return func.array_to_string(column, ",").like(
                                f"%{clause}%"
                            )
                        # New operator for checking if any element in the array matches
                        return column.any(clause)
                    else:
                        raise FilterError(
                            f"Unsupported operator for column {key}: {op}"
                        )
                else:
                    # Handle direct equality
                    if isinstance(value, str):
                        value = UUID(value)
                    return column == value
            else:
                # Handle JSON-based filters
                json_col = self.table.c.metadata
                if key.startswith("metadata."):
                    key = key.split("metadata.")[1]
                if isinstance(value, dict):
                    if len(value) > 1:
                        raise FilterError("only one operator permitted")
                    operator, clause = next(iter(value.items()))
                    if operator not in (
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

                    if operator == "$eq" and not hasattr(clause, "__len__"):
                        contains_value = cast({key: clause}, postgresql.JSONB)
                        return json_col.op("@>")(contains_value)

                    if operator == "$in":
                        if not isinstance(clause, list):
                            raise FilterError(
                                "argument to $in filter must be a list"
                            )
                        for elem in clause:
                            if not isinstance(elem, (int, str, float)):
                                raise FilterError(
                                    "argument to $in filter must be a list of scalars"
                                )
                        contains_value = [
                            cast(elem, postgresql.JSONB) for elem in clause
                        ]
                        return json_col.op("->")(key).in_(contains_value)

                    matches_value = cast(clause, postgresql.JSONB)

                    if operator == "$contains":
                        if not isinstance(clause, (int, str, float)):
                            raise FilterError(
                                "argument to $contains filter must be a scalar"
                            )
                        return and_(
                            json_col.op("->")(key).contains(matches_value),
                            func.jsonb_typeof(json_col.op("->")(key))
                            == "array",
                        )

                    return {
                        "$eq": json_col.op("->")(key) == matches_value,
                        "$ne": json_col.op("->")(key) != matches_value,
                        "$lt": json_col.op("->")(key) < matches_value,
                        "$lte": json_col.op("->")(key) <= matches_value,
                        "$gt": json_col.op("->")(key) > matches_value,
                        "$gte": json_col.op("->")(key) >= matches_value,
                    }[operator]
                else:
                    contains_value = cast({key: value}, postgresql.JSONB)
                    return json_col.op("@>")(contains_value)

        def parse_filter(filter_dict):
            conditions = []
            for key, value in filter_dict.items():
                if key == "$and":
                    conditions.append(and_(*[parse_filter(f) for f in value]))
                elif key == "$or":
                    conditions.append(or_(*[parse_filter(f) for f in value]))
                else:
                    conditions.append(parse_condition(key, value))
            return and_(*conditions)

        return parse_filter(filters)

    @classmethod
    def _list_collections(cls, client: "Client") -> list["Collection"]:
        """
        PRIVATE

        Retrieves all collections from the database.

        Args:
            client (Client): The database client.

        Returns:
            list[Collection]: A list of all existing collections.
        """

        query = text(
            """
        select
            relname as table_name,
            atttypmod as embedding_dim
        from
            pg_class pc
            join pg_attribute pa
                on pc.oid = pa.attrelid
        where
            pc.relnamespace = '{client.project_name}'::regnamespace
            and pc.relkind = 'r'
            and pa.attname = 'vec'
            and not pc.relname ^@ '_'
        """
        )
        xc = []
        with client.Session() as sess:
            for name, dimension in sess.execute(query):
                existing_collection = cls(name, dimension, client)
                xc.append(existing_collection)
        return xc

    @classmethod
    def _does_collection_exist(cls, client: "Client", name: str) -> bool:
        """
        PRIVATE

        Checks if a collection with a given name exists within the database

        Args:
            client (Client): The database client.
            name (str): The name of the collection

        Returns:
            Exists: Whether the collection exists or not
        """

        try:
            client.get_collection(name)
            return True
        except CollectionNotFound:
            return False

    @property
    def index(self) -> Optional[str]:
        """
        PRIVATE

        Note:
            The `index` property is private and expected to undergo refactoring.
            Do not rely on it's output.

        Retrieves the SQL name of the collection's vector index, if it exists.

        Returns:
            Optional[str]: The name of the index, or None if no index exists.
        """

        if self._index is None:
            query = text(
                f"""
            select
                relname as table_name
            from
                pg_class pc
            where
                pc.relnamespace = '{self.client.project_name}'::regnamespace
                and relname ilike 'ix_vector%'
                and pc.relkind = 'i'
            """
            )
            with self.client.Session() as sess:
                ix_name = sess.execute(query).scalar()
            self._index = ix_name
        return self._index

    def is_indexed_for_measure(self, measure: IndexMeasure):
        """
        Checks if the collection is indexed for a specific measure.

        Args:
            measure (IndexMeasure): The measure to check for.

        Returns:
            bool: True if the collection is indexed for the measure, False otherwise.
        """

        index_name = self.index
        if index_name is None:
            return False

        ops = INDEX_MEASURE_TO_OPS.get(measure)
        if ops is None:
            return False

        if ops in index_name:
            return True

        return False

    def close(self):
        """
        Closes the database connection associated with this collection.

        This method should be called when you are done using the collection to release
        the database resources.
        """
        if self.client:
            self.client.close()

    def create_index(
        self,
        measure: IndexMeasure = IndexMeasure.cosine_distance,
        method: IndexMethod = IndexMethod.auto,
        index_arguments: Optional[
            Union[IndexArgsIVFFlat, IndexArgsHNSW]
        ] = None,
        replace=True,
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

        Raises:
            ArgError: If an invalid index method is used, or if *replace* is False and an index already exists.
        """

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
            if self.client._supports_hnsw():
                method = IndexMethod.hnsw
            else:
                method = IndexMethod.ivfflat

        if method == IndexMethod.hnsw and not self.client._supports_hnsw():
            raise ArgError(
                "HNSW Unavailable. Upgrade your pgvector installation to > 0.5.0 to enable HNSW support"
            )

        ops = INDEX_MEASURE_TO_OPS.get(measure)
        if ops is None:
            raise ArgError("Unknown index measure")

        unique_string = str(uuid4()).replace("-", "_")[0:7]

        with self.client.Session() as sess:
            with sess.begin():
                if self.index is not None:
                    if replace:
                        sess.execute(
                            text(
                                f'drop index {self.client.project_name}."{self.index}";'
                            )
                        )
                        self._index = None
                    else:
                        raise ArgError(
                            "replace is set to False but an index exists"
                        )

                if method == IndexMethod.ivfflat:
                    if not index_arguments:
                        n_records: int = sess.execute(func.count(self.table.c.extraction_id)).scalar()  # type: ignore

                        n_lists = (
                            int(max(n_records / 1000, 30))
                            if n_records < 1_000_000
                            else int(math.sqrt(n_records))
                        )
                    else:
                        # The following mypy error is ignored because mypy
                        # complains that `index_arguments` is typed as a union
                        # of IndexArgsIVFFlat and IndexArgsHNSW types,
                        # which both don't necessarily contain the `n_lists`
                        # parameter, however we have validated that the
                        # correct type is being used above.
                        n_lists = index_arguments.n_lists  # type: ignore

                    sess.execute(
                        text(
                            f"""
                            create index ix_{ops}_ivfflat_nl{n_lists}_{unique_string}
                              on {self.client.project_name}."{self.table.name}"
                              using ivfflat (vec {ops}) with (lists={n_lists})
                            """
                        )
                    )

                if method == IndexMethod.hnsw:
                    if not index_arguments:
                        index_arguments = IndexArgsHNSW()

                    # See above for explanation of why the following lines
                    # are ignored
                    m = index_arguments.m  # type: ignore
                    ef_construction = index_arguments.ef_construction  # type: ignore

                    sess.execute(
                        text(
                            f"""
                            create index ix_{ops}_hnsw_m{m}_efc{ef_construction}_{unique_string}
                              on {self.client.project_name}."{self.table.name}"
                              using hnsw (vec {ops}) WITH (m={m}, ef_construction={ef_construction});
                            """
                        )
                    )

        return None


def _build_table(
    project_name: str, name: str, meta: MetaData, dimension: int
) -> Table:
    table = Table(
        name,
        meta,
        Column("extraction_id", postgresql.UUID, primary_key=True),
        Column("document_id", postgresql.UUID, nullable=False),
        Column("user_id", postgresql.UUID, nullable=False),
        Column(
            "collection_ids",
            postgresql.ARRAY(postgresql.UUID),
            server_default="{}",
        ),
        Column("vec", Vector(dimension), nullable=False),
        Column("text", postgresql.TEXT, nullable=True),
        Column(
            "fts",
            postgresql.TSVECTOR,
            nullable=False,
            server_default=text("to_tsvector('english'::regconfig, '')"),
        ),
        Column(
            "metadata",
            postgresql.JSONB,
            server_default=text("'{}'::jsonb"),
            nullable=False,
        ),
        # Create a GIN index for the tsvector column
        Index(f"idx_{name}_fts", "fts", postgresql_using="gin"),
        extend_existing=True,
    )

    return table
