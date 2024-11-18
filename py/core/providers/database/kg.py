import json
import logging
import time
from typing import Any, AsyncGenerator, Optional, Tuple, Union
from uuid import UUID

import asyncpg
from asyncpg.exceptions import PostgresError, UndefinedTableError
from fastapi import HTTPException

from core.base.abstractions import (
    Community,
    Entity,
    KGExtraction,
    KGExtractionStatus,
    Graph,
    R2RException,
    Relationship,
)

from core.base.providers.database import (
    GraphHandler,
    EntityHandler,
    RelationshipHandler,
    CommunityHandler,
    CommunityInfoHandler,
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

from core.base.utils import (
    _decorate_vector_type,
    llm_cost_per_million_tokens,
    _get_str_estimation_output,
)

from .base import PostgresConnectionManager
from .collection import PostgresCollectionHandler

logger = logging.getLogger()


class PostgresEntityHandler(EntityHandler):
    """Handler for managing entities in PostgreSQL database.

    Provides methods for CRUD operations on entities at different levels (chunk, document, collection).
    Handles creation of database tables and management of entity data.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the PostgresEntityHandler.

        Args:
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments. Must include:
                - dimension: Dimension size for vector embeddings
                - quantization_type: Type of vector quantization to use
        """

        # The signature to this class isn't finalized yet, so we need to use type ignore
        self.dimension: int = kwargs.get("dimension")  # type: ignore
        self.quantization_type: VectorQuantizationType = kwargs.get("quantization_type", VectorQuantizationType.FP32)  # type: ignore

        self.project_name: str = kwargs.get("project_name")  # type: ignore
        self.connection_manager: PostgresConnectionManager = kwargs.get("connection_manager")  # type: ignore

    async def create_tables(self) -> None:
        """Create the necessary database tables for storing entities.

        Creates three tables:
        - chunk_entity: For storing chunk-level entities
        - document_entity: For storing document-level entities with embeddings
        - collection_entity: For storing deduplicated collection-level entities

        Each table has appropriate columns and constraints for its level.
        """
        vector_column_str = _decorate_vector_type(
            f"({self.dimension})", self.quantization_type
        )

        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("chunk_entity")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            sid SERIAL NOT NULL,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            chunk_ids UUID[] NOT NULL,
            document_id UUID NOT NULL,
            attributes JSONB
        );
        """
        await self.connection_manager.execute_query(query)

        # embeddings tables
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("document_entity")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            sid SERIAL NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            chunk_ids UUID[] NOT NULL,
            description_embedding {vector_column_str} NOT NULL,
            document_id UUID NOT NULL,
            graph_ids UUID[]
            );
        """

        await self.connection_manager.execute_query(query)

        # graph entities table
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("graph_entity")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            sid SERIAL NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            chunk_ids UUID[] NOT NULL,
            document_ids UUID[] NOT NULL,
            graph_id UUID NOT NULL,
            description_embedding {vector_column_str},
            attributes JSONB
        );"""

        await self.connection_manager.execute_query(query)

    async def create(self, entities: list[Entity]) -> None:
        """Create new entities in the database.

        Args:
            entities: List of Entity objects to create. All entities must be of the same level.

        Raises:
            ValueError: If entity level is not set or if entities have different levels.
        """

        # TODO: move this the router layer
        # assert that all entities are of the same level
        entity_level = entities[0].level
        if entity_level is None:
            raise ValueError("Entity level is not set")

        if not all(entity.level == entity_level for entity in entities):
            raise ValueError("All entities must be of the same level")

        return await _add_objects(
            objects=[entity.__dict__ for entity in entities],
            full_table_name=self._get_table_name(entity_level + "_entity"),
            connection_manager=self.connection_manager,
            exclude_attributes=["level"],
        )

    async def get(
        self,
        level: EntityLevel,
        id: Optional[UUID] = None,
        entity_names: Optional[list[str]] = None,
        entity_categories: Optional[list[str]] = None,
        attributes: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = -1,
    ):
        """Retrieve entities from the database based on various filters.

        Args:
            level: Level of entities to retrieve (chunk, document, or collection)
            id: Optional UUID to filter by
            entity_names: Optional list of entity names to filter by
            entity_categories: Optional list of categories (only for chunk level)
            attributes: Optional list of attributes to filter by
            offset: Number of records to skip
            limit: Maximum number of records to return (-1 for no limit)

        Returns:
            List of matching Entity objects

        Raises:
            ValueError: If entity_categories is used with non-chunk level entities
        """
        params: list = [id]

        if level != EntityLevel.CHUNK and entity_categories:
            raise ValueError(
                "entity_categories are only supported for chunk level entities"
            )

        filter = {
            EntityLevel.CHUNK: "chunk_ids = ANY($1)",
            EntityLevel.DOCUMENT: "document_id = $1",
            EntityLevel.GRAPH: "graph_id = $1",
        }[level]

        if entity_names:
            filter += " AND name = ANY($2)"
            params.append(entity_names)

        if entity_categories:
            filter += " AND category = ANY($3)"
            params.append(entity_categories)

        QUERY = f"""
            SELECT * from {self._get_table_name(level + "_entity")} WHERE {filter}
            OFFSET ${len(params)+1} LIMIT ${len(params) + 2}
        """

        params.extend([offset, limit])

        output = await self.connection_manager.fetch_query(QUERY, params)

        if attributes:
            output = [
                entity for entity in output if entity["name"] in attributes
            ]

        output = [Entity(**entity) for entity in output]

        QUERY = f"""
            SELECT COUNT(*) from {self._get_table_name(level + "_entity")} WHERE {filter}
        """
        count = (
            await self.connection_manager.fetch_query(QUERY, params[:-2])
        )[0]["count"]

        if count == 0 and level == EntityLevel.GRAPH:
            raise R2RException(
                "No entities found in the graph, please add entities and then build the graph",
                204,
            )

        return output, count

    async def update(self, entity: Entity) -> None:
        """Update an existing entity in the database.

        Args:
            entity: Entity object containing updated data

        Raises:
            R2RException: If the entity does not exist in the database
        """
        table_name = entity.level.value + "_entity"  # type: ignore

        filter = "id = $1"
        params: list[Any] = [entity.id]
        if entity.level == EntityLevel.CHUNK:
            filter += " AND chunk_ids = ANY($2)"
            params.append(entity.chunk_ids)
        elif entity.level == EntityLevel.DOCUMENT:
            filter += " AND document_id = $2"
            params.append(entity.document_id)
        elif entity.level == EntityLevel.GRAPH:
            filter += " AND graph_id = $2"
            params.append(entity.graph_id)

        # check if the entity already exists
        QUERY = f"""
            SELECT COUNT(*) FROM {self._get_table_name(table_name)} WHERE {filter}
        """
        count = (await self.connection_manager.fetch_query(QUERY, params))[0][
            "count"
        ]

        # don't override the chunk_ids
        entity.chunk_ids = None
        entity.level = None

        # get non null attributes
        non_null_attributes = [
            k for k, v in entity.to_dict().items() if v is not None
        ]

        if count == 0:
            raise R2RException("Entity does not exist", 204)

        return await _update_object(
            object=entity.__dict__,
            full_table_name=self._get_table_name(table_name),
            connection_manager=self.connection_manager,
            id_column="id",
        )

    async def delete(self, entity: Entity) -> None:
        """Delete an entity from the database.

        Args:
            entity_id: UUID of the entity to delete
            level: Level of the entity (chunk, document, or collection)
        """
        table_name = entity.level.value + "_entity"  # type: ignore
        return await _delete_object(
            object_id=entity.id,  # type: ignore
            full_table_name=self._get_table_name(table_name),
            connection_manager=self.connection_manager,
        )


class PostgresRelationshipHandler(RelationshipHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.project_name: str = kwargs.get("project_name")  # type: ignore
        self.connection_manager: PostgresConnectionManager = kwargs.get("connection_manager")  # type: ignore

    async def create_tables(self) -> None:
        """Create the relationships table if it doesn't exist."""
        QUERY = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("chunk_relationship")} (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                subject_id UUID,
                object_id UUID,
                weight FLOAT DEFAULT 1.0,
                description TEXT,
                predicate_embedding FLOAT[],
                chunk_ids UUID[],
                document_id UUID,
                graph_ids UUID[],
                attributes JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS relationship_subject_idx ON {self._get_table_name("chunk_relationship")} (subject);
            CREATE INDEX IF NOT EXISTS relationship_object_idx ON {self._get_table_name("chunk_relationship")} (object);
            CREATE INDEX IF NOT EXISTS relationship_predicate_idx ON {self._get_table_name("chunk_relationship")} (predicate);
            CREATE INDEX IF NOT EXISTS relationship_document_id_idx ON {self._get_table_name("chunk_relationship")} (document_id);
        """
        await self.connection_manager.execute_query(QUERY)
        
        QUERY = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("graph_relationship")} (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                graph_id UUID NOT NULL,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                subject_id UUID,
                object_id UUID,
                weight FLOAT DEFAULT 1.0,
                description TEXT,
                predicate_embedding FLOAT[],
                chunk_ids UUID[],
                document_id UUID,
                attributes JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS relationship_subject_idx ON {self._get_table_name("graph_relationship")} (subject);
            CREATE INDEX IF NOT EXISTS relationship_object_idx ON {self._get_table_name("graph_relationship")} (object);
            CREATE INDEX IF NOT EXISTS relationship_predicate_idx ON {self._get_table_name("graph_relationship")} (predicate);
            CREATE INDEX IF NOT EXISTS relationship_document_id_idx ON {self._get_table_name("graph_relationship")} (document_id);
        """
        await self.connection_manager.execute_query(QUERY)


    def _get_table_name(self, table: str) -> str:
        """Get the fully qualified table name."""
        return f'"{self.project_name}"."{table}"'

    async def create(self, relationships: list[Relationship]) -> None:
        """Create a new relationship in the database."""
        await _add_objects(
            objects=[relationship.__dict__ for relationship in relationships],
            full_table_name=self._get_table_name("graph_relationship"),
            connection_manager=self.connection_manager,
        )

    async def get(
        self,
        id: UUID,
        level: EntityLevel,
        entity_names: Optional[list[str]] = None,
        relationship_types: Optional[list[str]] = None,
        attributes: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = -1,
    ):
        """Get relationships from storage by ID."""

        filter = {
            EntityLevel.CHUNK: "chunk_ids = ANY($1)",
            EntityLevel.DOCUMENT: "document_id = $1",
            EntityLevel.GRAPH: "graph_id = $1",
        }[level]

        if level == EntityLevel.DOCUMENT:
            level = EntityLevel.CHUNK # to change the table name

        params = [id]

        if entity_names:
            filter += " AND (subject = ANY($2) OR object = ANY($2))"
            params.append(entity_names)  # type: ignore

        if relationship_types:
            filter += " AND predicate = ANY($3)"
            params.append(relationship_types)  # type: ignore

        QUERY = f"""
            SELECT * FROM {self._get_table_name(level + "_relationship")}
            WHERE {filter}
            OFFSET ${len(params)+1} LIMIT ${len(params) + 2}
        """

        params.extend([offset, limit])  # type: ignore
        rows = await self.connection_manager.fetch_query(QUERY, params)

        QUERY_COUNT = f"""
            SELECT COUNT(*) FROM {self._get_table_name(level + "_relationship")} WHERE {filter}
        """
        count = (
            await self.connection_manager.fetch_query(QUERY_COUNT, params[:-2])
        )[0]["count"]

        return [Relationship(**row) for row in rows], count  # type: ignore

    async def update(self, relationship: Relationship) -> None:
        return await _update_object(
            object=relationship.__dict__,
            full_table_name=self._get_table_name(relationship.level.value + "_relationship"),
            connection_manager=self.connection_manager,
            id_column="id",
        )

    async def delete(self, relationship: Relationship) -> None:
        """Delete a relationship from the database."""
        QUERY = f"""
            DELETE FROM {self._get_table_name(relationship.level.value + "_relationship")}
            WHERE id = $1
        """
        return await self.connection_manager.execute_query(
            QUERY, [relationship.id]
        )


class PostgresCommunityHandler(CommunityHandler):

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.project_name: str = kwargs.get("project_name")  # type: ignore
        self.connection_manager: PostgresConnectionManager = kwargs.get("connection_manager")  # type: ignore
        self.dimension: int = kwargs.get("dimension")  # type: ignore
        self.quantization_type: VectorQuantizationType = kwargs.get("quantization_type")  # type: ignore

    async def create_tables(self) -> None:

        vector_column_str = _decorate_vector_type(
            f"({self.dimension})", self.quantization_type
        )

        # communities table, result of the Leiden algorithm
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("graph_community_info")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            sid SERIAL,
            node TEXT NOT NULL,
            cluster INT NOT NULL,
            parent_cluster INT,
            level INT NOT NULL,
            is_final_cluster BOOLEAN NOT NULL,
            relationship_ids INT[] NOT NULL,
            graph_id UUID NOT NULL,
            UNIQUE (graph_id, cluster)
        );"""

        await self.connection_manager.execute_query(query)

        # communities_report table
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("graph_community")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            graph_id UUID NOT NULL,
            sid SERIAL,
            community_number INT NOT NULL,
            level INT NOT NULL,
            name TEXT NOT NULL,
            summary TEXT NOT NULL,
            findings TEXT[] NOT NULL,
            rating FLOAT NOT NULL,
            rating_explanation TEXT NOT NULL,
            embedding {vector_column_str} NOT NULL,
            attributes JSONB,
            UNIQUE (community_number, level, graph_id)
        );"""

        await self.connection_manager.execute_query(query)

    async def create(self, communities: list[Community]) -> None:
        await _add_objects(
            objects=[community.__dict__ for community in communities],
            full_table_name=self._get_table_name("community"),
            connection_manager=self.connection_manager,
        )

    async def update(self, community: Community) -> None:
        return await _update_object(
            object=community.__dict__,
            full_table_name=self._get_table_name("community"),
            connection_manager=self.connection_manager,
            id_column="id",
        )

    async def delete(self, community: Community) -> None:
        return await _delete_object(
            object_id=community.id,  # type: ignore
            full_table_name=self._get_table_name("community"),
            connection_manager=self.connection_manager,
        )

    async def get(self, collection_id: UUID, offset: int, limit: int):
        QUERY = f"""
            SELECT * FROM {self._get_table_name("graph_community")} WHERE collection_id = $1
            OFFSET $2 LIMIT $3
        """
        params = [collection_id, offset, limit]
        communities = [
            Community(**row)
            for row in await self.connection_manager.fetch_query(QUERY, params)
        ]

        QUERY_COUNT = f"""
            SELECT COUNT(*) FROM {self._get_table_name("graph_community")} WHERE collection_id = $1
        """
        count = (
            await self.connection_manager.fetch_query(
                QUERY_COUNT, [collection_id]
            )
        )[0]["count"]

        return communities, count


