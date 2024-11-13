import json
import logging
import time
from typing import Any, AsyncGenerator, Optional, Tuple
from uuid import UUID
from fastapi import HTTPException

import asyncpg
from asyncpg.exceptions import PostgresError, UndefinedTableError

from core.base import (
    Community,
    Entity,
    KGExtraction,
    KGExtractionStatus,
    KGHandler,
    R2RException,
    Relationship,
)
from core.base.abstractions import (
    CommunityInfo,
    EntityLevel,
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEnrichmentStatus,
    KGEntityDeduplicationSettings,
    VectorQuantizationType,
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

        # raw relationships table, also the final table. this will have embeddings.
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("chunk_relationship")} (
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
            relationship_ids INT[] NOT NULL,
            collection_id UUID NOT NULL
        );"""

        await self.connection_manager.execute_query(query)

        # communities_report table
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("community")} (
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

        document_ids = [
            doc_id["document_id"] for doc_id in kg_extraction_statuses
        ]

        kg_enrichment_statuses = await self.connection_manager.fetch_query(
            f"SELECT enrichment_status FROM {self._get_table_name(PostgresCollectionHandler.TABLE_NAME)} WHERE id = $1",
            [collection_id],
        )

        # entity and relationship counts
        chunk_entity_count = await self.connection_manager.fetch_query(
            f"SELECT COUNT(*) FROM {self._get_table_name('chunk_entity')} WHERE document_id = ANY($1)",
            [document_ids],
        )

        chunk_relationship_count = await self.connection_manager.fetch_query(
            f"SELECT COUNT(*) FROM {self._get_table_name('chunk_relationship')} WHERE document_id = ANY($1)",
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
            f"SELECT COUNT(*) FROM {self._get_table_name('community')} WHERE collection_id = $1",
            [collection_id],
        )

        return {
            "kg_extraction_statuses": kg_extraction_statuses,
            "kg_enrichment_status": kg_enrichment_statuses[0][
                "enrichment_status"
            ],
            "chunk_entity_count": chunk_entity_count[0]["count"],
            "chunk_relationship_count": chunk_relationship_count[0]["count"],
            "document_entity_count": document_entity_count[0]["count"],
            "collection_entity_count": collection_entity_count[0]["count"],
            "community_count": community_count[0]["count"],
        }

    ### Relationships BEGIN ####
    async def add_relationships(
        self,
        relationships: list[Relationship],
        table_name: str = "chunk_relationship",
    ) -> None:
        """
        Upsert relationships into the chunk_relationship table. These are raw relationships extracted from the document.

        Args:
            relationships: list[Relationship]: list of relationships to upsert
            table_name: str: name of the table to upsert into

        Returns:
            result: asyncpg.Record: result of the upsert operation
        """
        return await self._add_objects(
            [ele.to_dict() for ele in relationships], table_name
        )

    async def list_relationships_v3(
        self,
        level: EntityLevel,
        id: UUID,
        entity_names: Optional[list[str]] = None,
        relationship_types: Optional[list[str]] = None,
        attributes: Optional[list[str]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ):
        filter_query = ""
        if entity_names:
            filter_query += "AND (subject IN ($2) OR object IN ($2))"
        if relationship_types:
            filter_query += "AND predicate IN ($3)"

        if level == EntityLevel.CHUNK:
            QUERY = f"""
                SELECT * FROM {self._get_table_name("chunk_relationship")} WHERE $1 = ANY(chunk_ids)
                {filter_query}
            """
        elif level == EntityLevel.DOCUMENT:
            QUERY = f"""
                SELECT * FROM {self._get_table_name("chunk_relationship")} WHERE $1 = document_id
                {filter_query}
            """
        elif level == EntityLevel.COLLECTION:
            QUERY = f"""
                WITH document_ids AS (
                    SELECT document_id FROM {self._get_table_name("document_info")} WHERE $1 = ANY(collection_ids)
                )
                SELECT * FROM {self._get_table_name("chunk_relationship")} WHERE document_id IN (SELECT document_id FROM document_ids)
                {filter_query}
            """

        results = await self.connection_manager.fetch_query(
            QUERY, [id, entity_names, relationship_types]
        )

        if attributes:
            results = [
                {k: v for k, v in result.items() if k in attributes}
                for result in results
            ]

        return results

    ### Relationships END ####
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
            FROM {self._get_table_name("chunk_relationship")} t
            JOIN entities_list el ON t.subject = el.name
            ORDER BY t.subject, t.predicate, t.object;
        """

        relationships_list = await self.connection_manager.fetch_query(
            QUERY2, [document_id]
        )
        relationships_list = [
            Relationship(
                subject=relationship["subject"],
                predicate=relationship["predicate"],
                object=relationship["object"],
                weight=relationship["weight"],
                description=relationship["description"],
                extraction_ids=relationship["extraction_ids"],
                document_id=relationship["document_id"],
            )
            for relationship in relationships_list
        ]

        entity_map: dict[str, dict[str, list[Any]]] = {}
        for entity in entities_list:
            if entity.name not in entity_map:
                entity_map[entity.name] = {"entities": [], "relationships": []}
            entity_map[entity.name]["entities"].append(entity)

        for relationship in relationships_list:
            if relationship.subject in entity_map:
                entity_map[relationship.subject]["relationships"].append(
                    relationship
                )
            if relationship.object in entity_map:
                entity_map[relationship.object]["relationships"].append(
                    relationship
                )

        return entity_map

    async def graph_search(  # type: ignore
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
            table_name = "chunk_relationship"
        elif search_type == "__Community__":
            table_name = "community"
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

    async def get_all_relationships(
        self, collection_id: UUID
    ) -> list[Relationship]:

        # getting all documents for a collection
        if document_ids is None:
            QUERY = f"""
                select distinct document_id from {self._get_table_name("document_info")} where $1 = ANY(collection_ids)
            """
            document_ids_list = await self.connection_manager.fetch_query(
                QUERY, [collection_id]
            )
            document_ids = [
                doc_id["document_id"] for doc_id in document_ids_list
            ]

        QUERY = f"""
            SELECT id, subject, predicate, weight, object, document_id FROM {self._get_table_name("chunk_relationship")} WHERE document_id = ANY($1)
        """
        relationships = await self.connection_manager.fetch_query(
            QUERY, [document_ids]
        )
        return [Relationship(**relationship) for relationship in relationships]

    async def add_community_info(
        self, communities: list[CommunityInfo]
    ) -> None:
        QUERY = f"""
            INSERT INTO {self._get_table_name("community_info")} (node, cluster, parent_cluster, level, is_final_cluster, relationship_ids, collection_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """
        communities_tuples_list = [
            (
                community.node,
                community.cluster,
                community.parent_cluster,
                community.level,
                community.is_final_cluster,
                community.relationship_ids,
                community.collection_id,
            )
            for community in communities
        ]
        await self.connection_manager.execute_many(
            QUERY, communities_tuples_list
        )

    async def get_communities(
        self,
        offset: int,
        limit: int,
        collection_id: Optional[UUID] = None,
        levels: Optional[list[int]] = None,
        community_numbers: Optional[list[int]] = None,
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
            FROM {self._get_table_name('community')}
            WHERE collection_id = $1
            {" AND " + " AND ".join(conditions) if conditions else ""}
            ORDER BY community_number
            {pagination_clause}
        """

        results = await self.connection_manager.fetch_query(query, params)
        total_entries = results[0]["total_entries"] if results else 0
        communities = [Community(**community) for community in results]

        return {
            "communities": communities,
            "total_entries": total_entries,
        }

    async def add_community(
        self, community: Community
    ) -> None:

        # TODO: Fix in the short term.
        # we need to do this because postgres insert needs to be a string
        community.embedding = str(community.embedding)  # type: ignore[assignment]

        non_null_attrs = {
            k: v for k, v in community.__dict__.items() if v is not None
        }
        columns = ", ".join(non_null_attrs.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(non_null_attrs)))

        conflict_columns = ", ".join(
            [f"{k} = EXCLUDED.{k}" for k in non_null_attrs]
        )

        QUERY = f"""
            INSERT INTO {self._get_table_name("community")} ({columns})
            VALUES ({placeholders})
            ON CONFLICT (community_number, level, collection_id) DO UPDATE SET
                {conflict_columns}
            """

        await self.connection_manager.execute_many(
            QUERY, [tuple(non_null_attrs.values())]
        )

    async def _create_graph_and_cluster(
        self, relationships: list[Relationship], leiden_params: dict[str, Any]
    ) -> Any:

        G = self.nx.Graph()
        for relationship in relationships:
            G.add_edge(
                relationship.subject,
                relationship.object,
                weight=relationship.weight,
                id=relationship.id,
            )

        hierarchical_communities = await self._compute_leiden_communities(
            G, leiden_params
        )

        return hierarchical_communities

    async def _cluster_and_add_community_info(
        self,
        relationships: list[Relationship],
        relationship_ids_cache: dict[str, list[int]],
        leiden_params: dict[str, Any],
        collection_id: UUID,
    ) -> int:

        # clear if there is any old information
        QUERY = f"""
            DELETE FROM {self._get_table_name("community_info")} WHERE collection_id = $1
        """
        await self.connection_manager.execute_query(QUERY, [collection_id])

        QUERY = f"""
            DELETE FROM {self._get_table_name("community")} WHERE collection_id = $1
        """
        await self.connection_manager.execute_query(QUERY, [collection_id])

        start_time = time.time()

        hierarchical_communities = await self._create_graph_and_cluster(
            relationships, leiden_params
        )

        logger.info(
            f"Computing Leiden communities completed, time {time.time() - start_time:.2f} seconds."
        )

        def relationship_ids(node: str) -> list[int]:
            return relationship_ids_cache.get(node, [])

        logger.info(
            f"Cached {len(relationship_ids_cache)} relationship ids, time {time.time() - start_time:.2f} seconds."
        )

        # upsert the communities into the database.
        inputs = [
            CommunityInfo(
                node=str(item.node),
                cluster=item.cluster,
                parent_cluster=item.parent_cluster,
                level=item.level,
                is_final_cluster=item.is_final_cluster,
                relationship_ids=relationship_ids(item.node),
                collection_id=collection_id,
            )
            for item in hierarchical_communities
        ]

        await self.add_community_info(inputs)

        num_communities = (
            max([item.cluster for item in hierarchical_communities]) + 1
        )

        logger.info(
            f"Generated {num_communities} communities, time {time.time() - start_time:.2f} seconds."
        )

        return num_communities

    async def _use_community_cache(
        self, collection_id: UUID, relationship_ids_cache: dict[str, list[int]]
    ) -> bool:

        # check if status is enriched or stale
        QUERY = f"""
            SELECT kg_enrichment_status FROM {self._get_table_name("collections")} WHERE collection_id = $1
        """
        status = (
            await self.connection_manager.fetchrow_query(
                QUERY, [collection_id]
            )
        )["kg_enrichment_status"]
        if status == KGEnrichmentStatus.PENDING:
            return False

        # check the number of entities in the cache.
        QUERY = f"""
            SELECT COUNT(distinct node) FROM {self._get_table_name("community_info")} WHERE collection_id = $1
        """
        num_entities = (
            await self.connection_manager.fetchrow_query(
                QUERY, [collection_id]
            )
        )["count"]

        # a hard threshold of 80% of the entities in the cache.
        if num_entities > 0.8 * len(relationship_ids_cache):
            return True
        else:
            return False

    async def _get_relationship_ids_cache(
        self, relationships: list[Relationship]
    ) -> dict[str, list[int]]:

        # caching the relationship ids
        relationship_ids_cache = dict[str, list[int]]()
        for relationship in relationships:
            if (
                relationship.subject not in relationship_ids_cache
                and relationship.subject is not None
            ):
                relationship_ids_cache[relationship.subject] = []
            if (
                relationship.object not in relationship_ids_cache
                and relationship.object is not None
            ):
                relationship_ids_cache[relationship.object] = []
            if (
                relationship.subject is not None
                and relationship.id is not None
            ):
                relationship_ids_cache[relationship.subject].append(
                    relationship.id
                )
            if relationship.object is not None and relationship.id is not None:
                relationship_ids_cache[relationship.object].append(
                    relationship.id
                )

        return relationship_ids_cache

    async def _incremental_clustering(
        self,
        relationship_ids_cache: dict[str, list[int]],
        leiden_params: dict[str, Any],
        collection_id: UUID,
    ) -> int:
        """
        Performs incremental clustering on new relationships by:
        1. Getting all relationships and new relationships
        2. Getting community mapping for all existing relationships
        3. For each new relationship:
            - Check if subject/object exists in community mapping
            - If exists, add its cluster to updated communities set
            - If not, append relationship to new_relationship_ids list for clustering
        4. Run hierarchical clustering on new_relationship_ids list
        5. Update community info table with new clusters, offsetting IDs by max_cluster_id
        """

        QUERY = f"""
            SELECT node, cluster, is_final_cluster FROM {self._get_table_name("community_info")} WHERE collection_id = $1
        """

        communities = await self.connection_manager.fetch_query(
            QUERY, [collection_id]
        )
        max_cluster_id = max(
            [community["cluster"] for community in communities]
        )

        # TODO: modify above query to get a dict grouped by node (without aggregation)
        communities_dict = {}  # type: ignore
        for community in communities:
            if community["node"] not in communities_dict:
                communities_dict[community["node"]] = []
            communities_dict[community["node"]].append(community)

        QUERY = f"""
            SELECT document_id FROM {self._get_table_name("document_info")} WHERE $1 = ANY(collection_ids) and kg_extraction_status = $2
        """

        new_document_ids = await self.connection_manager.fetch_query(
            QUERY, [collection_id, KGExtractionStatus.SUCCESS]
        )

        new_relationship_ids = await self.get_all_relationships(
            collection_id, new_document_ids
        )

        # community mapping for new relationships
        updated_communities = set()
        new_relationships = []
        for relationship in new_relationship_ids:
            # bias towards subject
            if relationship.subject in communities_dict:
                for community in communities_dict[relationship.subject]:
                    updated_communities.add(community["cluster"])
            elif relationship.object in communities_dict:
                for community in communities_dict[relationship.object]:
                    updated_communities.add(community["cluster"])
            else:
                new_relationships.append(relationship)

        # delete the communities information for the updated communities
        QUERY = f"""
            DELETE FROM {self._get_table_name("community")} WHERE collection_id = $1 AND community_number = ANY($2)
        """
        await self.connection_manager.execute_query(
            QUERY, [collection_id, updated_communities]
        )

        hierarchical_communities_output = await self._create_graph_and_cluster(
            new_relationships, leiden_params
        )

        community_info = []
        for community in hierarchical_communities_output:
            community_info.append(
                CommunityInfo(
                    node=community.node,
                    cluster=community.cluster + max_cluster_id,
                    parent_cluster=(
                        community.parent_cluster + max_cluster_id
                        if community.parent_cluster is not None
                        else None
                    ),
                    level=community.level,
                    relationship_ids=[],  # FIXME: need to get the relationship ids for the community
                    is_final_cluster=community.is_final_cluster,
                    collection_id=collection_id,
                )
            )

        await self.add_community_info(community_info)
        num_communities = max([item.cluster for item in community_info]) + 1
        return num_communities

    async def perform_graph_clustering(
        self,
        collection_id: UUID,
        leiden_params: dict[str, Any],
    ) -> int:
        """
        Leiden clustering algorithm to cluster the knowledge graph relationships into communities.

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

        relationships = await self.get_all_relationships(collection_id)

        logger.info(f"Clustering with settings: {leiden_params}")

        relationship_ids_cache = await self._get_relationship_ids_cache(
            relationships
        )

        if await self._use_community_cache(
            collection_id, relationship_ids_cache
        ):
            num_communities = await self._incremental_clustering(
                relationship_ids_cache, leiden_params, collection_id
            )
        else:
            num_communities = await self._cluster_and_add_community_info(
                relationships,
                relationship_ids_cache,
                leiden_params,
                collection_id,
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
            WITH node_relationship_ids AS (
                SELECT node, relationship_ids
                FROM {self._get_table_name("community_info")}
                WHERE cluster = $1 AND collection_id = $2
            )
            SELECT DISTINCT
                e.id AS id,
                e.name AS name,
                e.description AS description
            FROM node_relationship_ids nti
            JOIN {self._get_table_name(table_name)} e ON e.name = nti.node;
        """
        entities = await self.connection_manager.fetch_query(
            QUERY, [community_number, collection_id]
        )
        entities = [Entity(**entity) for entity in entities]

        QUERY = f"""
            WITH node_relationship_ids AS (
                SELECT node, relationship_ids
                FROM {self._get_table_name("community_info")}
                WHERE cluster = $1 and collection_id = $2
            )
            SELECT DISTINCT
                t.id, t.subject, t.predicate, t.object, t.weight, t.description
            FROM node_relationship_ids nti
            JOIN {self._get_table_name("chunk_relationship")} t ON t.id = ANY(nti.relationship_ids);
        """
        relationships = await self.connection_manager.fetch_query(
            QUERY, [community_number, collection_id]
        )
        relationships = [
            Relationship(**relationship) for relationship in relationships
        ]

        return level, entities, relationships

    # async def client(self):
    #     return None

    ############################################################
    ########## Entity CRUD Operations ##########################
    ############################################################

    async def create_entities_v3(
        self, level: EntityLevel, id: UUID, entities: list[Entity]
    ) -> None:

        # TODO: check if already exists
        await self._add_objects(entities, level.table_name)

    async def update_entity(self, collection_id: UUID, entity: Entity) -> None:
        table_name = entity.level.value + "_entity"

        # check if the entity already exists
        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name(table_name)} WHERE id = $1 AND collection_id = $2
        """
        count = (
            await self.connection_manager.fetch_query(
                QUERY, [entity.id, collection_id]
            )
        )[0]["count"]

        if count == 0:
            raise R2RException("Entity does not exist", 404)

        await self._add_objects([entity], table_name)

    async def delete_entity(self, collection_id: UUID, entity: Entity) -> None:

        table_name = entity.level.value + "_entity"
        QUERY = f"""
            DELETE FROM {self._get_table_name(table_name)} WHERE id = $1 AND collection_id = $2
        """
        await self.connection_manager.execute_query(
            QUERY, [entity.id, collection_id]
        )

    ############################################################
    ########## Relationship CRUD Operations ####################
    ############################################################

    async def create_relationship(
        self, collection_id: UUID, relationship: Relationship
    ) -> None:

        # check if the relationship already exists
        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("chunk_relationship")} WHERE subject = $1 AND predicate = $2 AND object = $3 AND collection_id = $4
        """
        count = (
            await self.connection_manager.fetch_query(
                QUERY,
                [
                    relationship.subject,
                    relationship.predicate,
                    relationship.object,
                    collection_id,
                ],
            )
        )[0]["count"]

        if count > 0:
            raise R2RException("Relationship already exists", 400)

        await self._add_objects([relationship], "chunk_relationship")

    async def update_relationship(
        self, relationship_id: UUID, relationship: Relationship
    ) -> None:

        # check if relationship_id exists
        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name("chunk_relationship")} WHERE id = $1
        """
        count = (
            await self.connection_manager.fetch_query(QUERY, [relationship.id])
        )[0]["count"]

        if count == 0:
            raise R2RException("Relationship does not exist", 404)

        await self._add_objects([relationship], "chunk_relationship")

    async def delete_relationship(self, relationship_id: UUID) -> None:
        QUERY = f"""
            DELETE FROM {self._get_table_name("chunk_relationship")} WHERE id = $1
        """
        await self.connection_manager.execute_query(QUERY, [relationship_id])

    ############################################################
    ########## Community CRUD Operations #######################
    ############################################################

    async def get_communities(
        self, collection_id: UUID
    ) -> list[Community]:
        QUERY = f"""
            SELECT *c FROM {self._get_table_name("community")} WHERE collection_id = $1
        """
        return await self.connection_manager.fetch_query(
            QUERY, [collection_id]
        )

    async def check_communities_exist(
        self, collection_id: UUID, offset: int, limit: int
    ) -> list[int]:
        QUERY = f"""
            SELECT distinct community_number FROM {self._get_table_name("community")} WHERE collection_id = $1 AND community_number >= $2 AND community_number < $3
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

        # remove all relationships for these documents.
        DELETE_QUERIES = [
            f"DELETE FROM {self._get_table_name('community_info')} WHERE collection_id = $1;",
            f"DELETE FROM {self._get_table_name('community')} WHERE collection_id = $1;",
        ]

        # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
        document_ids_response = (
            await self.collection_handler.documents_in_collection(
                offset=0,
                limit=100,
                collection_id=collection_id,
            )
        )

        # This type ignore is due to insufficient typing of the documents_in_collection method
        document_ids = [doc.id for doc in document_ids_response["results"]]  # type: ignore

        # TODO: make these queries more efficient. Pass the document_ids as params.
        if cascade:
            DELETE_QUERIES += [
                f"DELETE FROM {self._get_table_name('chunk_entity')} WHERE document_id = ANY($1::uuid[]);",
                f"DELETE FROM {self._get_table_name('chunk_relationship')} WHERE document_id = ANY($1::uuid[]);",
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
            f"DELETE FROM {self._get_table_name('chunk_relationship')} WHERE document_id = $1",
            f"DELETE FROM {self._get_table_name('document_entity')} WHERE document_id = $1",
        ]

        for query in delete_queries:
            await self.connection_manager.execute_query(query, [document_id])

        # Check if this is the last document in the collection
        # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
        documents = await self.collection_handler.documents_in_collection(
            offset=0,
            limit=100,
            collection_id=collection_id,
        )
        count = documents["total_entries"]

        if count == 0:
            # If it's the last document, delete collection-related data
            collection_queries = [
                f"DELETE FROM {self._get_table_name('community_info')} WHERE collection_id = $1",
                f"DELETE FROM {self._get_table_name('community')} WHERE collection_id = $1",
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
    ):

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
        estimated_relationships = (
            int(estimated_entities[0] * 1.25),
            int(estimated_entities[1] * 1.5),
        )  # Assuming 1.25 relationships per entity on average

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

        return {
            "message": 'Ran Graph Creation Estimate (not the actual run). Note that these are estimated ranges, actual values may vary. To run the KG creation process, run `create-graph` with `--run` in the cli, or `run_type="run"` in the client.',
            "document_count": len(document_ids),
            "number_of_jobs_created": len(document_ids) + 1,
            "total_chunks": total_chunks,
            "estimated_entities": self._get_str_estimation_output(
                estimated_entities
            ),
            "estimated_relationships": self._get_str_estimation_output(
                estimated_relationships
            ),
            "estimated_llm_calls": self._get_str_estimation_output(
                estimated_llm_calls
            ),
            "estimated_total_in_out_tokens_in_millions": self._get_str_estimation_output(
                total_in_out_tokens
            ),
            "estimated_cost_in_usd": self._get_str_estimation_output(
                estimated_cost
            ),
            "estimated_total_time_in_minutes": "Depends on your API key tier. Accurate estimate coming soon. Rough estimate: "
            + self._get_str_estimation_output(total_time_in_minutes),
        }

    async def get_enrichment_estimate(
        self, collection_id: UUID, kg_enrichment_settings: KGEnrichmentSettings
    ):

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
            SELECT COUNT(*) FROM {self._get_table_name("chunk_relationship")} WHERE document_id = ANY($1);
        """
        relationship_count = (
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

        return {
            "message": 'Ran Graph Enrichment Estimate (not the actual run). Note that these are estimated ranges, actual values may vary. To run the KG enrichment process, run `enrich-graph` with `--run` in the cli, or `run_type="run"` in the client.',
            "total_entities": entity_count,
            "total_relationships": relationship_count,
            "estimated_llm_calls": self._get_str_estimation_output(
                estimated_llm_calls
            ),
            "estimated_total_in_out_tokens_in_millions": self._get_str_estimation_output(
                estimated_total_in_out_tokens_in_millions
            ),
            "estimated_cost_in_usd": self._get_str_estimation_output(
                estimated_cost
            ),
            "estimated_total_time_in_minutes": "Depends on your API key tier. Accurate estimate coming soon. Rough estimate: "
            + self._get_str_estimation_output(estimated_total_time),
        }

    async def create_vector_index(self):
        # need to implement this. Just call vector db provider's create_vector_index method.
        # this needs to be run periodically for every collection.
        raise NotImplementedError

    async def delete_relationships(self, relationship_ids: list[int]):
        # need to implement this.
        raise NotImplementedError

    async def get_schema(self):
        # somehow get the rds from the postgres db.
        raise NotImplementedError

    async def get_entities_v3(
        self,
        level: EntityLevel,
        id: Optional[UUID] = None,
        entity_names: Optional[list[str]] = None,
        entity_categories: Optional[list[str]] = None,
        attributes: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = -1,
    ):

        params: list = [id]

        if level != EntityLevel.CHUNK and entity_categories:
            raise ValueError(
                "entity_categories are only supported for chunk level entities"
            )

        filter = {
            EntityLevel.CHUNK: "chunk_ids = ANY($1)",
            EntityLevel.DOCUMENT: "document_id = $1",
            EntityLevel.COLLECTION: "collection_id = $1",
        }[level]

        if entity_names:
            filter += " AND name = ANY($2)"
            params.append(entity_names)

        if entity_categories:
            filter += " AND category = ANY($3)"
            params.append(entity_categories)

        QUERY = f"""
            SELECT * from {self._get_table_name(level.table_name)} WHERE {filter}
            OFFSET ${len(params)} LIMIT ${len(params) + 1}
        """

        params.extend([offset, limit])

        output = await self.connection_manager.fetch_query(QUERY, params)

        if attributes:
            output = [
                entity for entity in output if entity["name"] in attributes
            ]

        return output

    # TODO: deprecate this
    async def get_entities(
        self,
        offset: int,
        limit: int,
        collection_id: Optional[UUID] = None,
        entity_ids: Optional[list[str]] = None,
        entity_names: Optional[list[str]] = None,
        entity_table_name: str = "document_entity",
        extra_columns: Optional[list[str]] = None,
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
            SELECT id, name, description, extraction_ids, document_ids {", " + ", ".join(extra_columns) if extra_columns else ""}
            FROM {self._get_table_name(entity_table_name)}
            WHERE collection_id = $1
            {" AND " + " AND ".join(conditions) if conditions else ""}
            ORDER BY id
            {pagination_clause}
            """
        else:
            query = f"""
            SELECT id, name, description, extraction_ids, document_id {", " + ", ".join(extra_columns) if extra_columns else ""}
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

    async def get_relationships(
        self,
        offset: int,
        limit: int,
        collection_id: Optional[UUID] = None,
        entity_names: Optional[list[str]] = None,
        relationship_ids: Optional[list[str]] = None,
    ) -> dict:
        conditions = []
        params: list = [str(collection_id)]
        param_index = 2

        if relationship_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(relationship_ids)
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
            FROM {self._get_table_name("chunk_relationship")}
            WHERE document_id = ANY(
                SELECT document_id FROM {self._get_table_name("document_info")}
                WHERE $1 = ANY(collection_ids)
            )
            {" AND " + " AND ".join(conditions) if conditions else ""}
            ORDER BY id
            {pagination_clause}
        """

        relationships = await self.connection_manager.fetch_query(
            query, params
        )
        relationships = [
            Relationship(**relationship) for relationship in relationships
        ]
        total_entries = await self.get_relationship_count(
            collection_id=collection_id
        )

        return {"relationships": relationships, "total_entries": total_entries}

    async def structured_query(self):
        raise NotImplementedError

    async def update_extraction_prompt(self):
        raise NotImplementedError

    async def update_kg_search_prompt(self):
        raise NotImplementedError

    async def upsert_relationships(self):
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

    async def get_relationship_count(
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
            SELECT COUNT(*) FROM {self._get_table_name("chunk_relationship")}
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
            raise HTTPException(
                status_code=500,
                detail="An error occurred while fetching the deduplication estimate.",
            )
        except Exception as e:
            logger.error(
                f"Unexpected error in get_deduplication_estimate: {str(e)}"
            )
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred while fetching the deduplication estimate.",
            )
