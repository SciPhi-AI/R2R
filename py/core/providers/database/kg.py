import asyncio
import asyncpg
import json
import logging
import time

from typing import Any, AsyncGenerator, Optional, Tuple
from asyncpg.exceptions import UniqueViolationError, UndefinedTableError
from uuid import UUID, uuid4


from fastapi import HTTPException

from core.base.abstractions import (
    Community,
    Entity,
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
    DataLevel,
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEnrichmentStatus,
    KGEntityDeduplicationSettings,
    VectorQuantizationType,
)
from core.base.api.models import GraphResponse

import datetime
import json

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
        - entity: For storing document-level entities with embeddings
        - collection_entity: For storing deduplicated collection-level entities

        Each table has appropriate columns and constraints for its level.
        """
        vector_column_str = _decorate_vector_type(
            f"({self.dimension})", self.quantization_type
        )

        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("chunk_entity")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            sid SERIAL,
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
        # SID is deprecated and we will remove it in the future
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("entity")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            sid SERIAL,
            name TEXT NOT NULL,
            category TEXT,
            description TEXT NOT NULL,
            chunk_ids UUID[],
            description_embedding {vector_column_str} NOT NULL,
            document_ids UUID[],
            document_id UUID,
            graph_ids UUID[],
            created_by UUID REFERENCES {self._get_table_name("users")}(user_id),
            last_modified_by UUID REFERENCES {self._get_table_name("users")}(user_id),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            attributes JSONB
            );
        """

        await self.connection_manager.execute_query(query)

        # graph entities table
        # This is only for backwards compatibility
        # We will not use this in v3
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("collection_entity")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            sid SERIAL,
            name TEXT NOT NULL,
            description TEXT,
            chunk_ids UUID[] NOT NULL,
            document_ids UUID[] NOT NULL,
            graph_id UUID,
            collection_id UUID,
            description_embedding {vector_column_str},
            attributes JSONB
        );"""

        await self.connection_manager.execute_query(query)

    async def create(
        self,
        name: str,
        category: str,
        description: str,
        description_embedding: str,
        attributes: dict,
        auth_user: Optional[Any] = None,
    ) -> UUID:  # type: ignore
        """Create a new entity in the database.

        Args:
            name: Name of the entity
            category: Category of the entity
            description: Description of the entity
            description_embedding: Embedding of the description
            attributes: Attributes of the entity

        Returns:
            UUID of the created entity
        """

        QUERY = f"""
            INSERT INTO {self._get_table_name("entity")} (name, category, description, description_embedding, attributes, created_by, last_modified_by) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, name, category, description, created_by, last_modified_by, created_at, updated_at, attributes
        """

        output = await self.connection_manager.fetch_query(
            QUERY,
            [
                name,
                category,
                description,
                description_embedding,
                attributes,
                auth_user.id,
                auth_user.id,
            ],
        )

        return output[0]

    async def get(
        self,
        offset: int,
        limit: int,
        id: Optional[UUID] = None,
        graph_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
        entity_names: Optional[list[str]] = None,
        include_embeddings: Optional[bool] = False,
        user_id: Optional[UUID] = None,
    ):
        """Retrieve entities from the database based on various filters.

        Args:
            id: Optional UUID to filter by
            graph_id: Optional UUID to filter by
            document_id: Optional UUID to filter by
            entity_names: Optional list of entity names to filter by
            attributes: Optional list of attributes to filter by
            offset: Number of records to skip
            limit: Maximum number of records to return (-1 for no limit)

        Returns:
            List of matching Entity objects

        """

        if not graph_id and not document_id:
            raise R2RException(
                "Either graph_id or document_id must be provided.",
                400,
            )

        filters = []
        params = []

        if id:
            params = [id]
            filters.append("id = $1")
        else:
            params = []

        if entity_names:
            filters.append(f"name = ANY(${len(params)+1})")
            params.append(entity_names)

        if graph_id:
            filters.append(f"${len(params)+1} = ANY(graph_ids)")
            params.append(graph_id)
        elif user_id:
            filters.append(
                f"(graph_ids && (SELECT array_agg(id) FROM graph)) AND user_id = ${len(params)+1}"
            )
            params.append(user_id)

        if document_id:
            # user has access to the document as we have done a check earlier
            filters.append(f"${len(params)+1} = ANY(document_ids)")
            params.append(document_id)

        filters_str = " AND ".join(filters)

        # Build query with conditional LIMIT
        base_query = f"""
            SELECT * from {self._get_table_name("entity")} WHERE {filters_str}
            OFFSET ${len(params)+1}
        """

        params.append(offset)

        if limit != -1:
            base_query += f" LIMIT ${len(params)+1}"
            params.append(limit)

        QUERY = base_query

        output = await self.connection_manager.fetch_query(QUERY, params)

        output = [
            Entity(
                id=entity["id"],
                name=entity["name"],
                description=entity["description"],
                description_embedding=(
                    entity["description_embedding"]
                    if include_embeddings
                    else None
                ),
                chunk_ids=entity["chunk_ids"],
                document_ids=entity["document_ids"],
                graph_ids=entity["graph_ids"],
                attributes=entity["attributes"],
            )
            for entity in output
        ]

        filters_str = " AND ".join(filters)

        QUERY = f"""
            SELECT COUNT(*) from {self._get_table_name("entity")} WHERE {filters_str}
        """
        count = (
            await self.connection_manager.fetch_query(
                QUERY, params[: -2 + (limit == -1)]
            )
        )[0]["count"]

        if count == 0 and graph_id:
            raise R2RException(
                "No entities found in the graph, please add first",
                204,
            )

        if count == 0 and document_id:
            raise R2RException(
                "No entities found in the document, please add first",
                204,
            )

        return output, count

    async def update(
        self,
        id: UUID,
        name: Optional[str] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        description_embedding: Optional[str] = None,
        attributes: Optional[dict] = None,
        auth_user: Optional[Any] = None,
    ) -> None:
        """Update an existing entity in the database.

        Args:
            entity: Entity object containing updated data

        Raises:
            R2RException: If the entity does not exist in the database
        """

        if not auth_user.is_superuser:
            if not await self._check_permissions(id, auth_user.id):
                raise R2RException(
                    "You do not have permission to update this entity.", 403
                )
        # Build update fields based on non-null attributes
        update_fields = []
        params = []
        param_count = 1

        if name is not None:
            update_fields.append(f"name = ${param_count}")
            params.append(name)
            param_count += 1

        if category is not None:
            update_fields.append(f"category = ${param_count}")
            params.append(category)
            param_count += 1

        if description is not None:
            update_fields.append(f"description = ${param_count}")
            params.append(description)
            param_count += 1

        if description_embedding is not None:
            update_fields.append(f"description_embedding = ${param_count}")
            params.append(description_embedding)
            param_count += 1

        if attributes is not None:
            update_fields.append(f"attributes = ${param_count}")
            params.append(attributes)
            param_count += 1

        # Always update last_modified_by
        update_fields.append(f"last_modified_by = ${param_count}")
        params.append(auth_user.id)
        param_count += 1

        update_fields.append("updated_at = CURRENT_TIMESTAMP")

        # Add id as final parameter
        params.append(id)

        if not update_fields:
            raise R2RException(
                "Error updating entity. No fields provided to update.", 400
            )

        QUERY = f"""
            UPDATE {self._get_table_name("entity")}
            SET {", ".join(update_fields)}
            WHERE id = ${param_count}
            RETURNING id, name, category, description, created_by, last_modified_by, created_at, updated_at, attributes
        """
        return await self.connection_manager.fetch_query(QUERY, params)

    async def _check_permissions(
        self,
        id: UUID,
        user_id: UUID,
    ) -> bool:

        # check if the user created the entity
        QUERY = f"""
            SELECT created_by, graph_ids FROM {self._get_table_name("entity")} WHERE id = $1
        """
        created_by, document_ids, graph_ids = (
            await self.connection_manager.fetch_query(QUERY, [id])
        )

        if created_by == user_id:
            return True

        # check if the user has access to the graph, so somoene shared the graph with the user
        if graph_ids:
            QUERY = f"""
                SELECT user_ids from {self._get_table_name("graph")} WHERE id = ANY($1)
            """
            user_ids = await self.connection_manager.fetch_query(
                QUERY, graph_ids
            )
            if user_id in user_ids:
                return True

        # check if the user has access all the documents that created this entity
        # Can be made more efficient by using a single query
        has_access_to_all_documents = True
        for document_id in document_ids:
            QUERY = f"""
                SELECT c.user_ids
                FROM {self._get_table_name("document_info")} d
                JOIN {self._get_table_name("collection")} c ON c.id = ANY(d.collection_ids)
                WHERE d.document_id = $1 AND $2 = ANY(c.user_ids)
            """
            has_access = await self.connection_manager.fetch_query(
                QUERY, [document_id, user_id]
            )

            if not has_access:
                has_access_to_all_documents = False
                break

        return has_access_to_all_documents

    async def delete(self, id: UUID, auth_user: Optional[Any] = None) -> None:
        """Delete an entity from the database.

        Args:
            id: UUID of the entity to delete
        """

        if not auth_user.is_superuser:
            if not await self._check_permissions(id, auth_user.id):
                raise R2RException(
                    "You do not have permission to delete this entity.", 403
                )

        QUERY = f"""
            DELETE FROM {self._get_table_name("entity")} WHERE id = $1
        """
        return await self.connection_manager.execute_query(QUERY, [id])

    async def add_to_graph(
        self, graph_id: UUID, entity_id: UUID, auth_user: Optional[Any] = None
    ) -> None:

        if not auth_user.is_superuser:
            if not await self._check_permissions(entity_id, auth_user.id):
                raise R2RException(
                    "You do not have permission to add this entity to the graph.",
                    403,
                )

        QUERY = f"""
            UPDATE {self._get_table_name("entity")}
            SET graph_ids = CASE
                WHEN graph_ids IS NULL THEN ARRAY[$1::uuid]
                WHEN NOT ($1 = ANY(graph_ids)) THEN array_append(graph_ids, $1)
                ELSE graph_ids
            END
            WHERE id = $2
            RETURNING id, name, category, description, graph_ids, attributes
        """

        return await self.connection_manager.fetch_query(
            QUERY, [graph_id, entity_id]
        )

    async def remove_from_graph(
        self, graph_id: UUID, entity_id: UUID, auth_user: Optional[Any] = None
    ) -> None:

        if not auth_user.is_superuser:
            if not await self._check_permissions(entity_id, auth_user.id):
                raise R2RException(
                    "You do not have permission to remove this entity from the graph.",
                    403,
                )

        QUERY = f"""
            UPDATE {self._get_table_name("entity")}
            SET graph_ids = array_remove(graph_ids, $1)
            WHERE id = $2
        """
        return await self.connection_manager.execute_query(
            QUERY, [graph_id, entity_id]
        )


class PostgresRelationshipHandler(RelationshipHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.project_name: str = kwargs.get("project_name")  # type: ignore
        self.connection_manager: PostgresConnectionManager = kwargs.get("connection_manager")  # type: ignore

    async def create_tables(self) -> None:
        """Create the relationships table if it doesn't exist."""
        QUERY = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("relationship")} (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                sid SERIAL,
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
            CREATE INDEX IF NOT EXISTS relationship_subject_idx ON {self._get_table_name("relationship")} (subject);
            CREATE INDEX IF NOT EXISTS relationship_object_idx ON {self._get_table_name("relationship")} (object);
            CREATE INDEX IF NOT EXISTS relationship_predicate_idx ON {self._get_table_name("relationship")} (predicate);
            CREATE INDEX IF NOT EXISTS relationship_document_id_idx ON {self._get_table_name("relationship")} (document_id);
        """
        await self.connection_manager.execute_query(QUERY)

        QUERY = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("graph_relationship")} (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                sid SERIAL,
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
            full_table_name=self._get_table_name("relationship"),
            connection_manager=self.connection_manager,
        )

    async def get(
        self,
        id: UUID,
        level: DataLevel,
        entity_names: Optional[list[str]] = None,
        relationship_types: Optional[list[str]] = None,
        attributes: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = -1,
        relationship_id: Optional[UUID] = None,
    ):
        """Get relationships from storage by ID."""

        filter = {
            DataLevel.CHUNK: "chunk_ids = ANY($1)",
            DataLevel.DOCUMENT: "document_id = $1",
            DataLevel.GRAPH: "graph_id = $1",
        }[level]

        if level == DataLevel.DOCUMENT:
            level = DataLevel.CHUNK  # to change the table name

        params = [id]

        if relationship_id:
            filter += " AND id = $2"
            params.append(relationship_id)

            QUERY = f"""
                SELECT * FROM {self._get_table_name(level + "_relationship")} WHERE {filter}
            """
            return Relationship(
                **(await self.connection_manager.fetchrow_query(QUERY, params))
            )
        else:
            if entity_names:
                filter += " AND (subject = ANY($2) OR object = ANY($2))"
                params.append(entity_names)  # type: ignore

            if relationship_types:
                filter += " AND predicate = ANY($3)"
                params.append(relationship_types)  # type: ignore

            # Build query with conditional LIMIT
            base_query = f"""
                SELECT * FROM {self._get_table_name(level + "_relationship")}
                WHERE {filter}
                OFFSET ${len(params)+1}
            """

            params.append(offset)  # type: ignore

            if limit != -1:
                base_query += f" LIMIT ${len(params)+1}"
                params.append(limit)  # type: ignore

            QUERY = base_query

            rows = await self.connection_manager.fetch_query(QUERY, params)

            QUERY_COUNT = f"""
                SELECT COUNT(*) FROM {self._get_table_name(level + "_relationship")} WHERE {filter}
            """
            count = (
                await self.connection_manager.fetch_query(
                    QUERY_COUNT, params[:-2]
                )
            )[0]["count"]

            return [Relationship(**row) for row in rows], count  # type: ignore

    async def update(self, relationship: Relationship) -> UUID:  # type: ignore
        return await _update_object(
            object=relationship.__dict__,
            full_table_name=self._get_table_name(
                relationship.level.value + "_relationship"  # type: ignore
            ),
            connection_manager=self.connection_manager,
            id_column="id",
        )

    async def delete(
        self, level: DataLevel, id: UUID, relationship_id: UUID
    ) -> None:
        """Delete a relationship from the database."""

        if level == DataLevel.DOCUMENT:
            level = DataLevel.CHUNK

        QUERY = f"""
            DELETE FROM {self._get_table_name(level.value + "_relationship")}
            WHERE id = $1
            RETURNING id
        """
        return await self.connection_manager.fetchrow_query(
            QUERY, [relationship_id]
        )

    async def add_to_graph(
        self, graph_id: UUID, relationship_ids: list[UUID]
    ) -> None:
        QUERY = f"""
            UPDATE {self._get_table_name("graph_relationship")}
            SET graph_ids = CASE
                WHEN graph_ids IS NULL THEN ARRAY[$1]
                WHEN NOT ($1 = ANY(graph_ids)) THEN array_append(graph_ids, $1)
                ELSE graph_ids
            END
            WHERE id = ANY($2)
        """
        return await self.connection_manager.execute_query(
            QUERY, [graph_id, relationship_ids]
        )

    async def remove_from_graph(
        self,
        graph_id: UUID,
        relationship_ids: list[UUID],
        auth_user: Optional[Any] = None,
    ) -> None:

        if not auth_user.is_superuser:
            if not await self._check_permissions(
                relationship_ids, auth_user.id
            ):
                raise R2RException(
                    "You do not have permission to remove this relationship from the graph.",
                    403,
                )

        QUERY = f"""
            UPDATE {self._get_table_name("graph_relationship")}
            SET graph_ids = array_remove(graph_ids, $1)
            WHERE id = ANY($2)
        """
        return await self.connection_manager.execute_query(
            QUERY, [graph_id, relationship_ids]
        )

    async def add_to_graph(
        self,
        graph_id: UUID,
        relationship_ids: list[UUID],
        auth_user: Optional[Any] = None,
    ) -> None:

        if not auth_user.is_superuser:
            if not await self._check_permissions(
                relationship_ids, auth_user.id
            ):
                raise R2RException(
                    "You do not have permission to add this relationship to the graph.",
                    403,
                )

        QUERY = f"""
            UPDATE {self._get_table_name("graph_relationship")}
            SET graph_ids = CASE
                WHEN graph_ids IS NULL THEN ARRAY[$1]
                WHEN NOT ($1 = ANY(graph_ids)) THEN array_append(graph_ids, $1)
                ELSE graph_ids
            END
            WHERE id = ANY($2)
        """
        return await self.connection_manager.execute_query(
            QUERY, [graph_id, relationship_ids]
        )

    async def _check_permissions(
        self, relationship_ids: list[UUID], auth_user_id: UUID
    ) -> bool:
        raise NotImplementedError("This is not implemented yet.")

    async def remove_from_graph(
        self,
        graph_id: UUID,
        relationship_ids: list[UUID],
        auth_user: Optional[Any] = None,
    ) -> None:

        if not auth_user.is_superuser:
            if not await self._check_permissions(
                relationship_ids, auth_user.id
            ):
                raise R2RException(
                    "You do not have permission to remove this relationship from the graph.",
                    403,
                )

        QUERY = f"""
            UPDATE {self._get_table_name("graph_relationship")}
            SET graph_ids = array_remove(graph_ids, $1)
            WHERE id = ANY($2)
        """
        return await self.connection_manager.execute_query(
            QUERY, [graph_id, relationship_ids]
        )

    async def add_to_graph(
        self, graph_id: UUID, relationship_ids: list[UUID]
    ) -> None:
        QUERY = f"""
            UPDATE {self._get_table_name("graph_relationship")}
            SET graph_ids = CASE
                WHEN graph_ids IS NULL THEN ARRAY[$1]
                WHEN NOT ($1 = ANY(graph_ids)) THEN array_append(graph_ids, $1)
                ELSE graph_ids
            END
            WHERE id = ANY($2)
        """
        return await self.connection_manager.execute_query(
            QUERY, [graph_id, relationship_ids]
        )

    async def remove_from_graph(
        self, graph_id: UUID, relationship_ids: list[UUID]
    ) -> None:
        QUERY = f"""
            UPDATE {self._get_table_name("graph_relationship")}
            SET graph_ids = array_remove(graph_ids, $1)
            WHERE id = ANY($2)
        """
        return await self.connection_manager.execute_query(
            QUERY, [graph_id, relationship_ids]
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
        # graph_id is for backward compatibility
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
            graph_id UUID,
            collection_id UUID,
            UNIQUE (graph_id, node, cluster, level)
        );"""

        await self.connection_manager.execute_query(query)

        # communities_report table
        # collection ID is for backward compatibility
        # Avoid unnecessary complexity by making communities belong to one graph only
        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("graph_community")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            graph_id UUID,
            collection_id UUID,
            community_number INT NOT NULL,
            level INT NOT NULL,
            name TEXT NOT NULL,
            summary TEXT NOT NULL,
            findings TEXT[] NOT NULL,
            rating FLOAT NOT NULL,
            rating_explanation TEXT NOT NULL,
            embedding {vector_column_str} NOT NULL,
            attributes JSONB,
            UNIQUE (community_number, level, graph_id, collection_id)
        );"""

        await self.connection_manager.execute_query(query)

    async def create(self, communities: list[Community]) -> None:
        await _add_objects(
            objects=[community.__dict__ for community in communities],
            full_table_name=self._get_table_name("graph_community"),
            connection_manager=self.connection_manager,
        )

    async def update(self, community: Community) -> None:
        return await _update_object(
            object=community.__dict__,
            full_table_name=self._get_table_name("graph_community"),
            connection_manager=self.connection_manager,
            id_column="id",
        )

    async def delete(self, community: Community) -> None:
        return await _delete_object(
            object_id=community.id,  # type: ignore
            full_table_name=self._get_table_name("graph_community"),
            connection_manager=self.connection_manager,
        )

    async def get(
        self,
        id: UUID,
        offset: int,
        limit: int,
        community_id: Optional[UUID] = None,
    ):

        if community_id is None:
            QUERY = f"""
                SELECT * FROM {self._get_table_name("graph_community")} WHERE graph_id = $1
                OFFSET $2 LIMIT $3
            """
            params = [id, offset, limit]
            communities = [
                Community(**row)
                for row in await self.connection_manager.fetch_query(
                    QUERY, params
                )
            ]

            QUERY_COUNT = f"""
                SELECT COUNT(*) FROM {self._get_table_name("graph_community")} WHERE graph_id = $1
            """
            count = (
                await self.connection_manager.fetch_query(QUERY_COUNT, [id])
            )[0]["count"]

            return communities, count

        else:
            QUERY = f"""
                SELECT * FROM {self._get_table_name("graph_community")} WHERE graph_id = $1 AND id = $2
            """
            params = [id, community_id]
            return [
                Community(
                    **await self.connection_manager.fetchrow_query(
                        QUERY, params
                    )
                )
            ]

    async def add_to_graph(
        self,
        graph_id: UUID,
        community_ids: list[UUID],
        auth_user: Optional[Any] = None,
    ) -> None:

        if not auth_user.is_superuser:
            if not await self._check_permissions(community_ids, auth_user.id):
                raise R2RException(
                    "You do not have permission to add this community to the graph.",
                    403,
                )

        QUERY = f"""
            UPDATE {self._get_table_name("graph_community")} SET graph_id = $1 WHERE id = ANY($2)
        """
        return await self.connection_manager.execute_query(
            QUERY, [graph_id, community_ids]
        )

    async def _check_permissions(
        self, community_ids: list[UUID], auth_user_id: UUID
    ) -> bool:
        raise NotImplementedError("This is not implemented yet.")

    async def remove_from_graph(
        self,
        graph_id: UUID,
        community_ids: list[UUID],
        auth_user: Optional[Any] = None,
    ) -> None:

        if not auth_user.is_superuser:
            if not await self._check_permissions(community_ids, auth_user.id):
                raise R2RException(
                    "You do not have permission to remove this community from the graph.",
                    403,
                )

        QUERY = f"""
            UPDATE {self._get_table_name("graph_community")} SET graph_id = NULL WHERE id = ANY($1)
        """
        return await self.connection_manager.execute_query(
            QUERY, [community_ids]
        )


class PostgresGraphHandler(GraphHandler):
    """Handler for Knowledge Graph METHODS in PostgreSQL."""

    TABLE_NAME = "graph"

    def __init__(
        self,
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
                user_id UUID,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                statistics JSONB,
                attributes JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """

        await self.connection_manager.execute_query(QUERY)

        for handler in self.handlers:
            print(f"Creating tables for {handler.__class__.__name__}")
            await handler.create_tables()

    async def create(
        self,
        user_id: UUID,
        name: Optional[str] = None,
        description: str = "",
        graph_id: Optional[UUID] = None,
        status: str = "pending",
    ) -> GraphResponse:

        query = f"""
            INSERT INTO {self._get_table_name(PostgresGraphHandler.TABLE_NAME)}
            (id, user_id, name, description, status)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, user_id, name, description, status, created_at, updated_at
        """
        params = [
            graph_id or uuid4(),
            user_id,
            name,
            description,
            status,
        ]

        try:
            result = await self.connection_manager.fetchrow_query(
                query=query,
                params=params,
            )

            return GraphResponse(
                id=result["id"],
                user_id=result["user_id"],
                name=result["name"],
                description=result["description"],
                status=result["status"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
            )
        except UniqueViolationError:
            raise R2RException(
                message="Graph with this ID already exists",
                status_code=409,
            )

    # FIXME: This needs to be cleaned up.
    async def delete(self, graph_id: UUID) -> None:
        # Remove graph_id from users
        user_update_query = f"""
            UPDATE {self._get_table_name('users')}
            SET graph_ids = array_remove(graph_ids, $1)
            WHERE $1 = ANY(graph_ids)
        """
        await self.connection_manager.execute_query(
            user_update_query, [graph_id]
        )

        QUERY = f"""
            DELETE FROM {self._get_table_name("graph")} WHERE id = $1
        """
        await self.connection_manager.execute_query(QUERY, [graph_id])

        # delete all entities and relationships mapping for this graph
        QUERY = f"""
            DELETE FROM {self._get_table_name("collection_entity")} WHERE graph_id = $1
        """
        await self.connection_manager.execute_query(QUERY, [graph_id])

        QUERY = f"""
            DELETE FROM {self._get_table_name("graph_relationship")} WHERE graph_id = $1
        """
        await self.connection_manager.execute_query(QUERY, [graph_id])

        # finally update the document entity and chunk relationship tables to remove the graph_id
        QUERY = f"""
            UPDATE {self._get_table_name("entity")} SET graph_ids = array_remove(graph_ids, $1) WHERE $1 = ANY(graph_ids)
        """
        await self.connection_manager.execute_query(QUERY, [graph_id])

        QUERY = f"""
            UPDATE {self._get_table_name("relationship")} SET graph_ids = array_remove(graph_ids, $1) WHERE $1 = ANY(graph_ids)
        """
        await self.connection_manager.execute_query(QUERY, [graph_id])

    async def list_graphs(
        self,
        offset: int,
        limit: int,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_graph_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[GraphResponse] | int]:
        conditions = []
        params: list[Any] = []
        param_index = 1

        if filter_graph_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(filter_graph_ids)
            param_index += 1

        if filter_user_ids:
            conditions.append(f"user_id = ANY(${param_index})")
            params.append(filter_user_ids)
            param_index += 1

        where_clause = (
            f"WHERE {' AND '.join(conditions)}" if conditions else ""
        )

        query = f"""
            SELECT
                id, user_id, name, description, status, created_at, updated_at,
                COUNT(*) OVER() as total_entries
            FROM {self._get_table_name("graph")}
            {where_clause}
            ORDER BY created_at DESC
            OFFSET ${param_index} LIMIT ${param_index + 1}
        """

        params.extend([offset, limit])

        try:
            results = await self.connection_manager.fetch_query(query, params)
            if not results:
                return {"results": [], "total_entries": 0}

            total_entries = results[0]["total_entries"] if results else 0

            graphs = [
                GraphResponse(
                    id=row["id"],
                    user_id=row["user_id"],
                    name=row["name"],
                    description=row["description"],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in results
            ]

            return {"results": graphs, "total_entries": total_entries}
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while fetching graphs: {e}",
            )

    async def get(
        self, offset: int, limit: int, graph_id: Optional[UUID] = None
    ):

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
            count = (await self.connection_manager.fetch_query(COUNT_QUERY))[
                0
            ]["count"]

            return {
                "results": [Graph(**row) for row in ret],
                "total_entries": count,
            }

        else:
            QUERY = f"""
                SELECT * FROM {self._get_table_name("graph")} WHERE id = $1
            """

            params = [graph_id]  # type: ignore

            return {
                "results": [
                    Graph(
                        **await self.connection_manager.fetchrow_query(
                            QUERY, params
                        )
                    )
                ]
            }

    async def add_documents(
        self, id: UUID, document_ids: list[UUID], copy_data: bool = True
    ) -> bool:

        # Get count of entities for each document
        QUERY = f"""
            SELECT document_id, COUNT(*) as entity_count
            FROM {self._get_table_name("entity")}
            WHERE document_id = ANY($1) AND entity_count = 0
            GROUP BY document_id
        """
        docs_missing_entities = await self.connection_manager.fetch_query(
            QUERY, [document_ids]
        )

        if len(docs_missing_entities) > 0:
            raise R2RException(
                f"Please make sure that all documents have at least one entity before adding them to the graph.",
                400,
            )

        # get count of relationships for each document
        QUERY = f"""
            SELECT document_id, COUNT(*) as relationship_count
            FROM {self._get_table_name("relationship")}
            WHERE document_id = ANY($1)
            GROUP BY document_id
        """
        docs_missing_relationships = await self.connection_manager.fetch_query(
            QUERY, [document_ids]
        )

        if len(docs_missing_relationships) > 0:
            raise R2RException(
                f"Please make sure that all documents have at least one relationship before adding them to the graph.",
                400,
            )

        for document_id in document_ids:
            for table in ["entity", "relationship"]:
                QUERY = f"""
                    UPDATE {self._get_table_name(table)}
                    SET graph_ids = CASE
                        WHEN $1 = ANY(graph_ids) THEN graph_ids
                        ELSE array_append(graph_ids, $1)
                    END
                    WHERE document_id = $2
                """
                await self.connection_manager.execute_query(
                    QUERY, [id, document_id]
                )

        if copy_data:
            for old_table, new_table in [
                ("entity", "collection_entity"),
                ("relationship", "graph_relationship"),
            ]:
                for document_id in document_ids:
                    QUERY = f"""
                        INSERT INTO {self._get_table_name(new_table)}
                        SELECT * FROM {self._get_table_name(old_table)}
                        WHERE document_id = $1
                    """
                    await self.connection_manager.execute_query(
                        QUERY, [document_id]
                    )

        return True

    async def remove_documents(
        self, id: UUID, document_ids: list[UUID], delete_data: bool = True
    ) -> bool:
        """
        Remove all entities and relationships for this document from the graph.
        """
        for document_id in document_ids:
            for table in ["entity", "relationship"]:
                QUERY = f"""
                    UPDATE {self._get_table_name(table)}
                    SET graph_ids = array_remove(graph_ids, $1)
                    WHERE document_id = $2
                """
                await self.connection_manager.execute_query(
                    QUERY, [id, document_id]
                )

        if delete_data:
            for old_table, new_table in [
                ("entity", "collection_entity"),
                ("relationship", "graph_relationship"),
            ]:
                for document_id in document_ids:
                    QUERY = f"""
                        DELETE FROM {self._get_table_name(new_table)} WHERE document_id = $1
                    """
                    await self.connection_manager.execute_query(
                        QUERY, [document_id]
                    )

        return True

    async def add_collections(
        self, id: UUID, collection_ids: list[UUID], copy_data: bool = True
    ) -> bool:
        """
        Add all entities and relationships for this collection to the graph.
        """
        for collection_id in collection_ids:
            for table in ["entity", "relationship"]:
                QUERY = f"""
                    UPDATE {self._get_table_name(table)}
                    SET graph_ids = CASE
                        WHEN $1 = ANY(graph_ids) THEN graph_ids
                        ELSE array_append(graph_ids, $1)
                    END
                    WHERE document_id = ANY(
                        ARRAY(
                            SELECT document_id FROM {self._get_table_name("document_info")}
                            WHERE $2 = ANY(collection_ids)
                        )
                    );
                """
                await self.connection_manager.execute_query(
                    QUERY, [id, collection_id]
                )

        if copy_data:
            for old_table, new_table in [
                ("entity", "collection_entity"),
                ("relationship", "graph_relationship"),
            ]:
                for collection_id in collection_ids:
                    QUERY = f"""
                        INSERT INTO {self._get_table_name(new_table)}
                        SELECT * FROM {self._get_table_name(old_table)}
                        WHERE document_id = ANY(
                            ARRAY(SELECT document_id FROM {self._get_table_name("document_info")} WHERE $1 = ANY(collection_ids)))
                    """
                    await self.connection_manager.execute_query(
                        QUERY, [collection_id]
                    )

        return True

    async def remove_collections(
        self, id: UUID, collection_ids: list[UUID], delete_data: bool = True
    ) -> bool:
        """
        Remove all entities and relationships for this collection from the graph.
        """
        for collection_id in collection_ids:
            for table in ["entity", "relationship"]:
                QUERY = f"""
                    UPDATE {self._get_table_name(table)}
                    SET graph_ids = array_remove(graph_ids, $1)
                    WHERE document_id = ANY(
                        ARRAY(
                            SELECT document_id FROM {self._get_table_name("document_info")}
                            WHERE $2 = ANY(collection_ids)
                        )
                    )
                """
                await self.connection_manager.execute_query(
                    QUERY, [id, collection_id]
                )

        if delete_data:
            for _, new_table in [
                ("entity", "collection_entity"),
                ("relationship", "graph_relationship"),
            ]:
                for collection_id in collection_ids:
                    QUERY = f"""
                        DELETE FROM {self._get_table_name(new_table)} WHERE document_id = ANY(ARRAY(SELECT document_id FROM {self._get_table_name("document_info")} WHERE $1 = ANY(collection_ids)))
                    """
                    await self.connection_manager.execute_query(
                        QUERY, [collection_id]
                    )

        return True

    async def add_entities_v3(
        self, id: UUID, entity_ids: list[UUID], copy_data: bool = True
    ) -> bool:
        """
        Add entities to the graph.
        """
        QUERY = f"""
            UPDATE {self._get_table_name("entity")}
            SET graph_ids = CASE
                    WHEN $1 = ANY(graph_ids) THEN graph_ids
                    ELSE array_append(graph_ids, $1)
                END
            WHERE id = ANY($2)
        """

        if copy_data:
            QUERY = f"""
                INSERT INTO {self._get_table_name("collection_entity")}
                SELECT * FROM {self._get_table_name("entity")}
                WHERE id = ANY($1)
            """
            await self.connection_manager.execute_query(QUERY, [entity_ids])

        await self.connection_manager.execute_query(QUERY, [id, entity_ids])

        return True

    async def remove_entities(
        self, id: UUID, entity_ids: list[UUID], delete_data: bool = True
    ) -> bool:
        """
        Remove entities from the graph.
        """
        QUERY = f"""
            UPDATE {self._get_table_name("entity")}
            SET graph_ids = array_remove(graph_ids, $1)
            WHERE id = ANY($2)
        """
        await self.connection_manager.execute_query(QUERY, [id, entity_ids])

        if delete_data:
            QUERY = f"""
                DELETE FROM {self._get_table_name("collection_entity")} WHERE id = ANY($1)
            """
            await self.connection_manager.execute_query(QUERY, [entity_ids])

        return True

    async def add_relationships_v3(
        self, id: UUID, relationship_ids: list[UUID], copy_data: bool = True
    ) -> bool:
        """
        Add relationships to the graph.
        """
        QUERY = f"""
            UPDATE {self._get_table_name("relationship")}
            SET graph_ids = array_append(graph_ids, $1)
            WHERE id = ANY($2)
        """
        await self.connection_manager.execute_query(
            QUERY, [id, relationship_ids]
        )

        if copy_data:
            QUERY = f"""
                INSERT INTO {self._get_table_name("graph_relationship")}
                SELECT * FROM {self._get_table_name("relationship")}
                WHERE id = ANY($1)
            """
            await self.connection_manager.execute_query(
                QUERY, [relationship_ids]
            )

        return True

    async def remove_relationships(
        self, id: UUID, relationship_ids: list[UUID], delete_data: bool = True
    ) -> bool:
        """
        Remove relationships from the graph.
        """
        QUERY = f"""
            UPDATE {self._get_table_name("relationship")}
            SET graph_ids = array_remove(graph_ids, $1)
            WHERE id = ANY($2)
        """
        await self.connection_manager.execute_query(
            QUERY, [id, relationship_ids]
        )

        if delete_data:
            QUERY = f"""
                DELETE FROM {self._get_table_name("graph_relationship")} WHERE id = ANY($1)
            """
            await self.connection_manager.execute_query(
                QUERY, [relationship_ids]
            )

        return True

    async def update(
        self,
        graph_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> GraphResponse:
        """Update an existing graph."""
        update_fields = []
        params: list = []
        param_index = 1

        if name is not None:
            update_fields.append(f"name = ${param_index}")
            params.append(name)
            param_index += 1

        if description is not None:
            update_fields.append(f"description = ${param_index}")
            params.append(description)
            param_index += 1

        if not update_fields:
            raise R2RException(status_code=400, message="No fields to update")

        update_fields.append("updated_at = NOW()")
        params.append(graph_id)

        query = f"""
            UPDATE {self._get_table_name("graph")}
            SET {', '.join(update_fields)}
            WHERE id = ${param_index}
            RETURNING id, user_id, name, description, status, created_at, updated_at
        """

        try:
            result = await self.connection_manager.fetchrow_query(
                query, params
            )

            if not result:
                raise R2RException(status_code=404, message="Graph not found")

            return GraphResponse(
                id=result["id"],
                user_id=result["user_id"],
                name=result["name"],
                description=result["description"],
                status=result["status"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while updating the graph: {e}",
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
            // kg_creation_settings.chunk_merge_count
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
        self,
        collection_id: UUID | None = None,
        graph_id: UUID | None = None,
        kg_enrichment_settings: KGEnrichmentSettings = KGEnrichmentSettings(),
    ):
        """Get the estimated cost and time for enriching a KG."""
        if collection_id is not None:

            document_ids = [
                doc.id
                for doc in (
                    await self.collection_handler.documents_in_collection(collection_id, offset=0, limit=-1)  # type: ignore
                )["results"]
            ]

            # Get entity and relationship counts
            entity_count = (
                await self.connection_manager.fetch_query(
                    f"SELECT COUNT(*) FROM {self._get_table_name('entity')} WHERE document_id = ANY($1);",
                    [document_ids],
                )
            )[0]["count"]

            if not entity_count:
                raise ValueError(
                    "No entities found in the graph. Please run `create-graph` first."
                )

            relationship_count = (
                await self.connection_manager.fetch_query(
                    f"SELECT COUNT(*) FROM {self._get_table_name('relationship')} WHERE document_id = ANY($1);",
                    [document_ids],
                )
            )[0]["count"]

        else:
            entity_count = (
                await self.connection_manager.fetch_query(
                    f"SELECT COUNT(*) FROM {self._get_table_name('entity')} WHERE $1 = ANY(graph_ids);",
                    [graph_id],
                )
            )[0]["count"]

            if not entity_count:
                raise ValueError(
                    "No entities found in the graph. Please run `create-graph` first."
                )

            relationship_count = (
                await self.connection_manager.fetch_query(
                    f"SELECT COUNT(*) FROM {self._get_table_name('relationship')} WHERE $1 = ANY(graph_ids);",
                    [graph_id],
                )
            )[0]["count"]

        # Calculate estimates
        estimated_llm_calls = (entity_count // 10, entity_count // 5)
        tokens_in_millions = tuple(
            2000 * calls / 1000000 for calls in estimated_llm_calls
        )
        cost_per_million = llm_cost_per_million_tokens(
            kg_enrichment_settings.generation_config.model  # type: ignore
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
                FROM {self._get_table_name("entity")}
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
        graph_id: Optional[UUID] = None,
        entity_ids: Optional[list[str]] = None,
        entity_names: Optional[list[str]] = None,
        entity_table_name: str = "entity",
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
            SELECT sid as id, name, description, chunk_ids, document_ids, graph_id {", " + ", ".join(extra_columns) if extra_columns else ""}
            FROM {self._get_table_name(entity_table_name)}
            WHERE collection_id = $1
            {" AND " + " AND ".join(conditions) if conditions else ""}
            ORDER BY id
            {pagination_clause}
            """
        else:
            query = f"""
            SELECT sid as id, name, description, chunk_ids, document_id, graph_ids {", " + ", ".join(extra_columns) if extra_columns else ""}
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
            f"DELETE FROM {self._get_table_name('relationship')} WHERE document_id = $1",
            f"DELETE FROM {self._get_table_name('entity')} WHERE document_id = $1",
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
                f"DELETE FROM {self._get_table_name('graph_community_info')} WHERE collection_id = $1",
                f"DELETE FROM {self._get_table_name('graph_community')} WHERE collection_id = $1",
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
        table_name: str = "relationship",
    ):  # type: ignore
        """
        Upsert relationships into the relationship table. These are raw relationships extracted from the document.

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
        self,
        collection_id: UUID | None,
        graph_id: UUID | None,
        document_ids: Optional[list[UUID]] = None,
    ) -> list[Relationship]:

        logger.info(
            f"Getting all relationships for {collection_id} and {graph_id}"
        )

        if collection_id is not None:

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
                SELECT sid as id, subject, predicate, weight, object, document_id FROM {self._get_table_name("relationship")} WHERE document_id = ANY($1)
            """
            relationships = await self.connection_manager.fetch_query(
                QUERY, [document_ids]
            )

            logger.info(
                f"Got {len(relationships)} relationships for {collection_id}"
            )

        else:
            QUERY = f"""
                SELECT sid as id, subject, predicate, weight, object, document_id FROM {self._get_table_name("relationship")} WHERE $1 = ANY(graph_ids)
            """
            relationships = await self.connection_manager.fetch_query(
                QUERY, [graph_id]
            )

        logger.info(
            f"Got {len(relationships)} relationships for {collection_id or graph_id}"
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
            SELECT id, subject, predicate, object, description, chunk_ids, document_id
            FROM {self._get_table_name("relationship")}
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
            SELECT distinct community_number FROM {self._get_table_name("graph_community")} WHERE graph_id = $1 AND community_number >= $2 AND community_number < $3
        """
        community_numbers = await self.connection_manager.fetch_query(
            QUERY, [collection_id, offset, offset + limit]
        )
        return [item["community_number"] for item in community_numbers]

    async def add_community_info(
        self, communities: list[CommunityInfo]
    ) -> None:
        QUERY = f"""
            INSERT INTO {self._get_table_name("graph_community_info")} (node, cluster, parent_cluster, level, is_final_cluster, relationship_ids, collection_id, graph_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
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
                community.graph_id,
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
            FROM {self._get_table_name('graph_community')}
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
        self,
        community_number: int,
        collection_id: UUID | None,
        graph_id: UUID | None,
    ) -> Tuple[int, list[Entity], list[Relationship]]:

        QUERY = f"""
            SELECT level FROM {self._get_table_name("graph_community_info")} WHERE cluster = $1 AND (collection_id = $2 OR graph_id = $3)
            LIMIT 1
        """
        level = (
            await self.connection_manager.fetch_query(
                QUERY, [community_number, collection_id, graph_id]
            )
        )[0]["level"]

        # selecting table name based on entity level
        # check if there are any entities in the community that are not in the entity_embedding table
        query = f"""
            SELECT COUNT(*) FROM {self._get_table_name("collection_entity")} WHERE (collection_id = $1 OR graph_id = $2)
        """
        entity_count = (
            await self.connection_manager.fetch_query(
                query, [collection_id, graph_id]
            )
        )[0]["count"]
        table_name = "collection_entity" if entity_count > 0 else "entity"

        QUERY = f"""
            WITH node_relationship_ids AS (
                SELECT node, relationship_ids
                FROM {self._get_table_name("graph_community_info")}
                WHERE cluster = $1 AND (collection_id = $2 OR graph_id = $3)
            )
            SELECT DISTINCT
                e.id AS id,
                e.name AS name,
                e.description AS description
            FROM node_relationship_ids nti
            JOIN {self._get_table_name(table_name)} e ON e.name = nti.node;
        """
        entities = await self.connection_manager.fetch_query(
            QUERY, [community_number, collection_id, graph_id]
        )
        entities = [Entity(**entity) for entity in entities]

        QUERY = f"""
            WITH node_relationship_ids AS (
                SELECT node, relationship_ids
                FROM {self._get_table_name("graph_community_info")}
                WHERE cluster = $1 and (collection_id = $2 OR graph_id = $3)
            )
            SELECT DISTINCT
                t.sid as id, t.subject, t.predicate, t.object, t.weight, t.description
            FROM node_relationship_ids nti
            JOIN {self._get_table_name("relationship")} t ON t.sid = ANY(nti.relationship_ids);
        """
        relationships = await self.connection_manager.fetch_query(
            QUERY, [community_number, collection_id, graph_id]
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
            INSERT INTO {self._get_table_name("graph_community")} ({columns})
            VALUES ({placeholders})
            ON CONFLICT (community_number, level, graph_id, collection_id) DO UPDATE SET
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
            f"DELETE FROM {self._get_table_name('graph_community_info')} WHERE collection_id = $1;",
            f"DELETE FROM {self._get_table_name('graph_community')} WHERE collection_id = $1;",
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
                f"DELETE FROM {self._get_table_name('relationship')} WHERE document_id = ANY($1::uuid[]);",
                f"DELETE FROM {self._get_table_name('entity')} WHERE document_id = ANY($1::uuid[]);",
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
        collection_id: UUID | None,
        graph_id: UUID | None,
        leiden_params: dict[str, Any],
        use_community_cache: bool = False,
    ) -> int:
        """
        Leiden clustering algorithm to cluster the knowledge graph relationships into communities.

        Available parameters and defaults:
            max_cluster_size: int = 1000,
            starting_communities: Optional[dict[str, int]] = None,
            extra_forced_iterations: int = 0,
            resolution: int | float = 1.0,
            randomness: int | float = 0.001,
            use_modularity: bool = True,
            random_seed: Optional[int] = None,
            weight_attribute: str = "weight",
            is_weighted: Optional[bool] = None,
            weight_default: int| float = 1.0,
            check_directed: bool = True,
        """

        start_time = time.time()

        relationships = await self.get_all_relationships(
            collection_id, graph_id
        )

        logger.info(
            f"Got {len(relationships)} relationships for {collection_id or graph_id}"
        )

        logger.info(f"Clustering with settings: {leiden_params}")

        relationship_ids_cache = await self._get_relationship_ids_cache(
            relationships
        )

        # incremental clustering isn't enabled for v3 yet.
        # collection ID will not be null for v2
        # if not graph_id and await self._use_community_cache(  # type: ignore
        #     collection_id, relationship_ids_cache
        # ):
        #     num_communities = await self._incremental_clustering(  # type: ignore
        #         relationship_ids_cache, leiden_params, collection_id
        #     )
        # else:
        num_communities = await self._cluster_and_add_community_info(
            relationships=relationships,
            relationship_ids_cache=relationship_ids_cache,
            leiden_params=leiden_params,
            collection_id=collection_id,
            graph_id=graph_id,
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
            FROM {self._get_table_name("relationship")} t
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

        relationship_count = await self.connection_manager.fetch_query(
            f"SELECT COUNT(*) FROM {self._get_table_name('relationship')} WHERE document_id = ANY($1)",
            [document_ids],
        )

        entity_count = await self.connection_manager.fetch_query(
            f"SELECT COUNT(*) FROM {self._get_table_name('entity')} WHERE document_id = ANY($1)",
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
            "relationship_count": relationship_count[0]["count"],
            "entity_count": entity_count[0]["count"],
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
        entities_level = kwargs.get("entities_level", DataLevel.DOCUMENT)
        limit = kwargs.get("limit", 10)

        table_name = ""
        if search_type == "__Entity__":
            table_name = (
                "collection_entity"
                if entities_level == DataLevel.COLLECTION
                else "entity"
            )
        elif search_type == "__Relationship__":
            table_name = "relationship"
        elif search_type == "__Community__":
            table_name = "graph_community"
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

        logger.info(f"Graph has {len(G.nodes)} nodes and {len(G.edges)} edges")

        hierarchical_communities = await self._compute_leiden_communities(
            G, leiden_params
        )

        return hierarchical_communities

    async def _cluster_and_add_community_info(
        self,
        relationships: list[Relationship],
        relationship_ids_cache: dict[str, list[int]],
        leiden_params: dict[str, Any],
        collection_id: Optional[UUID] = None,
        graph_id: Optional[UUID] = None,
    ) -> int:

        # clear if there is any old information
        conditions = []
        if collection_id is not None:
            conditions.append("collection_id = $1")
        if graph_id is not None:
            conditions.append("graph_id = $2")

        if conditions:
            where_clause = " OR ".join(conditions)
            QUERY = f"""
                DELETE FROM {self._get_table_name("graph_community_info")} WHERE {where_clause}
            """
            await self.connection_manager.execute_query(
                QUERY, [collection_id or graph_id]
            )

            QUERY = f"""
                DELETE FROM {self._get_table_name("graph_community")} WHERE {where_clause}
            """
            await self.connection_manager.execute_query(
                QUERY, [collection_id or graph_id]
            )

        await asyncio.sleep(0.1)

        start_time = time.time()

        logger.info(
            f"Creating graph and clustering for {collection_id or graph_id}"
        )

        hierarchical_communities = await self._create_graph_and_cluster(
            relationships=relationships,
            leiden_params=leiden_params,
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
                graph_id=graph_id,
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
        self,
        collection_id: Optional[UUID] = None,
        relationship_ids_cache: dict[str, list[int]] = {},
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
            SELECT COUNT(distinct node) FROM {self._get_table_name("graph_community_info")} WHERE collection_id = $1
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
        relationship_ids_cache = dict[str, list[int | UUID]]()
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
        collection_id: Optional[UUID] = None,
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
            SELECT node, cluster, is_final_cluster FROM {self._get_table_name("graph_community_info")} WHERE collection_id = $1
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
            DELETE FROM {self._get_table_name("graph_community")} WHERE collection_id = $1 AND community_number = ANY($2)
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
        graph_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
        distinct: bool = False,
        entity_table_name: str = "entity",
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
            SELECT COUNT(*) FROM {self._get_table_name("relationship")}
            WHERE {" AND ".join(conditions)}
        """
        return (await self.connection_manager.fetch_query(QUERY, params))[0][
            "count"
        ]

    async def update_entity_descriptions(self, entities: list[Entity]):

        query = f"""
            UPDATE {self._get_table_name("collection_entity")}
            SET description = $3, description_embedding = $4
            WHERE name = $1 AND graph_id = $2
        """

        inputs = [
            (
                entity.name,
                entity.graph_id,
                entity.description,
                entity.description_embedding,
            )
            for entity in entities
        ]

        await self.connection_manager.execute_many(query, inputs)  # type: ignore

    ####################### PRIVATE  METHODS ##########################


def _json_serialize(obj):
    if isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


async def _add_objects(
    objects: list[dict],
    full_table_name: str,
    connection_manager: PostgresConnectionManager,
    conflict_columns: list[str] = [],
    exclude_attributes: list[str] = [],
) -> list[UUID]:
    """
    Bulk insert objects into the specified table using jsonb_to_recordset.
    """

    # Exclude specified attributes and prepare data
    cleaned_objects = []
    for obj in objects:
        cleaned_obj = {
            k: v
            for k, v in obj.items()
            if k not in exclude_attributes and v is not None
        }
        cleaned_objects.append(cleaned_obj)

    # Serialize the list of objects to JSON
    json_data = json.dumps(cleaned_objects, default=_json_serialize)

    # Prepare the column definitions for jsonb_to_recordset

    columns = cleaned_objects[0].keys()
    column_defs = []
    for col in columns:
        # Map Python types to PostgreSQL types
        sample_value = cleaned_objects[0][col]
        if "embedding" in col:
            pg_type = "vector"
        elif "chunk_ids" in col or "document_ids" in col or "graph_ids" in col:
            pg_type = "uuid[]"
        elif col == "id" or "_id" in col:
            pg_type = "uuid"
        elif isinstance(sample_value, str):
            pg_type = "text"
        elif isinstance(sample_value, UUID):
            pg_type = "uuid"
        elif isinstance(sample_value, (int, float)):
            pg_type = "numeric"
        elif isinstance(sample_value, list) and all(
            isinstance(x, UUID) for x in sample_value
        ):
            pg_type = "uuid[]"
        elif isinstance(sample_value, list):
            pg_type = "jsonb"
        elif isinstance(sample_value, dict):
            pg_type = "jsonb"
        elif isinstance(sample_value, bool):
            pg_type = "boolean"
        elif isinstance(sample_value, (datetime.datetime, datetime.date)):
            pg_type = "timestamp"
        else:
            raise TypeError(
                f"Unsupported data type for column '{col}': {type(sample_value)}"
            )

        column_defs.append(f"{col} {pg_type}")

    columns_str = ", ".join(columns)
    column_defs_str = ", ".join(column_defs)

    if conflict_columns:
        conflict_columns_str = ", ".join(conflict_columns)
        update_columns_str = ", ".join(
            f"{col}=EXCLUDED.{col}"
            for col in columns
            if col not in conflict_columns
        )
        on_conflict_clause = f"ON CONFLICT ({conflict_columns_str}) DO UPDATE SET {update_columns_str}"
    else:
        on_conflict_clause = ""

    QUERY = f"""
        INSERT INTO {full_table_name} ({columns_str})
        SELECT {columns_str}
        FROM jsonb_to_recordset($1::jsonb)
        AS x({column_defs_str})
        {on_conflict_clause}
        RETURNING id;
    """

    # Execute the query
    result = await connection_manager.fetch_query(QUERY, [json_data])

    # Extract and return the IDs
    return [record["id"] for record in result]


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
        RETURNING id
    """
    return await connection_manager.fetchrow_query(QUERY, [object_id])