class PostgresGraphHandler(GraphHandler):
    """Handler for Knowledge Graph METHODS in PostgreSQL."""

    def __init__(
        self,
        # project_name: str,
        # connection_manager: PostgresConnectionManager,
        # collection_handler: PostgresCollectionHandler,
        # dimension: int,
        # quantization_type: VectorQuantizationType,
        *args: Any,
        **kwargs: Any,
    ) -> None:

        self.project_name: str = kwargs.get("project_name")  # type: ignore
        self.connection_manager: PostgresConnectionManager = kwargs.get("connection_manager")  # type: ignore
        self.dimension: int = kwargs.get("dimension")  # type: ignore
        self.quantization_type: VectorQuantizationType = kwargs.get("quantization_type")  # type: ignore
        self.collection_handler: PostgresCollectionHandler = kwargs.get("collection_handler")  # type: ignore

        self.entities = PostgresEntityHandler(*args, **kwargs)
        self.relationships = PostgresRelationshipHandler(*args, **kwargs)
        self.communities = PostgresCommunityHandler(*args, **kwargs)

        self.handlers = [
            self.entities,
            self.relationships,
            self.communities,
        ]

        import networkx as nx

        self.nx = nx

    async def create_tables(self) -> None:
        QUERY = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("graph")} (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                statistics JSONB,
                attributes JSONB
            );
        """

        await self.connection_manager.execute_query(QUERY)

        for handler in self.handlers:
            print(f"Creating tables for {handler.__class__.__name__}")
            await handler.create_tables()

    async def create(self, graph: Graph) -> None:
        return (await _add_objects(
            objects=[graph.__dict__],
            full_table_name=self._get_table_name("graph"),
            connection_manager=self.connection_manager,
        ))[0]['id']

    async def delete(self, graph_id: UUID, cascade: bool = False) -> None:

        if cascade:
            raise NotImplementedError("Cascade deletion not implemented. Please delete document level entities and relationships using the document delete endpoints.")

        QUERY = f"""
            DELETE FROM {self._get_table_name("graph")} WHERE id = $1
        """
        await self.connection_manager.execute_query(QUERY, [graph_id])

        # delete all entities and relationships mapping for this graph
        QUERY = f"""
            DELETE FROM {self._get_table_name("graph_entity")} WHERE graph_id = $1
        """
        await self.connection_manager.execute_query(QUERY, [graph_id])

        QUERY = f"""
            DELETE FROM {self._get_table_name("graph_relationship")} WHERE graph_id = $1
        """
        await self.connection_manager.execute_query(QUERY, [graph_id])

        # finally update the document entity and chunk relationship tables to remove the graph_id
        QUERY = f"""
            UPDATE {self._get_table_name("document_entity")} SET graph_ids = array_remove(graph_ids, $1) WHERE $1 = ANY(graph_ids)
        """
        await self.connection_manager.execute_query(QUERY, [graph_id])

        QUERY = f"""
            UPDATE {self._get_table_name("chunk_relationship")} SET graph_ids = array_remove(graph_ids, $1) WHERE $1 = ANY(graph_ids)
        """
        await self.connection_manager.execute_query(QUERY, [graph_id])

        return graph_id

    async def get(self, offset: int, limit: int, graph_id: Optional[UUID] = None):

        if graph_id is None:

            params = [offset, limit]

            QUERY = f"""
                SELECT * FROM {self._get_table_name("graph")}
                OFFSET $1 LIMIT $2
            """

            ret = await self.connection_manager.fetch_query(QUERY, params)

            COUNT_QUERY = f"""
                SELECT COUNT(*) FROM {self._get_table_name("graph")}
            """
            count = (
                await self.connection_manager.fetch_query(COUNT_QUERY)
            )[0]["count"]

            return {'results': [Graph(**row) for row in ret], 'total_entries': count}

        else:
            QUERY = f"""
                SELECT * FROM {self._get_table_name("graph")} WHERE id = $1
            """

            params = [graph_id]

            return {'results': [Graph(**await self.connection_manager.fetchrow_query(QUERY, params))]}


    async def add_document(self, graph_id: UUID, document_id: UUID) -> None:
        # add all entities and relationships for this document in the graph. look at the document_entity and chunk_relationship tables
        # also, don't add if the ID already exists
        
        for table in ["document_entity", "chunk_relationship"]:
            QUERY = f"""
                UPDATE {self._get_table_name(table)} 
                SET graph_ids = CASE 
                    WHEN $2 = ANY(graph_ids) THEN graph_ids
                    ELSE array_append(graph_ids, $2)
                END
                WHERE document_id = $1
            """
            await self.connection_manager.execute_query(QUERY, [graph_id, document_id])

    async def remove_document(self, graph_id: UUID, document_id: UUID) -> None:
        """
            Remove all entities and relationships for this document from the graph.
        """
        for table in ["document_entity", "chunk_relationship"]:
            QUERY = f"""
                UPDATE {self._get_table_name(table)} 
                SET graph_ids = array_remove(graph_ids, $2)
                WHERE document_id = $1
            """
            await self.connection_manager.execute_query(QUERY, [graph_id, document_id])

    async def add_collection(
        self, graph_id: UUID, collection_id: UUID
    ) -> None:
        """
            Add all entities and relationships for this collection to the graph.
        """
        for table in ["graph_entity", "graph_relationship"]:
            QUERY = f"""
                UPDATE {self._get_table_name(table)} 
                SET graph_ids = array_append(graph_ids, $2)
                WHERE document_id = ANY(
                    SELECT document_id FROM {self._get_table_name("document_info")}
                    WHERE $1 = ANY(collection_ids)
                )
            """
            await self.connection_manager.execute_query(QUERY, [graph_id, collection_id])

    async def remove_collection(
        self, graph_id: UUID, collection_id: UUID
    ) -> None:
        """
            Remove all entities and relationships for this collection from the graph.
        """
        for table in ["graph_entity", "graph_relationship"]:
            QUERY = f"""
                UPDATE {self._get_table_name(table)} 
                SET graph_ids = array_remove(graph_ids, $2)
                WHERE document_id = ANY(
                    SELECT document_id FROM {self._get_table_name("document_info")}
                    WHERE $1 = ANY(collection_ids)
                )
            """
            await self.connection_manager.execute_query(QUERY, [graph_id, collection_id])
            
    async def add_entities(self, graph_id: UUID, entity_ids: list[UUID]) -> None:
        """
            Add entities to the graph.
        """
        QUERY = f"""
            UPDATE {self._get_table_name("document_entity")} 
            SET graph_ids = CASE 
                WHEN $2 = ANY(graph_ids) THEN graph_ids
                ELSE array_append(graph_ids, $2)
            END
            WHERE document_id = $1
        """
        await self.connection_manager.execute_query(QUERY, [graph_id, entity_ids])
        
    async def remove_entities(self, graph_id: UUID, entity_ids: list[UUID]) -> None:
        """
            Remove entities from the graph.
        """
        QUERY = f"""
            UPDATE {self._get_table_name("document_entity")} SET graph_ids = array_remove(graph_ids, $2) WHERE document_id = $1
        """
        await self.connection_manager.execute_query(QUERY, [graph_id, entity_ids])
        
    async def add_relationships(self, graph_id: UUID, relationship_ids: list[UUID]) -> None:
        """
            Add relationships to the graph.
        """
        QUERY = f"""
            UPDATE {self._get_table_name("chunk_relationship")} SET graph_ids = array_append(graph_ids, $2) WHERE document_id = $1
        """
        await self.connection_manager.execute_query(QUERY, [graph_id, relationship_ids])
        
    async def remove_relationships(self, graph_id: UUID, relationship_ids: list[UUID]) -> None:
        """
            Remove relationships from the graph.
        """
        QUERY = f"""
            UPDATE {self._get_table_name("chunk_relationship")} SET graph_ids = array_remove(graph_ids, $2) WHERE document_id = $1
        """
        await self.connection_manager.execute_query(QUERY, [graph_id, relationship_ids])

    async def update(self, graph: Graph) -> None:
        return await _update_object(
            object=graph.__dict__,
            full_table_name=self._get_table_name("graph"),
            connection_manager=self.connection_manager,
            id_column="id",
        )

    ###### ESTIMATION METHODS ######

    async def get_creation_estimate(
        self,
        kg_creation_settings: KGCreationSettings,
        document_id: Optional[UUID] = None,
        collection_id: Optional[UUID] = None,
    ):
        """Get the estimated cost and time for creating a KG."""

        if bool(document_id) ^ bool(collection_id) is False:
            raise ValueError(
                "Exactly one of document_id or collection_id must be provided."
            )

        # todo: harmonize the document_id and id fields: postgres table contains document_id, but other places use id.

        document_ids = (
            [document_id]
            if document_id
            else [
                doc.id for doc in (await self.collection_handler.documents_in_collection(collection_id, offset=0, limit=-1))["results"]  # type: ignore
            ]
        )

        chunk_counts = await self.connection_manager.fetch_query(
            f"SELECT document_id, COUNT(*) as chunk_count FROM {self._get_table_name('vectors')} "
            f"WHERE document_id = ANY($1) GROUP BY document_id",
            [document_ids],
        )

        total_chunks = (
            sum(doc["chunk_count"] for doc in chunk_counts)
            // kg_creation_settings.extraction_merge_count
        )
        estimated_entities = (total_chunks * 10, total_chunks * 20)
        estimated_relationships = (
            int(estimated_entities[0] * 1.25),
            int(estimated_entities[1] * 1.5),
        )
        estimated_llm_calls = (
            total_chunks * 2 + estimated_entities[0],
            total_chunks * 2 + estimated_entities[1],
        )
        total_in_out_tokens = tuple(
            2000 * calls // 1000000 for calls in estimated_llm_calls
        )
        cost_per_million = llm_cost_per_million_tokens(
            kg_creation_settings.generation_config.model
        )
        estimated_cost = tuple(
            tokens * cost_per_million for tokens in total_in_out_tokens
        )
        total_time_in_minutes = tuple(
            tokens * 10 / 60 for tokens in total_in_out_tokens
        )

        return {
            "message": 'Ran Graph Creation Estimate (not the actual run). Note that these are estimated ranges, actual values may vary. To run the KG creation process, run `create-graph` with `--run` in the cli, or `run_type="run"` in the client.',
            "document_count": len(document_ids),
            "number_of_jobs_created": len(document_ids) + 1,
            "total_chunks": total_chunks,
            "estimated_entities": _get_str_estimation_output(
                estimated_entities
            ),
            "estimated_relationships": _get_str_estimation_output(
                estimated_relationships
            ),
            "estimated_llm_calls": _get_str_estimation_output(
                estimated_llm_calls
            ),
            "estimated_total_in_out_tokens_in_millions": _get_str_estimation_output(
                total_in_out_tokens
            ),
            "estimated_cost_in_usd": _get_str_estimation_output(
                estimated_cost
            ),
            "estimated_total_time_in_minutes": "Depends on your API key tier. Accurate estimate coming soon. Rough estimate: "
            + _get_str_estimation_output(total_time_in_minutes),
        }

    async def get_enrichment_estimate(
        self, collection_id: UUID, kg_enrichment_settings: KGEnrichmentSettings
    ):
        """Get the estimated cost and time for enriching a KG."""

        document_ids = [
            doc.id
            for doc in (
                await self.collection_handler.documents_in_collection(collection_id)  # type: ignore
            )["results"]
        ]

        # Get entity and relationship counts
        entity_count = (
            await self.connection_manager.fetch_query(
                f"SELECT COUNT(*) FROM {self._get_table_name('document_entity')} WHERE document_id = ANY($1);",
                [document_ids],
            )
        )[0]["count"]

        if not entity_count:
            raise ValueError(
                "No entities found in the graph. Please run `create-graph` first."
            )

        relationship_count = (
            await self.connection_manager.fetch_query(
                f"SELECT COUNT(*) FROM {self._get_table_name('chunk_relationship')} WHERE document_id = ANY($1);",
                [document_ids],
            )
        )[0]["count"]

        # Calculate estimates
        estimated_llm_calls = (entity_count // 10, entity_count // 5)
        tokens_in_millions = tuple(
            2000 * calls / 1000000 for calls in estimated_llm_calls
        )
        cost_per_million = llm_cost_per_million_tokens(
            kg_enrichment_settings.generation_config.model
        )
        estimated_cost = tuple(
            tokens * cost_per_million for tokens in tokens_in_millions
        )
        estimated_time = tuple(
            tokens * 10 / 60 for tokens in tokens_in_millions
        )

        return {
            "message": 'Ran Graph Enrichment Estimate (not the actual run). Note that these are estimated ranges, actual values may vary. To run the KG enrichment process, run `enrich-graph` with `--run` in the cli, or `run_type="run"` in the client.',
            "total_entities": entity_count,
            "total_relationships": relationship_count,
            "estimated_llm_calls": _get_str_estimation_output(
                estimated_llm_calls
            ),
            "estimated_total_in_out_tokens_in_millions": _get_str_estimation_output(
                tokens_in_millions
            ),
            "estimated_cost_in_usd": _get_str_estimation_output(
                estimated_cost
            ),
            "estimated_total_time_in_minutes": "Depends on your API key tier. Accurate estimate coming soon. Rough estimate: "
            + _get_str_estimation_output(estimated_time),
        }

    async def get_deduplication_estimate(
        self,
        collection_id: UUID,
        kg_deduplication_settings: KGEntityDeduplicationSettings,
    ):
        """Get the estimated cost and time for deduplicating entities in a KG."""
        try:
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
            tokens_in_millions = (
                estimated_llm_calls[0] * 1000 / 1000000,
                estimated_llm_calls[1] * 5000 / 1000000,
            )
            cost_per_million = llm_cost_per_million_tokens(
                kg_deduplication_settings.generation_config.model
            )
            estimated_cost = (
                tokens_in_millions[0] * cost_per_million,
                tokens_in_millions[1] * cost_per_million,
            )
            estimated_time = (
                tokens_in_millions[0] * 10 / 60,
                tokens_in_millions[1] * 10 / 60,
            )

            return {
                "message": "Ran Deduplication Estimate (not the actual run). Note that these are estimated ranges.",
                "num_entities": num_entities,
                "estimated_llm_calls": _get_str_estimation_output(
                    estimated_llm_calls
                ),
                "estimated_total_in_out_tokens_in_millions": _get_str_estimation_output(
                    tokens_in_millions
                ),
                "estimated_cost_in_usd": _get_str_estimation_output(
                    estimated_cost
                ),
                "estimated_total_time_in_minutes": _get_str_estimation_output(
                    estimated_time
                ),
            }
        except UndefinedTableError:
            raise R2RException(
                "Entity embedding table not found. Please run `create-graph` first.",
                404,
            )
        except Exception as e:
            logger.error(f"Error in get_deduplication_estimate: {str(e)}")
            raise HTTPException(500, "Error fetching deduplication estimate.")

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
            SELECT sid as id, name, description, chunk_ids, document_ids {", " + ", ".join(extra_columns) if extra_columns else ""}
            FROM {self._get_table_name(entity_table_name)}
            WHERE collection_id = $1
            {" AND " + " AND ".join(conditions) if conditions else ""}
            ORDER BY id
            {pagination_clause}
            """
        else:
            query = f"""
            SELECT sid as id, name, description, chunk_ids, document_id {", " + ", ".join(extra_columns) if extra_columns else ""}
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
            entity_dict["chunk_ids"] = (
                entity_dict["chunk_ids"]
                if entity_dict.get("chunk_ids")
                else []
            )
            entity_dict["description_embedding"] = (
                str(entity_dict["description_embedding"])
                if entity_dict.get("description_embedding")  # type: ignore
                else None
            )
            cleaned_entities.append(entity_dict)

        return await _add_objects(
            objects=cleaned_entities,
            full_table_name=self._get_table_name(table_name),
            connection_manager=self.connection_manager,
            conflict_columns=conflict_columns,
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

    ##################### RELATIONSHIP METHODS #####################

    # DEPRECATED
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
        return await _add_objects(
            objects=[ele.to_dict() for ele in relationships],
            full_table_name=self._get_table_name(table_name),
            connection_manager=self.connection_manager,
        )

    async def get_all_relationships(
        self, collection_id: UUID, document_ids: Optional[list[UUID]] = None
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
            SELECT sid as id, subject, predicate, weight, object, document_id FROM {self._get_table_name("chunk_relationship")} WHERE document_id = ANY($1)
        """
        relationships = await self.connection_manager.fetch_query(
            QUERY, [document_ids]
        )
        return [Relationship(**relationship) for relationship in relationships]

    # DEPRECATED
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
            SELECT sid as id, subject, predicate, object, description, chunk_ids, document_id
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

    ####################### COMMUNITY METHODS #######################

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
            JOIN {self._get_table_name("chunk_relationship")} t ON t.sid = ANY(nti.relationship_ids);
        """
        relationships = await self.connection_manager.fetch_query(
            QUERY, [community_number, collection_id]
        )
        relationships = [
            Relationship(**relationship) for relationship in relationships
        ]

        return level, entities, relationships

    async def add_community(self, community: Community) -> None:

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

        if (
            await self._use_community_cache(
                collection_id, relationship_ids_cache
            )
            and False
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

    ####################### MANAGEMENT METHODS #######################

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
                   (SELECT array_agg(DISTINCT x) FROM unnest(e.chunk_ids) x) AS chunk_ids,
                   e.document_id
            FROM {self._get_table_name("chunk_entity")} e
            JOIN entities_list el ON e.name = el.name
            GROUP BY e.name, e.description, e.category, e.chunk_ids, e.document_id
            ORDER BY e.name;"""

        entities_list = await self.connection_manager.fetch_query(
            QUERY1, [document_id]
        )
        entities_list = [
            Entity(
                name=entity["name"],
                description=entity["description"],
                category=entity["category"],
                chunk_ids=entity["chunk_ids"],
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
                   (SELECT array_agg(DISTINCT x) FROM unnest(t.chunk_ids) x) AS chunk_ids, t.document_id
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
                chunk_ids=relationship["chunk_ids"],
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

    ####################### ESTIMATION METHODS #######################

    ####################### GRAPH SEARCH METHODS #######################

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

    ####################### GRAPH CLUSTERING METHODS #######################

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
        relationship_ids_cache = dict[str, list[Union[int, UUID]]]()
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

        return relationship_ids_cache  # type: ignore

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

    ####################### UTILITY METHODS #######################

    async def get_existing_entity_chunk_ids(
        self, document_id: UUID
    ) -> list[str]:
        QUERY = f"""
            SELECT DISTINCT unnest(chunk_ids) AS chunk_id FROM {self._get_table_name("chunk_entity")} WHERE document_id = $1
        """
        return [
            item["chunk_id"]
            for item in await self.connection_manager.fetch_query(
                QUERY, [document_id]
            )
        ]

    async def create_vector_index(self):
        # need to implement this. Just call vector db provider's create_vector_index method.
        # this needs to be run periodically for every collection.
        raise NotImplementedError

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

    ####################### PRIVATE  METHODS ##########################


async def _add_objects(
    objects: list,
    full_table_name: str,
    connection_manager: PostgresConnectionManager,
    conflict_columns: list[str] = [],
    exclude_attributes: list[str] = [],
) -> list[UUID]:
    """
    Bulk insert objects and return their IDs.
    """
    # Get non-null attributes from the first object
    non_null_attrs = {
        k: v
        for k, v in objects[0].items()
        if v is not None and k not in exclude_attributes
    }
    columns = ", ".join(non_null_attrs.keys())

    # Create the VALUES part using unnest
    value_types = []
    value_lists = []
    for key in non_null_attrs.keys():
        values = [
            json.dumps(obj[key]) if isinstance(obj[key], (dict, list)) or key == "statistics" or key == "attributes"  # Added statistics check
            else str(obj[key]) if "embedding" in key
            else obj[key]
            for obj in objects
        ]
        value_lists.append(values)
        # Determine PostgreSQL type based on the first non-null value and column name
        sample_value = next((v for v in values if v is not None), None)
        pg_type = (
            "jsonb" if isinstance(sample_value, (dict, list)) or key == "statistics" or key == "attributes"
            else "text" if isinstance(sample_value, str)
            else "uuid[]" if isinstance(sample_value, list)
            else "timestamp" if key == "created_at" or key == "updated_at"
            else "float8"
        )
        value_types.append(pg_type)

    unnest_expr = ", ".join(f"unnest(${i+1}::{pg_type}[])" for i, pg_type in enumerate(value_types))

    if conflict_columns:
        conflict_columns_str = ", ".join(conflict_columns)
        replace_columns_str = ", ".join(
            f"{column} = EXCLUDED.{column}" for column in non_null_attrs
        )
        on_conflict_query = f"ON CONFLICT ({conflict_columns_str}) DO UPDATE SET {replace_columns_str}"
    else:
        on_conflict_query = ""

    QUERY = f"""
        INSERT INTO {full_table_name} ({columns})
        SELECT {unnest_expr}
        {on_conflict_query}
        RETURNING id;
    """

    # Execute single query and return list of IDs
    return await connection_manager.fetch_query(QUERY, value_lists)

async def _update_object(
    object: dict[str, Any],
    full_table_name: str,
    connection_manager: PostgresConnectionManager,
    id_column: str = "id",
    exclude_attributes: list[str] = [],
) -> asyncpg.Record:
    """
    Update a single object in the specified table.

    Args:
        object: Dictionary containing the fields to update
        full_table_name: Name of the table to update
        connection_manager: Database connection manager
        id_column: Name of the ID column to use in WHERE clause (default: "id")
        exclude_attributes: List of attributes to exclude from update
    """
    # Get non-null attributes, excluding the ID and any excluded attributes
    non_null_attrs = {
        k: v
        for k, v in object.items()
        if v is not None and k != id_column and k not in exclude_attributes
    }

    # Create SET clause with placeholders
    set_clause = ", ".join(
        f"{k} = ${i+1}" for i, k in enumerate(non_null_attrs.keys())
    )

    QUERY = f"""
        UPDATE {full_table_name}
        SET {set_clause}
        WHERE {id_column} = ${len(non_null_attrs) + 1}
        RETURNING id
    """

    # Prepare parameters: values for SET clause + ID value for WHERE clause
    params = [
        (
            json.dumps(v)
            if isinstance(v, dict)
            else str(v) if "embedding" in k else v
        )
        for k, v in non_null_attrs.items()
    ]
    params.append(object[id_column])

    ret = await connection_manager.fetchrow_query(QUERY, tuple(params))  # type: ignore

    return ret


async def _delete_object(
    object_id: UUID,
    full_table_name: str,
    connection_manager: PostgresConnectionManager,
):
    QUERY = f"""
        DELETE FROM {full_table_name} WHERE id = $1
    """
    return await connection_manager.execute_query(QUERY, [object_id])
