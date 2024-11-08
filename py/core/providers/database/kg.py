import json
import logging
import time
from typing import Any, AsyncGenerator, Optional, Tuple
from uuid import UUID

import asyncpg
from asyncpg.exceptions import PostgresError, UndefinedTableError

from core.base import (
    CommunityReport,
    Entity,
    KGExtraction,
    KGExtractionStatus,
    KGHandler,
    R2RException,
    Relationship
)
from core.base.abstractions import (
    EntityLevel,
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEntityDeduplicationSettings,
    VectorQuantizationType,
)
from core.base.api.models import (
    KGCreationEstimationResponse,
    KGDeduplicationEstimationResponse,
    KGEnrichmentEstimationResponse,
)
from core.base.utils import _decorate_vector_type, llm_cost_per_million_tokens

from .base import PostgresConnectionManager
from .collection import PostgresCollectionHandler

logger = logging.getLogger()


class PostgresKGHandler(KGHandler):
    """Handler for Knowledge Graph operations in PostgreSQL."""

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        collection_handler: PostgresCollectionHandler,
        dimension: int,
        quantization_type: VectorQuantizationType,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the handler with the same signature as the original provider."""
        super().__init__(project_name, connection_manager)
        self.collection_handler = collection_handler
        self.dimension = dimension
        self.quantization_type = quantization_type
        try:
            import networkx as nx

            self.nx = nx
        except ImportError as exc:
            raise ImportError(
                "NetworkX is not installed. Please install it to use this module."
            ) from exc

    def _get_table_name(self, base_name: str) -> str:
        """Get the fully qualified table name."""
        return f"{self.project_name}.{base_name}"

    async def create_tables(self):
        # raw entities table
        # create schema

        vector_column_str = _decorate_vector_type(
            f"({self.dimension})", self.quantization_type
        )

        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("chunk_entity")} (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            extraction_ids UUID[] NOT NULL,
            document_id UUID NOT NULL,
            attributes JSONB
        );
        """
        await self.connection_manager.execute_query(query)

        # raw triples table, also the final table. this will have embeddings.
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("chunk_triple")} (
            id SERIAL PRIMARY KEY,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            weight FLOAT NOT NULL,
            description TEXT NOT NULL,
            embedding {vector_column_str},
            extraction_ids UUID[] NOT NULL,
            document_id UUID NOT NULL,
            attributes JSONB NOT NULL
        );
        """
        await self.connection_manager.execute_query(query)

        # embeddings tables
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("document_entity")} (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            extraction_ids UUID[] NOT NULL,
            description_embedding {vector_column_str} NOT NULL,
            document_id UUID NOT NULL,
            UNIQUE (name, document_id)
            );
        """

        await self.connection_manager.execute_query(query)

        # deduplicated entities table
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("collection_entity")} (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            extraction_ids UUID[] NOT NULL,
            document_ids UUID[] NOT NULL,
            collection_id UUID NOT NULL,
            description_embedding {vector_column_str},
            attributes JSONB,
            UNIQUE (name, collection_id, attributes)
        );"""

        await self.connection_manager.execute_query(query)

        # communities table, result of the Leiden algorithm
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("community_info")} (
            id SERIAL PRIMARY KEY,
            node TEXT NOT NULL,
            cluster INT NOT NULL,
            parent_cluster INT,
            level INT NOT NULL,
            is_final_cluster BOOLEAN NOT NULL,
            triple_ids INT[] NOT NULL,
            collection_id UUID NOT NULL
        );"""

        await self.connection_manager.execute_query(query)

        # communities_report table
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("community_report")} (
            id SERIAL PRIMARY KEY,
            community_number INT NOT NULL,
            collection_id UUID NOT NULL,
            level INT NOT NULL,
            name TEXT NOT NULL,
            summary TEXT NOT NULL,
            findings TEXT[] NOT NULL,
            rating FLOAT NOT NULL,
            rating_explanation TEXT NOT NULL,
            embedding {vector_column_str} NOT NULL,
            attributes JSONB,
            UNIQUE (community_number, level, collection_id)
        );"""

        await self.connection_manager.execute_query(query)

    async def _add_objects(
        self,
        objects: list[Any],
        table_name: str,
        conflict_columns: list[str] = [],
    ) -> asyncpg.Record:
        """
        Upsert objects into the specified table.
        """
        # Get non-null attributes from the first object
        non_null_attrs = {k: v for k, v in objects[0].items() if v is not None}
        columns = ", ".join(non_null_attrs.keys())

        placeholders = ", ".join(f"${i+1}" for i in range(len(non_null_attrs)))

        if conflict_columns:
            conflict_columns_str = ", ".join(conflict_columns)
            replace_columns_str = ", ".join(
                f"{column} = EXCLUDED.{column}" for column in non_null_attrs
            )
            on_conflict_query = f"ON CONFLICT ({conflict_columns_str}) DO UPDATE SET {replace_columns_str}"
        else:
            on_conflict_query = ""

        QUERY = f"""
            INSERT INTO {self._get_table_name(table_name)} ({columns})
            VALUES ({placeholders})
            {on_conflict_query}
        """

        # Filter out null values for each object
        params = [
            tuple(
                (json.dumps(v) if isinstance(v, dict) else v)
                for v in obj.values()
                if v is not None
            )
            for obj in objects
        ]

        return await self.connection_manager.execute_many(QUERY, params)  # type: ignore

    async def add_entities(
        self,
        entities: list[Entity],
        table_name: str,
        conflict_columns: list[str] = [],
    ) -> asyncpg.Record:
        """
        Upsert entities into the entities_raw table. These are raw entities extracted from the document.

        Args:
            entities: list[Entity]: list of entities to upsert
            collection_name: str: name of the collection

        Returns:
            result: asyncpg.Record: result of the upsert operation
        """
        cleaned_entities = []
        for entity in entities:
            entity_dict = entity.to_dict()
            entity_dict["extraction_ids"] = (
                entity_dict["extraction_ids"]
                if entity_dict.get("extraction_ids")
                else []
            )
            entity_dict["description_embedding"] = (
                str(entity_dict["description_embedding"])
                if entity_dict.get("description_embedding")
                else None
            )
            cleaned_entities.append(entity_dict)

        return await self._add_objects(
            cleaned_entities, table_name, conflict_columns
        )

    async def get_graph_status(self, collection_id: UUID) -> dict:
        # check document_info table for the documents in the collection and return the status of each document
        kg_extraction_statuses = await self.connection_manager.fetch_query(
            f"SELECT document_id, kg_extraction_status FROM {self._get_table_name('document_info')} WHERE collection_id = $1",
            [collection_id],
        )

        document_ids = [doc_id["document_id"] for doc_id in kg_extraction_statuses]

        kg_enrichment_statuses = await self.connection_manager.fetch_query(
            f"SELECT enrichment_status FROM {self._get_table_name(PostgresCollectionHandler.TABLE_NAME)} WHERE id = $1",
            [collection_id],
        )

        # entity and relationship counts
        chunk_entity_count = await self.connection_manager.fetch_query(
            f"SELECT COUNT(*) FROM {self._get_table_name('chunk_entity')} WHERE document_id = ANY($1)",
            [document_ids],
        )

        chunk_triple_count = await self.connection_manager.fetch_query(
            f"SELECT COUNT(*) FROM {self._get_table_name('chunk_triple')} WHERE document_id = ANY($1)",
            [document_ids],
        )

        document_entity_count = await self.connection_manager.fetch_query(
            f"SELECT COUNT(*) FROM {self._get_table_name('document_entity')} WHERE document_id = ANY($1)",
            [document_ids],
        )

        collection_entity_count = await self.connection_manager.fetch_query(
            f"SELECT COUNT(*) FROM {self._get_table_name('collection_entity')} WHERE collection_id = $1",
            [collection_id],
        )

        community_count = await self.connection_manager.fetch_query(
            f"SELECT COUNT(*) FROM {self._get_table_name('community_report')} WHERE collection_id = $1",
            [collection_id],
        )

        return {
            "kg_extraction_statuses": kg_extraction_statuses,
            "kg_enrichment_status": kg_enrichment_statuses[0]["enrichment_status"],
            "chunk_entity_count": chunk_entity_count[0]["count"],
            "chunk_triple_count": chunk_triple_count[0]["count"],
            "document_entity_count": document_entity_count[0]["count"],
            "collection_entity_count": collection_entity_count[0]["count"],
            "community_count": community_count[0]["count"],
        }


    async def add_triples(
        self,
        triples: list[Relationship],
        table_name: str = "chunk_triple",
    ) -> None:
        """
        Upsert triples into the chunk_triple table. These are raw triples extracted from the document.

        Args:
            triples: list[Relationship]: list of triples to upsert
            table_name: str: name of the table to upsert into

        Returns:
            result: asyncpg.Record: result of the upsert operation
        """
        return await self._add_objects(
            [ele.to_dict() for ele in triples], table_name
        )

    async def add_kg_extractions(
        self,
        kg_extractions: list[KGExtraction],
        table_prefix: str = "chunk_",
    ) -> Tuple[int, int]:
        """
        Upsert entities and triples into the database. These are raw entities and triples extracted from the document fragments.

        Args:
            kg_extractions: list[KGExtraction]: list of KG extractions to upsert
            table_prefix: str: prefix to add to the table names

        Returns:
            total_entities: int: total number of entities upserted
            total_relationships: int: total number of relationships upserted
        """

        total_entities, total_relationships = 0, 0

        for extraction in kg_extractions:

            total_entities, total_relationships = (
                total_entities + len(extraction.entities),
                total_relationships + len(extraction.triples),
            )

            if extraction.entities:
                if not extraction.entities[0].extraction_ids:
                    for i in range(len(extraction.entities)):
                        extraction.entities[i].extraction_ids = (
                            extraction.extraction_ids
                        )
                        extraction.entities[i].document_id = (
                            extraction.document_id
                        )

                await self.add_entities(
                    extraction.entities, table_name=f"{table_prefix}entity"
                )

            if extraction.triples:
                if not extraction.triples[0].extraction_ids:
                    for i in range(len(extraction.triples)):
                        extraction.triples[i].extraction_ids = (
                            extraction.extraction_ids
                        )
                    extraction.triples[i].document_id = extraction.document_id

                await self.add_triples(
                    extraction.triples, table_name=f"{table_prefix}triple"
                )

        return (total_entities, total_relationships)

    async def get_entity_map(
        self, offset: int, limit: int, document_id: UUID
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:

        QUERY1 = f"""
            WITH entities_list AS (
                SELECT DISTINCT name
                FROM {self._get_table_name("chunk_entity")}
                WHERE document_id = $1
                ORDER BY name ASC
                LIMIT {limit} OFFSET {offset}
            )
            SELECT e.name, e.description, e.category,
                   (SELECT array_agg(DISTINCT x) FROM unnest(e.extraction_ids) x) AS extraction_ids,
                   e.document_id
            FROM {self._get_table_name("chunk_entity")} e
            JOIN entities_list el ON e.name = el.name
            GROUP BY e.name, e.description, e.category, e.extraction_ids, e.document_id
            ORDER BY e.name;"""

        entities_list = await self.connection_manager.fetch_query(
            QUERY1, [document_id]
        )
        entities_list = [
            Entity(
                name=entity["name"],
                description=entity["description"],
                category=entity["category"],
                extraction_ids=entity["extraction_ids"],
                document_id=entity["document_id"],
            )
            for entity in entities_list
        ]

        QUERY2 = f"""
            WITH entities_list AS (

                SELECT DISTINCT name
                FROM {self._get_table_name("chunk_entity")}
                WHERE document_id = $1
                ORDER BY name ASC
                LIMIT {limit} OFFSET {offset}
            )

            SELECT DISTINCT t.subject, t.predicate, t.object, t.weight, t.description,
                   (SELECT array_agg(DISTINCT x) FROM unnest(t.extraction_ids) x) AS extraction_ids, t.document_id
            FROM {self._get_table_name("chunk_triple")} t
            JOIN entities_list el ON t.subject = el.name
            ORDER BY t.subject, t.predicate, t.object;
        """

        triples_list = await self.connection_manager.fetch_query(
            QUERY2, [document_id]
        )
        triples_list = [
            Relationship(
                subject=triple["subject"],
                predicate=triple["predicate"],
                object=triple["object"],
                weight=triple["weight"],
                description=triple["description"],
                extraction_ids=triple["extraction_ids"],
                document_id=triple["document_id"],
            )
            for triple in triples_list
        ]

        entity_map: dict[str, dict[str, list[Any]]] = {}
        for entity in entities_list:
            if entity.name not in entity_map:
                entity_map[entity.name] = {"entities": [], "triples": []}
            entity_map[entity.name]["entities"].append(entity)

        for triple in triples_list:
            if triple.subject in entity_map:
                entity_map[triple.subject]["triples"].append(triple)
            if triple.object in entity_map:
                entity_map[triple.object]["triples"].append(triple)

        return entity_map

    async def upsert_embeddings(
        self,
        data: list[Tuple[Any]],
        table_name: str,
    ) -> None:
        QUERY = f"""
            INSERT INTO {self._get_table_name(table_name)} (name, description, description_embedding, extraction_ids, document_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (name, document_id) DO UPDATE SET
                description = EXCLUDED.description,
                description_embedding = EXCLUDED.description_embedding,
                extraction_ids = EXCLUDED.extraction_ids,
                document_id = EXCLUDED.document_id
            """
        return await self.connection_manager.execute_many(QUERY, data)

    async def upsert_entities(self, entities: list[Entity]) -> None:
        QUERY = """
            INSERT INTO $1.$2 (category, name, description, description_embedding, extraction_ids, document_id, attributes)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """

        table_name = self._get_table_name("entities")
        query = QUERY.format(table_name)
        await self.connection_manager.execute_query(query, entities)

    async def vector_query(  # type: ignore
        self, query: str, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:

        query_embedding = kwargs.get("query_embedding", None)
        search_type = kwargs.get("search_type", "__Entity__")
        embedding_type = kwargs.get("embedding_type", "description_embedding")
        property_names = kwargs.get("property_names", ["name", "description"])
        filters = kwargs.get("filters", {})
        entities_level = kwargs.get("entities_level", EntityLevel.DOCUMENT)
        limit = kwargs.get("limit", 10)

        table_name = ""
        if search_type == "__Entity__":
            table_name = (
                "collection_entity"
                if entities_level == EntityLevel.COLLECTION
                else "document_entity"
            )
        elif search_type == "__Relationship__":
            table_name = "chunk_triple"
        elif search_type == "__Community__":
            table_name = "community_report"
        else:
            raise ValueError(f"Invalid search type: {search_type}")

        property_names_str = ", ".join(property_names)

        collection_ids_dict = filters.get("collection_ids", {})
        filter_query = ""
        if collection_ids_dict:
            filter_query = "WHERE collection_id = ANY($3)"
            filter_ids = collection_ids_dict["$overlap"]

            if (
                search_type == "__Community__"
                or table_name == "collection_entity"
            ):
                logger.info(f"Searching in collection ids: {filter_ids}")

            elif search_type in ["__Entity__", "__Relationship__"]:
                filter_query = "WHERE document_id = ANY($3)"
                # TODO - This seems like a hack, we will need a better way to filter by collection ids for entities and relationships
                query = f"""
                    SELECT distinct document_id FROM {self._get_table_name('document_info')} WHERE $1 = ANY(collection_ids)
                """
                filter_ids = [
                    doc_id["document_id"]
                    for doc_id in await self.connection_manager.fetch_query(
                        query, filter_ids
                    )
                ]
                logger.info(f"Searching in document ids: {filter_ids}")

        QUERY = f"""
            SELECT {property_names_str} FROM {self._get_table_name(table_name)} {filter_query} ORDER BY {embedding_type} <=> $1 LIMIT $2;
        """

        if filter_query != "":
            results = await self.connection_manager.fetch_query(
                QUERY, (str(query_embedding), limit, filter_ids)
            )
        else:
            results = await self.connection_manager.fetch_query(
                QUERY, (str(query_embedding), limit)
            )

        for result in results:
            yield {
                property_name: result[property_name]
                for property_name in property_names
            }

    async def get_all_triples(self, collection_id: UUID) -> list[Relationship]:

        # getting all documents for a collection
        QUERY = f"""
            select distinct document_id from {self._get_table_name("document_info")} where $1 = ANY(collection_ids)
        """
        document_ids = await self.connection_manager.fetch_query(
            QUERY, [collection_id]
        )
        document_ids = [doc_id["document_id"] for doc_id in document_ids]

        QUERY = f"""
            SELECT id, subject, predicate, weight, object FROM {self._get_table_name("chunk_triple")} WHERE document_id = ANY($1)
        """
        triples = await self.connection_manager.fetch_query(
            QUERY, [document_ids]
        )
        return [Relationship(**triple) for triple in triples]

    async def add_communities(self, communities: list[Any]) -> None:
        QUERY = f"""
            INSERT INTO {self._get_table_name("community_info")} (node, cluster, parent_cluster, level, is_final_cluster, triple_ids, collection_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
        await self.connection_manager.execute_many(QUERY, communities)

    async def get_communities(
        self,
        collection_id: Optional[UUID] = None,
        levels: Optional[list[int]] = None,
        community_numbers: Optional[list[int]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = -1,
    ) -> dict:
        conditions = []
        params: list = [collection_id]
        param_index = 2

        if levels is not None:
            conditions.append(f"level = ANY(${param_index})")
            params.append(levels)
            param_index += 1

        if community_numbers is not None:
            conditions.append(f"community_number = ANY(${param_index})")
            params.append(community_numbers)
            param_index += 1

        pagination_params = []
        if offset:
            pagination_params.append(f"OFFSET ${param_index}")
            params.append(offset)
            param_index += 1

        if limit != -1:
            pagination_params.append(f"LIMIT ${param_index}")
            params.append(limit)
            param_index += 1

        pagination_clause = " ".join(pagination_params)

        query = f"""
            SELECT id, community_number, collection_id, level, name, summary, findings, rating, rating_explanation, COUNT(*) OVER() AS total_entries
            FROM {self._get_table_name('community_report')}
            WHERE collection_id = $1
            {" AND " + " AND ".join(conditions) if conditions else ""}
            ORDER BY community_number
            {pagination_clause}
        """

        results = await self.connection_manager.fetch_query(query, params)
        total_entries = results[0]["total_entries"] if results else 0
        communities = [CommunityReport(**community) for community in results]

        return {
            "communities": communities,
            "total_entries": total_entries,
        }

    async def add_community_report(
        self, community_report: CommunityReport
    ) -> None:

        # TODO: Fix in the short term.
        # we need to do this because postgres insert needs to be a string
        community_report.embedding = str(community_report.embedding)  # type: ignore[assignment]

        non_null_attrs = {
            k: v for k, v in community_report.__dict__.items() if v is not None
        }
        columns = ", ".join(non_null_attrs.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(non_null_attrs)))

        conflict_columns = ", ".join(
            [f"{k} = EXCLUDED.{k}" for k in non_null_attrs]
        )

        QUERY = f"""
            INSERT INTO {self._get_table_name("community_report")} ({columns})
            VALUES ({placeholders})
            ON CONFLICT (community_number, level, collection_id) DO UPDATE SET
                {conflict_columns}
            """

        await self.connection_manager.execute_many(
            QUERY, [tuple(non_null_attrs.values())]
        )

    async def perform_graph_clustering(
        self,
        collection_id: UUID,
        leiden_params: dict[str, Any],
    ) -> int:
        """
        Leiden clustering algorithm to cluster the knowledge graph triples into communities.

        Available parameters and defaults:
            max_cluster_size: int = 1000,
            starting_communities: Optional[dict[str, int]] = None,
            extra_forced_iterations: int = 0,
            resolution: Union[int, float] = 1.0,
            randomness: Union[int, float] = 0.001,
            use_modularity: bool = True,
            random_seed: Optional[int] = None,
            weight_attribute: str = "weight",
            is_weighted: Optional[bool] = None,
            weight_default: Union[int, float] = 1.0,
            check_directed: bool = True,
        """

        start_time = time.time()
        triples = await self.get_all_triples(collection_id)

        logger.info(f"Clustering with settings: {leiden_params}")

        G = self.nx.Graph()
        for triple in triples:
            G.add_edge(
                triple.subject,
                triple.object,
                weight=triple.weight,
                id=triple.id,
            )

        logger.info("Computing Leiden communities started.")

        hierarchical_communities = await self._compute_leiden_communities(
            G, leiden_params
        )

        logger.info(
            f"Computing Leiden communities completed, time {time.time() - start_time:.2f} seconds."
        )

        # caching the triple ids
        triple_ids_cache = dict[str, list[int]]()
        for triple in triples:
            if (
                triple.subject not in triple_ids_cache
                and triple.subject is not None
            ):
                triple_ids_cache[triple.subject] = []
            if (
                triple.object not in triple_ids_cache
                and triple.object is not None
            ):
                triple_ids_cache[triple.object] = []
            if triple.subject is not None and triple.id is not None:
                triple_ids_cache[triple.subject].append(triple.id)
            if triple.object is not None and triple.id is not None:
                triple_ids_cache[triple.object].append(triple.id)

        def triple_ids(node: str) -> list[int]:
            return triple_ids_cache.get(node, [])

        logger.info(
            f"Cached {len(triple_ids_cache)} triple ids, time {time.time() - start_time:.2f} seconds."
        )

        # upsert the communities into the database.
        inputs = [
            (
                str(item.node),
                item.cluster,
                item.parent_cluster,
                item.level,
                item.is_final_cluster,
                triple_ids(item.node),
                collection_id,
            )
            for item in hierarchical_communities
        ]

        await self.add_communities(inputs)

        num_communities = len(
            {item.cluster for item in hierarchical_communities}
        )

        logger.info(
            f"Generated {num_communities} communities, time {time.time() - start_time:.2f} seconds."
        )

        return num_communities

    async def _compute_leiden_communities(
        self,
        graph: Any,
        leiden_params: dict[str, Any],
    ) -> Any:
        """Compute Leiden communities."""
        try:
            from graspologic.partition import hierarchical_leiden

            if "random_seed" not in leiden_params:
                leiden_params["random_seed"] = (
                    7272  # add seed to control randomness
                )

            start_time = time.time()
            logger.info(
                f"Running Leiden clustering with params: {leiden_params}"
            )

            community_mapping = hierarchical_leiden(graph, **leiden_params)

            logger.info(
                f"Leiden clustering completed in {time.time() - start_time:.2f} seconds."
            )
            return community_mapping

        except ImportError as e:
            raise ImportError("Please install the graspologic package.") from e

    async def get_community_details(
        self, community_number: int, collection_id: UUID
    ) -> Tuple[int, list[Entity], list[Relationship]]:

        QUERY = f"""
            SELECT level FROM {self._get_table_name("community_info")} WHERE cluster = $1 AND collection_id = $2
            LIMIT 1
        """
        level = (
            await self.connection_manager.fetch_query(
                QUERY, [community_number, collection_id]
            )
        )[0]["level"]

        # selecting table name based on entity level
        # check if there are any entities in the community that are not in the entity_embedding table
        query = f"""
            SELECT COUNT(*) FROM {self._get_table_name("collection_entity")} WHERE collection_id = $1
        """
        entity_count = (
            await self.connection_manager.fetch_query(query, [collection_id])
        )[0]["count"]
        table_name = (
            "collection_entity" if entity_count > 0 else "document_entity"
        )

        QUERY = f"""
            WITH node_triple_ids AS (
                SELECT node, triple_ids
                FROM {self._get_table_name("community_info")}
                WHERE cluster = $1 AND collection_id = $2
            )
            SELECT DISTINCT
                e.id AS id,
                e.name AS name,
                e.description AS description
            FROM node_triple_ids nti
            JOIN {self._get_table_name(table_name)} e ON e.name = nti.node;
        """
        entities = await self.connection_manager.fetch_query(
            QUERY, [community_number, collection_id]
        )
        entities = [Entity(**entity) for entity in entities]

        QUERY = f"""
            WITH node_triple_ids AS (
                SELECT node, triple_ids
                FROM {self._get_table_name("community_info")}
                WHERE cluster = $1 and collection_id = $2
            )
            SELECT DISTINCT
                t.id, t.subject, t.predicate, t.object, t.weight, t.description
            FROM node_triple_ids nti
            JOIN {self._get_table_name("chunk_triple")} t ON t.id = ANY(nti.triple_ids);
        """
        triples = await self.connection_manager.fetch_query(
            QUERY, [community_number, collection_id]
        )
        triples = [Relationship(**triple) for triple in triples]

        return level, entities, triples

    # async def client(self):
    #     return None

    ############################################################
    ########## Entity CRUD Operations ##########################
    ############################################################

    async def create_entity(
        self, collection_id: UUID, entity: Entity
    ) -> None:

        table_name = entity.level.value + "_entity"
        entity.level = None

        # check if the entity already exists
        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name(table_name)} WHERE id = $1 AND collection_id = $2
        """
        count = (
            await self.connection_manager.fetch_query(QUERY, [entity.id, collection_id])
        )[0]["count"]

        if count > 0:
            raise R2RException("Entity already exists", 400)

        await self._add_objects([entity], table_name)

    async def update_entity(
        self, collection_id: UUID, entity: Entity
    ) -> None:
        table_name = entity.level.value + "_entity"

        # check if the entity already exists
        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name(table_name)} WHERE id = $1 AND collection_id = $2
        """
        count = (
            await self.connection_manager.fetch_query(QUERY, [entity.id, collection_id])
        )[0]["count"]

        if count == 0:
            raise R2RException("Entity does not exist", 404)

        await self._add_objects([entity], table_name)

    async def delete_entity(
        self, collection_id: UUID, entity: Entity
    ) -> None:

        table_name = entity.level.value + "_entity"
        QUERY = f"""
            DELETE FROM {self._get_table_name(table_name)} WHERE id = $1 AND collection_id = $2
        """
        await self.connection_manager.execute_query(QUERY, [entity.id, collection_id])

    ############################################################
    ########## Relationship CRUD Operations ####################
    ############################################################

    async def create_relationship(
        self, collection_id: UUID, relationship: Relationship
    ) -> None:
        
        # check if the relationship already exists
        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("chunk_triple")} WHERE subject = $1 AND predicate = $2 AND object = $3 AND collection_id = $4
        """
        count = (
            await self.connection_manager.fetch_query(QUERY, [relationship.subject, relationship.predicate, relationship.object, collection_id])
        )[0]["count"]

        if count > 0:
            raise R2RException("Relationship already exists", 400)

        await self._add_objects([relationship], "chunk_triple")

    async def update_relationship(
        self, relationship_id: UUID, relationship: Relationship
    ) -> None:
        
        # check if relationship_id exists
        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("chunk_triple")} WHERE id = $1
        """
        count = (
            await self.connection_manager.fetch_query(QUERY, [relationship.id])
        )[0]["count"]

        if count == 0:
            raise R2RException("Relationship does not exist", 404)

        await self._add_objects([relationship], "chunk_triple")

    async def delete_relationship(
        self, relationship_id: UUID
    ) -> None:
        QUERY = f"""
            DELETE FROM {self._get_table_name("chunk_triple")} WHERE id = $1
        """
        await self.connection_manager.execute_query(QUERY, [relationship_id])

    ############################################################
    ########## Community CRUD Operations #######################
    ############################################################

    async def get_community_reports(
        self, collection_id: UUID
    ) -> list[CommunityReport]:
        QUERY = f"""
            SELECT *c FROM {self._get_table_name("community_report")} WHERE collection_id = $1
        """
        return await self.connection_manager.fetch_query(
            QUERY, [collection_id]
        )

    async def check_community_reports_exist(
        self, collection_id: UUID, offset: int, limit: int
    ) -> list[int]:
        QUERY = f"""
            SELECT distinct community_number FROM {self._get_table_name("community_report")} WHERE collection_id = $1 AND community_number >= $2 AND community_number < $3
        """
        community_numbers = await self.connection_manager.fetch_query(
            QUERY, [collection_id, offset, offset + limit]
        )
        return [item["community_number"] for item in community_numbers]

    async def delete_graph_for_collection(
        self, collection_id: UUID, cascade: bool = False
    ) -> None:

        # don't delete if status is PROCESSING.
        QUERY = f"""
            SELECT kg_enrichment_status FROM {self._get_table_name("collections")} WHERE collection_id = $1
        """
        status = (
            await self.connection_manager.fetch_query(QUERY, [collection_id])
        )[0]["kg_enrichment_status"]
        if status == KGExtractionStatus.PROCESSING.value:
            return

        # remove all triples for these documents.
        DELETE_QUERIES = [
            f"DELETE FROM {self._get_table_name('community_info')} WHERE collection_id = $1;",
            f"DELETE FROM {self._get_table_name('community_report')} WHERE collection_id = $1;",
        ]

        document_ids_response = (
            await self.collection_handler.documents_in_collection(
                collection_id
            )
        )

        # This type ignore is due to insufficient typing of the documents_in_collection method
        document_ids = [doc.id for doc in document_ids_response["results"]]  # type: ignore

        # TODO: make these queries more efficient. Pass the document_ids as params.
        if cascade:
            DELETE_QUERIES += [
                f"DELETE FROM {self._get_table_name('chunk_entity')} WHERE document_id = ANY($1::uuid[]);",
                f"DELETE FROM {self._get_table_name('chunk_triple')} WHERE document_id = ANY($1::uuid[]);",
                f"DELETE FROM {self._get_table_name('document_entity')} WHERE document_id = ANY($1::uuid[]);",
                f"DELETE FROM {self._get_table_name('collection_entity')} WHERE collection_id = $1;",
            ]

            # setting the kg_creation_status to PENDING for this collection.
            QUERY = f"""
                UPDATE {self._get_table_name("document_info")} SET kg_extraction_status = $1 WHERE $2::uuid = ANY(collection_ids)
            """
            await self.connection_manager.execute_query(
                QUERY, [KGExtractionStatus.PENDING, collection_id]
            )

        for query in DELETE_QUERIES:
            if "community" in query or "collection_entity" in query:
                await self.connection_manager.execute_query(
                    query, [collection_id]
                )
            else:
                await self.connection_manager.execute_query(
                    query, [document_ids]
                )

        # set status to PENDING for this collection.
        QUERY = f"""
            UPDATE {self._get_table_name("collections")} SET kg_enrichment_status = $1 WHERE collection_id = $2
        """
        await self.connection_manager.execute_query(
            QUERY, [KGExtractionStatus.PENDING, collection_id]
        )

    async def delete_node_via_document_id(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        # don't delete if status is PROCESSING.
        QUERY = f"""
            SELECT kg_enrichment_status FROM {self._get_table_name("collections")} WHERE collection_id = $1
        """
        status = (
            await self.connection_manager.fetch_query(QUERY, [collection_id])
        )[0]["kg_enrichment_status"]
        if status == KGExtractionStatus.PROCESSING.value:
            return

        # Execute separate DELETE queries
        delete_queries = [
            f"DELETE FROM {self._get_table_name('chunk_entity')} WHERE document_id = $1",
            f"DELETE FROM {self._get_table_name('chunk_triple')} WHERE document_id = $1",
            f"DELETE FROM {self._get_table_name('document_entity')} WHERE document_id = $1",
        ]

        for query in delete_queries:
            await self.connection_manager.execute_query(query, [document_id])

        # Check if this is the last document in the collection
        documents = await self.collection_handler.documents_in_collection(
            collection_id
        )
        count = documents["total_entries"]

        if count == 0:
            # If it's the last document, delete collection-related data
            collection_queries = [
                f"DELETE FROM {self._get_table_name('community_info')} WHERE collection_id = $1",
                f"DELETE FROM {self._get_table_name('community_report')} WHERE collection_id = $1",
            ]
            for query in collection_queries:
                await self.connection_manager.execute_query(
                    query, [collection_id]
                )  # Ensure collection_id is in a list

            # set status to PENDING for this collection.
            QUERY = f"""
                UPDATE {self._get_table_name("collections")} SET kg_enrichment_status = $1 WHERE collection_id = $2
            """
            await self.connection_manager.execute_query(
                QUERY, [KGExtractionStatus.PENDING, collection_id]
            )
            return None
        return None

    def _get_str_estimation_output(self, x: tuple[Any, Any]) -> str:
        if isinstance(x[0], int) and isinstance(x[1], int):
            return " - ".join(map(str, x))
        else:
            return " - ".join(f"{round(a, 2)}" for a in x)

    async def get_existing_entity_extraction_ids(
        self, document_id: UUID
    ) -> list[str]:
        QUERY = f"""
            SELECT DISTINCT unnest(extraction_ids) AS chunk_id FROM {self._get_table_name("chunk_entity")} WHERE document_id = $1
        """
        return [
            item["chunk_id"]
            for item in await self.connection_manager.fetch_query(
                QUERY, [document_id]
            )
        ]

    async def get_creation_estimate(
        self, collection_id: UUID, kg_creation_settings: KGCreationSettings
    ) -> KGCreationEstimationResponse:

        # todo: harmonize the document_id and id fields: postgres table contains document_id, but other places use id.
        document_ids = [
            doc.id
            for doc in (
                await self.collection_handler.documents_in_collection(collection_id)  # type: ignore
            )["results"]
        ]

        query = f"""
            SELECT document_id, COUNT(*) as chunk_count
            FROM {self._get_table_name("vectors")}
            WHERE document_id = ANY($1)
            GROUP BY document_id
        """

        chunk_counts = await self.connection_manager.fetch_query(
            query, [document_ids]
        )

        total_chunks = (
            sum(doc["chunk_count"] for doc in chunk_counts)
            // kg_creation_settings.extraction_merge_count
        )  # 4 chunks per llm
        estimated_entities = (
            total_chunks * 10,
            total_chunks * 20,
        )  # 25 entities per 4 chunks
        estimated_triples = (
            int(estimated_entities[0] * 1.25),
            int(estimated_entities[1] * 1.5),
        )  # Assuming 1.25 triples per entity on average

        estimated_llm_calls = (
            total_chunks * 2 + estimated_entities[0],
            total_chunks * 2 + estimated_entities[1],
        )

        total_in_out_tokens = (
            2000 * estimated_llm_calls[0] // 1000000,
            2000 * estimated_llm_calls[1] // 1000000,
        )  # in millions

        estimated_cost = (
            total_in_out_tokens[0]
            * llm_cost_per_million_tokens(
                kg_creation_settings.generation_config.model
            ),
            total_in_out_tokens[1]
            * llm_cost_per_million_tokens(
                kg_creation_settings.generation_config.model
            ),
        )

        total_time_in_minutes = (
            total_in_out_tokens[0] * 10 / 60,
            total_in_out_tokens[1] * 10 / 60,
        )  # 10 minutes per million tokens

        return KGCreationEstimationResponse(
            message='Ran Graph Creation Estimate (not the actual run). Note that these are estimated ranges, actual values may vary. To run the KG creation process, run `create-graph` with `--run` in the cli, or `run_type="run"` in the client.',
            document_count=len(document_ids),
            number_of_jobs_created=len(document_ids) + 1,
            total_chunks=total_chunks,
            estimated_entities=self._get_str_estimation_output(
                estimated_entities
            ),
            estimated_triples=self._get_str_estimation_output(
                estimated_triples
            ),
            estimated_llm_calls=self._get_str_estimation_output(
                estimated_llm_calls
            ),
            estimated_total_in_out_tokens_in_millions=self._get_str_estimation_output(
                total_in_out_tokens
            ),
            estimated_cost_in_usd=self._get_str_estimation_output(
                estimated_cost
            ),
            estimated_total_time_in_minutes="Depends on your API key tier. Accurate estimate coming soon. Rough estimate: "
            + self._get_str_estimation_output(total_time_in_minutes),
        )

    async def get_enrichment_estimate(
        self, collection_id: UUID, kg_enrichment_settings: KGEnrichmentSettings
    ) -> KGEnrichmentEstimationResponse:

        document_ids = [
            doc.id
            for doc in (
                await self.collection_handler.documents_in_collection(collection_id)  # type: ignore
            )["results"]
        ]

        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("document_entity")} WHERE document_id = ANY($1);
        """
        entity_count = (
            await self.connection_manager.fetch_query(QUERY, [document_ids])
        )[0]["count"]

        if not entity_count:
            raise ValueError(
                "No entities found in the graph. Please run `create-graph` first."
            )

        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("chunk_triple")} WHERE document_id = ANY($1);
        """
        triple_count = (
            await self.connection_manager.fetch_query(QUERY, [document_ids])
        )[0]["count"]

        estimated_llm_calls = (entity_count // 10, entity_count // 5)
        estimated_total_in_out_tokens_in_millions = (
            2000 * estimated_llm_calls[0] / 1000000,
            2000 * estimated_llm_calls[1] / 1000000,
        )
        cost_per_million_tokens = llm_cost_per_million_tokens(
            kg_enrichment_settings.generation_config.model
        )
        estimated_cost = (
            estimated_total_in_out_tokens_in_millions[0]
            * cost_per_million_tokens,
            estimated_total_in_out_tokens_in_millions[1]
            * cost_per_million_tokens,
        )

        estimated_total_time = (
            estimated_total_in_out_tokens_in_millions[0] * 10 / 60,
            estimated_total_in_out_tokens_in_millions[1] * 10 / 60,
        )

        return KGEnrichmentEstimationResponse(
            message='Ran Graph Enrichment Estimate (not the actual run). Note that these are estimated ranges, actual values may vary. To run the KG enrichment process, run `enrich-graph` with `--run` in the cli, or `run_type="run"` in the client.',
            total_entities=entity_count,
            total_triples=triple_count,
            estimated_llm_calls=self._get_str_estimation_output(
                estimated_llm_calls
            ),
            estimated_total_in_out_tokens_in_millions=self._get_str_estimation_output(
                estimated_total_in_out_tokens_in_millions
            ),
            estimated_cost_in_usd=self._get_str_estimation_output(
                estimated_cost
            ),
            estimated_total_time_in_minutes="Depends on your API key tier. Accurate estimate coming soon. Rough estimate: "
            + self._get_str_estimation_output(estimated_total_time),
        )

    async def create_vector_index(self):
        # need to implement this. Just call vector db provider's create_vector_index method.
        # this needs to be run periodically for every collection.
        raise NotImplementedError

    async def delete_triples(self, triple_ids: list[int]):
        # need to implement this.
        raise NotImplementedError

    async def get_schema(self):
        # somehow get the rds from the postgres db.
        raise NotImplementedError

    async def get_entities(
        self,
        collection_id: Optional[UUID] = None,
        entity_ids: Optional[list[str]] = None,
        entity_names: Optional[list[str]] = None,
        entity_table_name: str = "document_entity",
        offset: int = 0,
        limit: int = -1,
    ) -> dict:
        conditions = []
        params: list = [collection_id]
        param_index = 2

        if entity_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(entity_ids)
            param_index += 1

        if entity_names:
            conditions.append(f"name = ANY(${param_index})")
            params.append(entity_names)
            param_index += 1

        pagination_params = []
        if offset:
            pagination_params.append(f"OFFSET ${param_index}")
            params.append(offset)
            param_index += 1

        if limit != -1:
            pagination_params.append(f"LIMIT ${param_index}")
            params.append(limit)
            param_index += 1

        pagination_clause = " ".join(pagination_params)

        if entity_table_name == "collection_entity":
            query = f"""
            SELECT id, name, description, extraction_ids, document_ids
            FROM {self._get_table_name(entity_table_name)}
            WHERE collection_id = $1
            {" AND " + " AND ".join(conditions) if conditions else ""}
            ORDER BY id
            {pagination_clause}
            """
        else:
            query = f"""
            SELECT id, name, description, extraction_ids, document_id
            FROM {self._get_table_name(entity_table_name)}
            WHERE document_id = ANY(
                SELECT document_id FROM {self._get_table_name("document_info")}
                WHERE $1 = ANY(collection_ids)
            )
            {" AND " + " AND ".join(conditions) if conditions else ""}
            ORDER BY id
            {pagination_clause}
            """

        results = await self.connection_manager.fetch_query(query, params)
        entities = [Entity(**entity) for entity in results]

        total_entries = await self.get_entity_count(
            collection_id=collection_id, entity_table_name=entity_table_name
        )

        return {"entities": entities, "total_entries": total_entries}

    async def get_triples(
        self,
        collection_id: Optional[UUID] = None,
        entity_names: Optional[list[str]] = None,
        triple_ids: Optional[list[str]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = -1,
    ) -> dict:
        conditions = []
        params: list = [str(collection_id)]
        param_index = 2

        if triple_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(triple_ids)
            param_index += 1

        if entity_names:
            conditions.append(
                f"subject = ANY(${param_index}) or object = ANY(${param_index})"
            )
            params.append(entity_names)
            param_index += 1

        pagination_params = []
        if offset:
            pagination_params.append(f"OFFSET ${param_index}")
            params.append(offset)
            param_index += 1

        if limit != -1:
            pagination_params.append(f"LIMIT ${param_index}")
            params.append(limit)
            param_index += 1

        pagination_clause = " ".join(pagination_params)

        query = f"""
            SELECT id, subject, predicate, object, description
            FROM {self._get_table_name("chunk_triple")}
            WHERE document_id = ANY(
                SELECT document_id FROM {self._get_table_name("document_info")}
                WHERE $1 = ANY(collection_ids)
            )
            {" AND " + " AND ".join(conditions) if conditions else ""}
            ORDER BY id
            {pagination_clause}
        """

        triples = await self.connection_manager.fetch_query(query, params)
        triples = [Relationship(**triple) for triple in triples]
        total_entries = await self.get_triple_count(
            collection_id=collection_id
        )

        return {"triples": triples, "total_entries": total_entries}

    async def structured_query(self):
        raise NotImplementedError

    async def update_extraction_prompt(self):
        raise NotImplementedError

    async def update_kg_search_prompt(self):
        raise NotImplementedError

    async def upsert_triples(self):
        raise NotImplementedError

    async def get_entity_count(
        self,
        collection_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
        distinct: bool = False,
        entity_table_name: str = "document_entity",
    ) -> int:
        if collection_id is None and document_id is None:
            raise ValueError(
                "Either collection_id or document_id must be provided."
            )

        conditions = []
        params = []

        if entity_table_name == "collection_entity":
            if document_id:
                raise ValueError(
                    "document_id is not supported for collection_entity table"
                )
            conditions.append("collection_id = $1")
            params.append(str(collection_id))
        elif collection_id:
            conditions.append(
                f"""
                document_id = ANY(
                    SELECT document_id FROM {self._get_table_name("document_info")}
                    WHERE $1 = ANY(collection_ids)
                )
                """
            )
            params.append(str(collection_id))
        else:
            conditions.append("document_id = $1")
            params.append(str(document_id))

        count_value = "DISTINCT name" if distinct else "*"

        QUERY = f"""
            SELECT COUNT({count_value}) FROM {self._get_table_name(entity_table_name)}
            WHERE {" AND ".join(conditions)}
        """
        return (await self.connection_manager.fetch_query(QUERY, params))[0][
            "count"
        ]

    async def get_triple_count(
        self,
        collection_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
    ) -> int:
        if collection_id is None and document_id is None:
            raise ValueError(
                "Either collection_id or document_id must be provided."
            )

        conditions = []
        params = []

        if collection_id:
            conditions.append(
                f"""
                document_id = ANY(
                    SELECT document_id FROM {self._get_table_name("document_info")}
                    WHERE $1 = ANY(collection_ids)
                )
                """
            )
            params.append(str(collection_id))
        else:
            conditions.append("document_id = $1")
            params.append(str(document_id))

        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("chunk_triple")}
            WHERE {" AND ".join(conditions)}
        """
        return (await self.connection_manager.fetch_query(QUERY, params))[0][
            "count"
        ]

    async def update_entity_descriptions(self, entities: list[Entity]):

        query = f"""
            UPDATE {self._get_table_name("collection_entity")}
            SET description = $3, description_embedding = $4
            WHERE name = $1 AND collection_id = $2
        """

        inputs = [
            (
                entity.name,
                entity.collection_id,
                entity.description,
                entity.description_embedding,
            )
            for entity in entities
        ]

        await self.connection_manager.execute_many(query, inputs)  # type: ignore

    async def get_deduplication_estimate(
        self,
        collection_id: UUID,
        kg_deduplication_settings: KGEntityDeduplicationSettings,
    ):
        try:
            # number of documents in collection
            query = f"""
                SELECT name, count(name)
                FROM {self._get_table_name("document_entity")}
                WHERE document_id = ANY(
                    SELECT document_id FROM {self._get_table_name("document_info")}
                    WHERE $1 = ANY(collection_ids)
                )
                GROUP BY name
                HAVING count(name) >= 5
            """
            entities = await self.connection_manager.fetch_query(
                query, [collection_id]
            )
            num_entities = len(entities)

            estimated_llm_calls = (num_entities, num_entities)
            estimated_total_in_out_tokens_in_millions = (
                estimated_llm_calls[0] * 1000 / 1000000,
                estimated_llm_calls[1] * 5000 / 1000000,
            )
            estimated_cost_in_usd = (
                estimated_total_in_out_tokens_in_millions[0]
                * llm_cost_per_million_tokens(
                    kg_deduplication_settings.generation_config.model
                ),
                estimated_total_in_out_tokens_in_millions[1]
                * llm_cost_per_million_tokens(
                    kg_deduplication_settings.generation_config.model
                ),
            )

            estimated_total_time_in_minutes = (
                estimated_total_in_out_tokens_in_millions[0] * 10 / 60,
                estimated_total_in_out_tokens_in_millions[1] * 10 / 60,
            )

            return KGDeduplicationEstimationResponse(
                message='Ran Deduplication Estimate (not the actual run). Note that these are estimated ranges, actual values may vary. To run the Deduplication process, run `deduplicate-entities` with `--run` in the cli, or `run_type="run"` in the client.',
                num_entities=num_entities,
                estimated_llm_calls=self._get_str_estimation_output(
                    estimated_llm_calls
                ),
                estimated_total_in_out_tokens_in_millions=self._get_str_estimation_output(
                    estimated_total_in_out_tokens_in_millions
                ),
                estimated_cost_in_usd=self._get_str_estimation_output(
                    estimated_cost_in_usd
                ),
                estimated_total_time_in_minutes=self._get_str_estimation_output(
                    estimated_total_time_in_minutes
                ),
            )
        except UndefinedTableError as e:
            logger.error(
                f"Entity embedding table not found. Please run `create-graph` first. {str(e)}"
            )
            raise R2RException(
                message="Entity embedding table not found. Please run `create-graph` first.",
                status_code=404,
            )
        except PostgresError as e:
            logger.error(
                f"Database error in get_deduplication_estimate: {str(e)}"
            )
            raise R2RException(
                message="An error occurred while fetching the deduplication estimate.",
                status_code=500,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error in get_deduplication_estimate: {str(e)}"
            )
            raise R2RException(
                message="An unexpected error occurred while fetching the deduplication estimate.",
                status_code=500,
            )
