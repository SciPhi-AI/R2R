# okay let's roll it.
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional, Tuple, Union
from uuid import UUID

import asyncpg

from core import KGEnrichmentSettings, KGExtraction
from core.base import (
    Community,
    DatabaseProvider,
    EmbeddingProvider,
    Entity,
    KGConfig,
    KGProvider,
    Triple,
)

logger = logging.getLogger(__name__)

from typing import Optional


class PostgresKGProvider(KGProvider):

    def __init__(
        self,
        config: KGConfig,
        db_provider: DatabaseProvider,
        embedding_provider: EmbeddingProvider,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, *args, **kwargs)

        self.db_provider = db_provider.relational
        self.embedding_provider = embedding_provider
        try:
            import networkx as nx

            self.nx = nx
        except ImportError as exc:
            raise ImportError(
                "NetworkX is not installed. Please install it to use this module."
            ) from exc

    async def initialize(self):
        logger.info(
            f"Initializing PostgresKGProvider for project {self.db_provider.project_name}"
        )
        await self.create_tables(project_name=self.db_provider.project_name)

    async def execute_query(
        self, query: str, params: Optional[list[tuple[Any]]] = None
    ) -> Any:
        return await self.db_provider.execute_query(query, params)

    async def execute_many(
        self,
        query: str,
        params: Optional[list[tuple[Any]]] = None,
        batch_size: int = 1000,
    ) -> Any:
        return await self.db_provider.execute_many(query, params, batch_size)

    async def fetch_query(
        self, query: str, params: Optional[list[tuple[Any]]] = None
    ) -> Any:
        return await self.db_provider.fetch_query(query, params)

    def _get_table_name(self, base_name: str) -> str:
        return self.db_provider._get_table_name(base_name)

    async def create_tables(self, project_name: str):
        # raw entities table
        # create schema

        query = f"""

            CREATE TABLE IF NOT EXISTS {self._get_table_name("entity_raw")} (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            extraction_ids UUID[] NOT NULL,
            document_id UUID NOT NULL,
            attributes JSONB
        );
        """
        await self.execute_query(query)

        # raw triples table, also the final table. this will have embeddings.
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("triple_raw")} (
            id SERIAL PRIMARY KEY,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            weight FLOAT NOT NULL,
            description TEXT NOT NULL,
            embedding vector({self.embedding_provider.config.base_dimension}),
            extraction_ids UUID[] NOT NULL,
            document_id UUID NOT NULL,
            attributes JSONB NOT NULL
        );
        """
        result = await self.execute_query(query)

        # entity description table, unique by document_id, category, name
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("entity_description")} (
            id SERIAL PRIMARY KEY,
            document_id UUID NOT NULL,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            description_embedding vector(1536),
            extraction_ids UUID[] NOT NULL,
            attributes JSONB NOT NULL,
            UNIQUE (document_id, category, name)
        );"""

        result = await self.execute_query(query)

        # triples table 2 # Relationship summaries by document ID
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("triple_description")} (
            id SERIAL PRIMARY KEY,
            document_ids UUID[] NOT NULL,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            weight FLOAT NOT NULL,
            description TEXT NOT NULL,
            extraction_ids UUID[] NOT NULL,
            attributes JSONB NOT NULL,
            UNIQUE (document_ids, subject, predicate, object)
        );"""

        result = await self.execute_query(query)

        # embeddings tables
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("entity_embedding")} (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            description_embedding vector({self.embedding_provider.config.base_dimension}) NOT NULL,
            UNIQUE (name)
            );
        """

        result = await self.execute_query(query)

        # triples embeddings table
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("triple_embedding")} (
            id SERIAL PRIMARY KEY,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            description_embedding vector({self.embedding_provider.config.base_dimension}) NOT NULL,
            UNIQUE (subject, predicate, object)
            );
        """

        result = await self.execute_query(query)

        # communities table, result of the Leiden algorithm
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("community")} (
            id SERIAL PRIMARY KEY,
            node TEXT NOT NULL,
            cluster INT NOT NULL,
            parent_cluster INT,
            level INT NOT NULL,
            is_final_cluster BOOLEAN NOT NULL,
            triple_ids INT[] NOT NULL
        );"""

        result = await self.execute_query(query)

        # communities_report table
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("community_report")} (
            id SERIAL PRIMARY KEY,
            community_id INT NOT NULL,
            collection_id UUID NOT NULL,
            level INT NOT NULL,
            name TEXT NOT NULL,
            summary TEXT NOT NULL,
            findings TEXT[] NOT NULL,
            rating FLOAT NOT NULL,
            rating_explanation TEXT NOT NULL,
            embedding vector({self.embedding_provider.config.base_dimension}) NOT NULL,
            attributes JSONB,
            UNIQUE (community_id, level, collection_id)
        );"""

        result = await self.execute_query(query)

    async def _add_objects(
        self, objects: list[Any], table_name: str
    ) -> asyncpg.Record:
        """
        Upsert objects into the specified table.
        """
        # Get non-null attributes from the first object
        non_null_attrs = {
            k: v for k, v in objects[0].__dict__.items() if v is not None
        }
        columns = ", ".join(non_null_attrs.keys())

        placeholders = ", ".join(f"${i+1}" for i in range(len(non_null_attrs)))

        print(
            f"Inseriting {len(objects)} objects into {table_name} with columns: {columns} in table {self._get_table_name(table_name)}"
        )

        QUERY = f"""
            INSERT INTO {self._get_table_name(table_name)} ({columns})
            VALUES ({placeholders})
        """

        # Filter out null values for each object
        params = [
            tuple(
                json.dumps(v) if isinstance(v, dict) else v
                for v in obj.__dict__.values()
                if v is not None
            )
            for obj in objects
        ]
        return await self.execute_many(QUERY, params)

    async def add_entities(
        self,
        entities: list[Entity],
        table_name: str,
    ) -> asyncpg.Record:
        """
        Upsert entities into the entities_raw table. These are raw entities extracted from the document.

        Args:
            entities: list[Entity]: list of entities to upsert
            collection_name: str: name of the collection

        Returns:
            result: asyncpg.Record: result of the upsert operation
        """
        return await self._add_objects(entities, table_name)

    async def add_triples(
        self,
        triples: list[Triple],
        table_name: str,
    ) -> asyncpg.Record:
        """
        Upsert triples into the triple_raw table. These are raw triples extracted from the document.

        Args:
            triples: list[Triple]: list of triples to upsert
            table_name: str: name of the table to upsert into

        Returns:
            result: asyncpg.Record: result of the upsert operation
        """
        return await self._add_objects(triples, table_name)

    async def add_kg_extractions(
        self,
        kg_extractions: list[KGExtraction],
        table_suffix: str = "_raw",
    ) -> Tuple[int, int]:
        """
        Upsert entities and triples into the database. These are raw entities and triples extracted from the document fragments.

        Args:
            kg_extractions: list[KGExtraction]: list of KG extractions to upsert
            table_suffix: str: suffix to add to the table names

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
                    extraction.entities,
                    table_name="entity" + table_suffix,
                )

            if extraction.triples:
                if not extraction.triples[0].extraction_ids:
                    for i in range(len(extraction.triples)):
                        extraction.triples[i].extraction_ids = (
                            extraction.extraction_ids
                        )
                    extraction.triples[i].document_id = extraction.document_id

                await self.add_triples(
                    extraction.triples,
                    table_name="triple" + table_suffix,
                )

        logger.info(
            f"Upserted {total_entities} entities and {total_relationships} relationships into the database."
        )

        return (total_entities, total_relationships)

    async def get_entity_map(
        self, offset: int, limit: int, document_id: str
    ) -> dict[str, Any]:

        QUERY1 = f"""
            WITH entities_list AS (

                SELECT DISTINCT name
                FROM {self._get_table_name("entity_raw")}
                WHERE document_id = $1
                ORDER BY name ASC
                LIMIT {limit} OFFSET {offset}
            )
            SELECT DISTINCT e.name, e.description, e.category
            FROM {self._get_table_name("entity_raw")} e
            JOIN entities_list el ON e.name = el.name
            ORDER BY e.name;"""

        entities_list = await self.fetch_query(QUERY1, [document_id])
        entities_list = [
            {
                "name": entity["name"],
                "description": entity["description"],
                "category": entity["category"],
            }
            for entity in entities_list
        ]

        QUERY2 = f"""
            WITH entities_list AS (

                SELECT DISTINCT name
                FROM {self._get_table_name("entity_raw")}
                WHERE document_id = $1
                ORDER BY name ASC
                LIMIT {limit} OFFSET {offset}
            )

            SELECT DISTINCT t.subject, t.predicate, t.object, t.weight, t.description
            FROM {self._get_table_name("triple_raw")} t
            JOIN entities_list el ON t.subject = el.name
            ORDER BY t.subject, t.predicate, t.object;
        """

        triples_list = await self.fetch_query(QUERY2, [document_id])
        triples_list = [
            {
                "subject": triple["subject"],
                "predicate": triple["predicate"],
                "object": triple["object"],
                "weight": triple["weight"],
                "description": triple["description"],
            }
            for triple in triples_list
        ]

        entity_map = {}
        for entity in entities_list:
            if entity["name"] not in entity_map:
                entity_map[entity["name"]] = {"entities": [], "triples": []}
            entity_map[entity["name"]]["entities"].append(entity)

        for triple in triples_list:
            if triple["subject"] in entity_map:
                entity_map[triple["subject"]]["triples"].append(triple)
            if triple["object"] in entity_map:
                entity_map[triple["object"]]["triples"].append(triple)

        return entity_map

    async def upsert_embeddings(
        self,
        data: list[dict[str, Any]],
        table_name: str,
    ) -> None:
        QUERY = f"""
            INSERT INTO {self._get_table_name(table_name)} (name, description, description_embedding)
            VALUES ($1, $2, $3)
            ON CONFLICT (name) DO UPDATE SET
                description = EXCLUDED.description,
                description_embedding = EXCLUDED.description_embedding
            """
        return await self.execute_many(QUERY, data)

    async def upsert_entities(self, entities: list[Entity]) -> None:
        QUERY = """
            INSERT INTO $1.$2 (category, name, description, description_embedding, extraction_ids, document_id, attributes)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """

        table_name = self._get_table_name("entities")
        query = QUERY.format(table_name)
        await self.execute_query(query, entities)

    async def upsert_relationships(self, relationships: list[Triple]) -> None:
        QUERY = """
            INSERT INTO $1.$2 (source, target, relationship)
            VALUES ($1, $2, $3)
            """

        table_name = self._get_table_name("triples")
        query = QUERY.format(table_name)
        await self.execute_query(query, relationships)

    async def vector_query(self, query: str, **kwargs: Any) -> Any:

        query_embedding = kwargs.get("query_embedding", None)
        search_type = kwargs.get("search_type", "__Entity__")
        embedding_type = kwargs.get("embedding_type", "description_embedding")
        property_names = kwargs.get("property_names", ["name", "description"])
        limit = kwargs.get("limit", 10)

        table_name = ""
        if search_type == "__Entity__":
            table_name = "entity_embedding"
        elif search_type == "__Relationship__":
            table_name = "triple_raw"
        elif search_type == "__Community__":
            table_name = "community_report"
        else:
            raise ValueError(f"Invalid search type: {search_type}")

        property_names_str = ", ".join(property_names)
        QUERY = f"""
                SELECT {property_names_str} FROM {self._get_table_name(table_name)} ORDER BY {embedding_type} <=> $1 LIMIT $2;
        """

        results = await self.fetch_query(QUERY, (str(query_embedding), limit))

        for result in results:
            yield {
                property_name: result[property_name]
                for property_name in property_names
            }

    async def get_all_triples(self, collection_id: UUID) -> list[Triple]:

        # getting all documents for a collection
        QUERY = f"""
            select distinct document_id from {self._get_table_name("document_info")} where $1 = ANY(collection_ids)
        """
        document_ids = await self.fetch_query(QUERY, [collection_id])
        document_ids = [doc_id["document_id"] for doc_id in document_ids]

        QUERY = f"""
            SELECT id, subject, predicate, weight, object FROM {self._get_table_name("triple_raw")} WHERE document_id = ANY($1)
        """
        triples = await self.fetch_query(QUERY, [document_ids])
        return triples

    async def add_communities(
        self, communities: list[tuple[int, Any]]
    ) -> None:
        QUERY = f"""
            INSERT INTO {self._get_table_name("community")} (node, cluster, parent_cluster, level, is_final_cluster, triple_ids)
            VALUES ($1, $2, $3, $4, $5, $6)
            """
        await self.execute_many(QUERY, communities)

    async def add_community_report(
        self, community: Community, collection_id: UUID
    ) -> None:

        community.embedding = str(community.embedding)

        await self._add_objects([community], "community_report")

        # await self.execute_query(

    async def perform_graph_clustering(
        self, collection_id: UUID, leiden_params: dict
    ) -> Tuple[int, int, set[tuple[int, Any]]]:
        # TODO: implementing the clustering algorithm but now we will get communities at a document level and then we will get communities at a higher level.
        # we will use the Leiden algorithm for this.
        # but for now let's skip it and make other stuff work.
        # we will need multiple tables for this to work.

        settings = {}
        triples = await self.get_all_triples(collection_id)

        logger.info(f"Clustering with settings: {str(settings)}")

        G = self.nx.Graph()
        for triple in triples:
            G.add_edge(
                triple["subject"],
                triple["object"],
                weight=triple["weight"],
                id=triple["id"],
            )

        hierarchical_communities = await self._compute_leiden_communities(
            G, leiden_params
        )

        async def triple_ids(node: int) -> list[int]:
            return [
                triple["id"]
                for triple in triples
                if triple["subject"] == node or triple["object"] == node
            ]

        # upsert the communities into the database.
        inputs = [
            (
                item.node,
                item.cluster,
                item.parent_cluster,
                item.level,
                item.is_final_cluster,
                (await triple_ids(item.node)),
            )
            for item in hierarchical_communities
        ]

        result = await self.add_communities(inputs)

        num_communities = len(
            set([item.cluster for item in hierarchical_communities])
        )
        # num_hierarchies = len(set([item.level for item in hierarchical_communities]))
        # intermediate_communities = set([(item.level, item.cluster) for item in hierarchical_communities])

        return num_communities

    async def _compute_leiden_communities(
        self,
        graph: Any,
        leiden_params: dict,
    ) -> dict[int, dict[str, int]]:
        """Compute Leiden communities."""
        try:
            from graspologic.partition import hierarchical_leiden

            community_mapping = hierarchical_leiden(graph)

            return community_mapping

        except ImportError as e:
            raise ImportError("Please install the graspologic package.") from e

    async def get_community_details(self, community_id: int):

        QUERY = f"""
            SELECT level FROM {self._get_table_name("community")} WHERE cluster = $1
            LIMIT 1
        """
        level = (await self.fetch_query(QUERY, [community_id]))[0]["level"]

        QUERY = f"""
            WITH node_triple_ids AS (

                SELECT node, triple_ids
                FROM {self._get_table_name("community")}
                WHERE cluster = $1
            )
            SELECT DISTINCT
                e.id AS id,
                e.name AS name,
                e.description AS description
            FROM node_triple_ids nti
            JOIN {self._get_table_name("entity_embedding")} e ON e.name = nti.node;
        """
        entities = await self.fetch_query(QUERY, [community_id])

        QUERY = f"""
            WITH node_triple_ids AS (

                SELECT node, triple_ids
                FROM {self._get_table_name("community")}
                WHERE cluster = $1
            )
            SELECT DISTINCT
                t.id, t.subject, t.predicate, t.object, t.weight, t.description
            FROM node_triple_ids nti
            JOIN {self._get_table_name("triple_raw")} t ON t.id = ANY(nti.triple_ids);
        """
        triples = await self.fetch_query(QUERY, [community_id])

        return level, entities, triples

    # async def client(self):
    #     return None

    async def create_vector_index(self):
        # need to implement this. Just call vector db provider's create_vector_index method.
        # this needs to be run periodically for every collection.
        pass

    async def delete_triples(self, triple_ids: list[int]):
        # need to implement this.
        pass

    async def get_schema(self):
        # somehow get the rds from the postgres db.
        pass

    async def get_entities(self, collection_id: str):
        pass

    async def get_triples(self, collection_id: str):
        pass

    async def structured_query(self):
        pass

    async def update_extraction_prompt(self):
        pass

    async def update_kg_search_prompt(self):
        pass

    async def upsert_triples(self):
        pass

    async def get_entity_count(self, document_id: str) -> int:
        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("entity_raw")} WHERE document_id = $1
        """
        return (await self.fetch_query(QUERY, [document_id]))[0]["count"]
