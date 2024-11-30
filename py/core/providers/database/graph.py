import asyncio
import datetime
import json
import logging
import time
from enum import Enum
from typing import Any, AsyncGenerator, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import asyncpg
from asyncpg.exceptions import UndefinedTableError, UniqueViolationError
from fastapi import HTTPException

from core.base.abstractions import (
    Community,
    CommunityInfo,
    Entity,
    Graph,
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEnrichmentStatus,
    KGEntityDeduplicationSettings,
    KGExtractionStatus,
    R2RException,
    Relationship,
    VectorQuantizationType,
)
from core.base.api.models import GraphResponse
from core.base.providers.database import (
    CommunityHandler,
    EntityHandler,
    GraphHandler,
    RelationshipHandler,
)
from core.base.utils import (
    _decorate_vector_type,
    _get_str_estimation_output,
    generate_id,
    llm_cost_per_million_tokens,
)

from .base import PostgresConnectionManager
from .collection import PostgresCollectionHandler


class StoreType(str, Enum):
    GRAPH = "graph"
    DOCUMENT = "document"


logger = logging.getLogger()


class PostgresEntityHandler(EntityHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.project_name: str = kwargs.get("project_name")  # type: ignore
        self.connection_manager: PostgresConnectionManager = kwargs.get("connection_manager")  # type: ignore
        self.dimension: int = kwargs.get("dimension")  # type: ignore
        self.quantization_type: VectorQuantizationType = kwargs.get("quantization_type")  # type: ignore

    def _get_table_name(self, table: str) -> str:
        """Get the fully qualified table name."""
        return f'"{self.project_name}"."{table}"'

    def _get_entity_table_for_store(self, store_type: StoreType) -> str:
        """Get the appropriate table name for the store type."""
        if isinstance(store_type, StoreType):
            store_type = store_type.value
        return f"{store_type}_entity"

    def _get_parent_constraint(self, store_type: StoreType) -> str:
        """Get the appropriate foreign key constraint for the store type."""
        if store_type == StoreType.GRAPH:
            return f"""
                CONSTRAINT fk_graph
                    FOREIGN KEY(parent_id)
                    REFERENCES {self._get_table_name("graph")}(id)
                    ON DELETE CASCADE
            """
        else:
            return f"""
                CONSTRAINT fk_document
                    FOREIGN KEY(parent_id)
                    REFERENCES {self._get_table_name("document_info")}(document_id)
                    ON DELETE CASCADE
            """

    async def create_tables(self) -> None:
        """Create separate tables for graph and document entities."""
        vector_column_str = _decorate_vector_type(
            f"({self.dimension})", self.quantization_type
        )

        for store_type in StoreType:
            table_name = self._get_entity_table_for_store(store_type)
            parent_constraint = self._get_parent_constraint(store_type)

            QUERY = f"""
                CREATE TABLE IF NOT EXISTS {self._get_table_name(table_name)} (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    name TEXT NOT NULL,
                    category TEXT,
                    description TEXT,
                    parent_id UUID NOT NULL,
                    description_embedding {vector_column_str},
                    chunk_ids UUID[],
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    {parent_constraint}
                );
                CREATE INDEX IF NOT EXISTS {table_name}_name_idx
                    ON {self._get_table_name(table_name)} (name);
                CREATE INDEX IF NOT EXISTS {table_name}_parent_id_idx
                    ON {self._get_table_name(table_name)} (parent_id);
                CREATE INDEX IF NOT EXISTS {table_name}_category_idx
                    ON {self._get_table_name(table_name)} (category);
            """
            await self.connection_manager.execute_query(QUERY)

    async def create(
        self,
        parent_id: UUID,
        store_type: StoreType,
        name: str,
        category: Optional[str] = None,
        description: Optional[str] = None,
        description_embedding: Optional[list[float] | str] = None,
        chunk_ids: Optional[list[UUID]] = None,
        metadata: Optional[dict[str, Any] | str] = None,
    ) -> Entity:
        """Create a new entity in the specified store."""
        table_name = self._get_entity_table_for_store(store_type)

        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                pass

        if isinstance(description_embedding, list):
            description_embedding = str(description_embedding)

        query = f"""
            INSERT INTO {self._get_table_name(table_name)}
            (name, category, description, parent_id, description_embedding, chunk_ids, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, name, category, description, parent_id, chunk_ids, metadata
        """

        params = [
            name,
            category,
            description,
            parent_id,
            description_embedding,
            chunk_ids,
            json.dumps(metadata) if metadata else None,
        ]

        result = await self.connection_manager.fetchrow_query(
            query=query,
            params=params,
        )

        return Entity(
            id=result["id"],
            name=result["name"],
            category=result["category"],
            description=result["description"],
            parent_id=result["parent_id"],
            chunk_ids=result["chunk_ids"],
            metadata=result["metadata"],
        )

    async def get(
        self,
        parent_id: UUID,
        store_type: StoreType,
        offset: int,
        limit: int,
        entity_ids: Optional[list[UUID]] = None,
        entity_names: Optional[list[str]] = None,
        include_embeddings: bool = False,
    ):
        """Retrieve entities from the specified store."""
        table_name = self._get_entity_table_for_store(store_type)

        conditions = ["parent_id = $1"]
        params: list[Any] = [parent_id]
        param_index = 2

        if entity_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(entity_ids)
            param_index += 1

        if entity_names:
            conditions.append(f"name = ANY(${param_index})")
            params.append(entity_names)
            param_index += 1

        select_fields = """
            id, name, category, description, parent_id,
            chunk_ids, metadata
        """
        if include_embeddings:
            select_fields += ", description_embedding"

        COUNT_QUERY = f"""
            SELECT COUNT(*)
            FROM {self._get_table_name(table_name)}
            WHERE {' AND '.join(conditions)}
        """

        count_params = params[: param_index - 1]
        count = (
            await self.connection_manager.fetch_query(
                COUNT_QUERY, count_params
            )
        )[0]["count"]

        QUERY = f"""
            SELECT {select_fields}
            FROM {self._get_table_name(table_name)}
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at
            OFFSET ${param_index}
        """
        params.append(offset)
        param_index += 1

        if limit != -1:
            QUERY += f" LIMIT ${param_index}"
            params.append(limit)

        rows = await self.connection_manager.fetch_query(QUERY, params)

        entities = []
        for row in rows:
            # Convert the Record to a dictionary
            entity_dict = dict(row)

            # Process metadata if it exists and is a string
            if isinstance(entity_dict["metadata"], str):
                try:
                    entity_dict["metadata"] = json.loads(
                        entity_dict["metadata"]
                    )
                except json.JSONDecodeError:
                    pass

            entities.append(Entity(**entity_dict))

        return entities, count

    async def update(
        self,
        entity_id: UUID,
        store_type: StoreType,
        name: Optional[str] = None,
        description: Optional[str] = None,
        description_embedding: Optional[list[float] | str] = None,
        category: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Entity:
        """Update an entity in the specified store."""
        table_name = self._get_entity_table_for_store(store_type)
        update_fields = []
        params: list[Any] = []
        param_index = 1

        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                pass

        if name is not None:
            update_fields.append(f"name = ${param_index}")
            params.append(name)
            param_index += 1

        if description is not None:
            update_fields.append(f"description = ${param_index}")
            params.append(description)
            param_index += 1

        if description_embedding is not None:
            update_fields.append(f"description_embedding = ${param_index}")
            params.append(description_embedding)
            param_index += 1

        if category is not None:
            update_fields.append(f"category = ${param_index}")
            params.append(category)
            param_index += 1

        if metadata is not None:
            update_fields.append(f"metadata = ${param_index}")
            params.append(json.dumps(metadata))
            param_index += 1

        if not update_fields:
            raise R2RException(status_code=400, message="No fields to update")

        update_fields.append("updated_at = NOW()")
        params.append(entity_id)

        query = f"""
            UPDATE {self._get_table_name(table_name)}
            SET {', '.join(update_fields)}
            WHERE id = ${param_index}\
            RETURNING id, name, category, description, parent_id, chunk_ids, metadata
        """
        try:
            result = await self.connection_manager.fetchrow_query(
                query=query,
                params=params,
            )

            return Entity(
                id=result["id"],
                name=result["name"],
                category=result["category"],
                description=result["description"],
                parent_id=result["parent_id"],
                chunk_ids=result["chunk_ids"],
                metadata=result["metadata"],
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while updating the entity: {e}",
            )

    async def delete(
        self,
        parent_id: UUID,
        entity_ids: Optional[list[UUID]] = None,
        store_type: StoreType = StoreType.GRAPH,
    ) -> None:
        """
        Delete entities from the specified store.
        If entity_ids is not provided, deletes all entities for the given parent_id.

        Args:
            parent_id (UUID): Parent ID (graph_id or document_id)
            entity_ids (Optional[list[UUID]]): Specific entity IDs to delete. If None, deletes all entities for parent_id
            store_type (StoreType): Type of store (graph or document)

        Returns:
            list[UUID]: List of deleted entity IDs

        Raises:
            R2RException: If specific entities were requested but not all found
        """
        table_name = self._get_entity_table_for_store(store_type)

        if entity_ids is None:
            # Delete all entities for the parent_id
            QUERY = f"""
                DELETE FROM {self._get_table_name(table_name)}
                WHERE parent_id = $1
                RETURNING id
            """
            results = await self.connection_manager.fetch_query(
                QUERY, [parent_id]
            )
        else:
            # Delete specific entities
            QUERY = f"""
                DELETE FROM {self._get_table_name(table_name)}
                WHERE id = ANY($1) AND parent_id = $2
                RETURNING id
            """
            results = await self.connection_manager.fetch_query(
                QUERY, [entity_ids, parent_id]
            )

            # Check if all requested entities were deleted
            deleted_ids = [row["id"] for row in results]
            if entity_ids and len(deleted_ids) != len(entity_ids):
                raise R2RException(
                    f"Some entities not found in {store_type} store or no permission to delete",
                    404,
                )


class PostgresRelationshipHandler(RelationshipHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.project_name: str = kwargs.get("project_name")  # type: ignore
        self.connection_manager: PostgresConnectionManager = kwargs.get("connection_manager")  # type: ignore
        self.dimension: int = kwargs.get("dimension")  # type: ignore
        self.quantization_type: VectorQuantizationType = kwargs.get("quantization_type")  # type: ignore

    def _get_table_name(self, table: str) -> str:
        """Get the fully qualified table name."""
        return f'"{self.project_name}"."{table}"'

    def _get_relationship_table_for_store(self, store_type: StoreType) -> str:
        """Get the appropriate table name for the store type."""
        if isinstance(store_type, StoreType):
            store_type = store_type.value
        return f"{store_type}_relationship"

    def _get_parent_constraint(self, store_type: StoreType) -> str:
        """Get the appropriate foreign key constraint for the store type."""
        if store_type == StoreType.GRAPH:
            return f"""
                CONSTRAINT fk_graph
                    FOREIGN KEY(parent_id)
                    REFERENCES {self._get_table_name("graph")}(id)
                    ON DELETE CASCADE
            """
        else:
            return f"""
                CONSTRAINT fk_document
                    FOREIGN KEY(parent_id)
                    REFERENCES {self._get_table_name("document_info")}(document_id)
                    ON DELETE CASCADE
            """

    async def create_tables(self) -> None:
        """Create separate tables for graph and document relationships."""
        for store_type in StoreType:
            table_name = self._get_relationship_table_for_store(store_type)
            parent_constraint = self._get_parent_constraint(store_type)
            vector_column_str = _decorate_vector_type(
                f"({self.dimension})", self.quantization_type
            )
            QUERY = f"""
                CREATE TABLE IF NOT EXISTS {self._get_table_name(table_name)} (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    description TEXT,
                    description_embedding {vector_column_str},
                    subject_id UUID,
                    object_id UUID,
                    weight FLOAT DEFAULT 1.0,
                    chunk_ids UUID[],
                    parent_id UUID NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    {parent_constraint}
                );

                CREATE INDEX IF NOT EXISTS {table_name}_subject_idx
                    ON {self._get_table_name(table_name)} (subject);
                CREATE INDEX IF NOT EXISTS {table_name}_object_idx
                    ON {self._get_table_name(table_name)} (object);
                CREATE INDEX IF NOT EXISTS {table_name}_predicate_idx
                    ON {self._get_table_name(table_name)} (predicate);
                CREATE INDEX IF NOT EXISTS {table_name}_parent_id_idx
                    ON {self._get_table_name(table_name)} (parent_id);
                CREATE INDEX IF NOT EXISTS {table_name}_subject_id_idx
                    ON {self._get_table_name(table_name)} (subject_id);
                CREATE INDEX IF NOT EXISTS {table_name}_object_id_idx
                    ON {self._get_table_name(table_name)} (object_id);
            """
            await self.connection_manager.execute_query(QUERY)

    async def create(
        self,
        subject: str,
        subject_id: UUID,
        predicate: str,
        object: str,
        object_id: UUID,
        parent_id: UUID,
        store_type: StoreType,
        description: str | None = None,
        weight: float | None = 1.0,
        chunk_ids: Optional[list[UUID]] = None,
        description_embedding: Optional[list[float] | str] = None,
        metadata: Optional[dict[str, Any] | str] = None,
    ) -> Relationship:
        """Create a new relationship in the specified store."""
        table_name = self._get_relationship_table_for_store(store_type)

        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                pass

        if isinstance(description_embedding, list):
            description_embedding = str(description_embedding)

        query = f"""
            INSERT INTO {self._get_table_name(table_name)}
            (subject, predicate, object, description, subject_id, object_id,
             weight, chunk_ids, parent_id, description_embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING id, subject, predicate, object, description, subject_id, object_id, weight, chunk_ids, parent_id, metadata
        """

        params = [
            subject,
            predicate,
            object,
            description,
            subject_id,
            object_id,
            weight,
            chunk_ids,
            parent_id,
            description_embedding,
            json.dumps(metadata) if metadata else None,
        ]

        result = await self.connection_manager.fetchrow_query(
            query=query,
            params=params,
        )

        return Relationship(
            id=result["id"],
            subject=result["subject"],
            predicate=result["predicate"],
            object=result["object"],
            description=result["description"],
            subject_id=result["subject_id"],
            object_id=result["object_id"],
            weight=result["weight"],
            chunk_ids=result["chunk_ids"],
            parent_id=result["parent_id"],
            metadata=result["metadata"],
        )

    async def get(
        self,
        parent_id: UUID,
        store_type: StoreType,
        offset: int,
        limit: int,
        relationship_ids: Optional[list[UUID]] = None,
        entity_names: Optional[list[str]] = None,
        relationship_types: Optional[list[str]] = None,
        include_metadata: bool = False,
    ):
        """
        Get relationships from the specified store.

        Args:
            parent_id: UUID of the parent (graph_id or document_id)
            store_type: Type of store (graph or document)
            offset: Number of records to skip
            limit: Maximum number of records to return (-1 for no limit)
            relationship_ids: Optional list of specific relationship IDs to retrieve
            entity_names: Optional list of entity names to filter by (matches subject or object)
            relationship_types: Optional list of relationship types (predicates) to filter by
            include_metadata: Whether to include metadata in the response

        Returns:
            Tuple of (list of relationships, total count)
        """
        table_name = self._get_relationship_table_for_store(store_type)

        conditions = ["parent_id = $1"]
        params: list[Any] = [parent_id]
        param_index = 2

        if relationship_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(relationship_ids)
            param_index += 1

        if entity_names:
            conditions.append(
                f"(subject = ANY(${param_index}) OR object = ANY(${param_index}))"
            )
            params.append(entity_names)
            param_index += 1

        if relationship_types:
            conditions.append(f"predicate = ANY(${param_index})")
            params.append(relationship_types)
            param_index += 1

        select_fields = """
            id, subject, predicate, object, description,
            subject_id, object_id, weight, chunk_ids,
            parent_id
        """
        if include_metadata:
            select_fields += ", metadata"

        # Count query
        COUNT_QUERY = f"""
            SELECT COUNT(*)
            FROM {self._get_table_name(table_name)}
            WHERE {' AND '.join(conditions)}
        """
        count_params = params[: param_index - 1]
        count = (
            await self.connection_manager.fetch_query(
                COUNT_QUERY, count_params
            )
        )[0]["count"]

        # Main query
        QUERY = f"""
            SELECT {select_fields}
            FROM {self._get_table_name(table_name)}
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at
            OFFSET ${param_index}
        """
        params.append(offset)
        param_index += 1

        if limit != -1:
            QUERY += f" LIMIT ${param_index}"
            params.append(limit)

        rows = await self.connection_manager.fetch_query(QUERY, params)

        relationships = []
        for row in rows:
            relationship_dict = dict(row)
            if include_metadata and isinstance(
                relationship_dict["metadata"], str
            ):
                try:
                    relationship_dict["metadata"] = json.loads(
                        relationship_dict["metadata"]
                    )
                except json.JSONDecodeError:
                    pass
            relationships.append(Relationship(**relationship_dict))

        return relationships, count

    async def update(
        self,
        relationship_id: UUID,
        store_type: StoreType,
        subject: Optional[str],
        subject_id: Optional[UUID],
        predicate: Optional[str],
        object: Optional[str],
        object_id: Optional[UUID],
        description: Optional[str],
        description_embedding: Optional[list[float] | str],
        weight: Optional[float],
        metadata: Optional[dict[str, Any] | str],
    ) -> Relationship:
        """Update multiple relationships in the specified store."""
        table_name = self._get_relationship_table_for_store(store_type)
        update_fields = []
        params: list = []
        param_index = 1

        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                pass

        if subject is not None:
            update_fields.append(f"subject = ${param_index}")
            params.append(subject)
            param_index += 1

        if subject_id is not None:
            update_fields.append(f"subject_id = ${param_index}")
            params.append(subject_id)
            param_index += 1

        if predicate is not None:
            update_fields.append(f"predicate = ${param_index}")
            params.append(predicate)
            param_index += 1

        if object is not None:
            update_fields.append(f"object = ${param_index}")
            params.append(object)
            param_index += 1

        if object_id is not None:
            update_fields.append(f"object_id = ${param_index}")
            params.append(object_id)
            param_index += 1

        if description is not None:
            update_fields.append(f"description = ${param_index}")
            params.append(description)
            param_index += 1

        if description_embedding is not None:
            update_fields.append(f"description_embedding = ${param_index}")
            params.append(description_embedding)
            param_index += 1

        if weight is not None:
            update_fields.append(f"weight = ${param_index}")
            params.append(weight)
            param_index += 1

        if not update_fields:
            raise R2RException(status_code=400, message="No fields to update")

        update_fields.append("updated_at = NOW()")
        params.append(relationship_id)

        query = f"""
            UPDATE {self._get_table_name(table_name)}
            SET {', '.join(update_fields)}
            WHERE id = ${param_index}
            RETURNING id, subject, predicate, object, description, subject_id, object_id, weight, chunk_ids, parent_id, metadata
        """

        try:
            result = await self.connection_manager.fetchrow_query(
                query=query,
                params=params,
            )

            return Relationship(
                id=result["id"],
                subject=result["subject"],
                predicate=result["predicate"],
                object=result["object"],
                description=result["description"],
                subject_id=result["subject_id"],
                object_id=result["object_id"],
                weight=result["weight"],
                chunk_ids=result["chunk_ids"],
                parent_id=result["parent_id"],
                metadata=result["metadata"],
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while updating the relationship: {e}",
            )

    async def delete(
        self,
        parent_id: UUID,
        relationship_ids: Optional[list[UUID]] = None,
        store_type: StoreType = StoreType.GRAPH,
    ) -> None:
        """
        Delete relationships from the specified store.
        If relationship_ids is not provided, deletes all relationships for the given parent_id.

        Args:
            parent_id: UUID of the parent (graph_id or document_id)
            relationship_ids: Optional list of specific relationship IDs to delete
            store_type: Type of store (graph or document)

        Returns:
            List of deleted relationship IDs

        Raises:
            R2RException: If specific relationships were requested but not all found
        """
        table_name = self._get_relationship_table_for_store(store_type)

        if relationship_ids is None:
            QUERY = f"""
                DELETE FROM {self._get_table_name(table_name)}
                WHERE parent_id = $1
                RETURNING id
            """
            results = await self.connection_manager.fetch_query(
                QUERY, [parent_id]
            )
        else:
            QUERY = f"""
                DELETE FROM {self._get_table_name(table_name)}
                WHERE id = ANY($1) AND parent_id = $2
                RETURNING id
            """
            results = await self.connection_manager.fetch_query(
                QUERY, [relationship_ids, parent_id]
            )

            deleted_ids = [row["id"] for row in results]
            if relationship_ids and len(deleted_ids) != len(relationship_ids):
                raise R2RException(
                    f"Some relationships not found in {store_type} store or no permission to delete",
                    404,
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
            cluster UUID NOT NULL,
            parent_cluster INT,
            level INT,
            is_final_cluster BOOLEAN NOT NULL,
            relationship_ids UUID[] NOT NULL,
            graph_id UUID,
            collection_id UUID,
            UNIQUE (graph_id, collection_id, node, cluster, level)
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
            community_id UUID,
            level INT,
            name TEXT NOT NULL,
            summary TEXT NOT NULL,
            findings TEXT[],
            rating FLOAT,
            rating_explanation TEXT,
            description_embedding {vector_column_str} NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB,
            UNIQUE (community_id, level, graph_id, collection_id)
        );"""

        await self.connection_manager.execute_query(query)

    async def create(
        self,
        parent_id: UUID,
        store_type: StoreType,
        name: str,
        summary: str,
        findings: Optional[list[str]],
        rating: Optional[float],
        rating_explanation: Optional[str],
        description_embedding: Optional[list[float] | str] = None,
    ) -> Community:
        # Do we ever want to get communities from document store?
        table_name = "graph_community"

        if isinstance(description_embedding, list):
            description_embedding = str(description_embedding)

        query = f"""
            INSERT INTO {self._get_table_name(table_name)}
            (collection_id, name, summary, findings, rating, rating_explanation, description_embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, collection_id, name, summary, findings, rating, rating_explanation, created_at, updated_at
        """

        params = [
            parent_id,
            name,
            summary,
            findings,
            rating,
            rating_explanation,
            description_embedding,
        ]

        try:
            result = await self.connection_manager.fetchrow_query(
                query=query,
                params=params,
            )

            return Community(
                id=result["id"],
                collection_id=result["collection_id"],
                name=result["name"],
                summary=result["summary"],
                findings=result["findings"],
                rating=result["rating"],
                rating_explanation=result["rating_explanation"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while creating the community: {e}",
            )

    async def update(
        self,
        community_id: UUID,
        store_type: StoreType,
        name: Optional[str] = None,
        summary: Optional[str] = None,
        summary_embedding: Optional[list[float] | str] = None,
        findings: Optional[list[str]] = None,
        rating: Optional[float] = None,
        rating_explanation: Optional[str] = None,
    ) -> Community:
        table_name = "graph_community"
        update_fields = []
        params: list[Any] = []
        param_index = 1

        if name is not None:
            update_fields.append(f"name = ${param_index}")
            params.append(name)
            param_index += 1

        if summary is not None:
            update_fields.append(f"summary = ${param_index}")
            params.append(summary)
            param_index += 1

        if summary_embedding is not None:
            update_fields.append(f"description_embedding = ${param_index}")
            params.append(summary_embedding)
            param_index += 1

        if findings is not None:
            update_fields.append(f"findings = ${param_index}")
            params.append(findings)
            param_index += 1

        if rating is not None:
            update_fields.append(f"rating = ${param_index}")
            params.append(rating)
            param_index += 1

        if rating_explanation is not None:
            update_fields.append(f"rating_explanation = ${param_index}")
            params.append(rating_explanation)
            param_index += 1

        if not update_fields:
            raise R2RException(status_code=400, message="No fields to update")

        update_fields.append("updated_at = NOW()")
        params.append(community_id)

        query = f"""
            UPDATE {self._get_table_name(table_name)}
            SET {", ".join(update_fields)}
            WHERE id = ${param_index}\
            RETURNING id, community_id, name, summary, findings, rating, rating_explanation, created_at, updated_at
        """
        try:
            result = await self.connection_manager.fetchrow_query(
                query, params
            )

            return Community(
                id=result["id"],
                community_id=result["community_id"],
                name=result["name"],
                summary=result["summary"],
                findings=result["findings"],
                rating=result["rating"],
                rating_explanation=result["rating_explanation"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while updating the community: {e}",
            )

    async def delete(
        self,
        parent_id: UUID,
        community_id: UUID,
    ) -> None:
        table_name = "graph_community"

        query = f"""
            DELETE FROM {self._get_table_name(table_name)}
            WHERE id = $1 AND graph_id = $2
        """

        params = [community_id, parent_id]

        try:
            await self.connection_manager.execute_query(query, params)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while deleting the community: {e}",
            )

    async def get(
        self,
        parent_id: UUID,
        store_type: StoreType,
        offset: int,
        limit: int,
        community_ids: Optional[list[UUID]] = None,
        community_names: Optional[list[str]] = None,
        include_embeddings: bool = False,
    ):
        """Retrieve communities from the specified store."""
        # Do we ever want to get communities from document store?
        table_name = "graph_community"

        conditions = ["collection_id = $1"]
        params: list[Any] = [parent_id]
        param_index = 2

        if community_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(community_ids)
            param_index += 1

        if community_names:
            conditions.append(f"name = ANY(${param_index})")
            params.append(community_names)
            param_index += 1

        select_fields = """
            id, community_id, name, summary, findings, rating,
            rating_explanation, level, created_at, updated_at
        """
        if include_embeddings:
            select_fields += ", description_embedding"

        COUNT_QUERY = f"""
            SELECT COUNT(*)
            FROM {self._get_table_name(table_name)}
            WHERE {' AND '.join(conditions)}
        """

        count = (
            await self.connection_manager.fetch_query(
                COUNT_QUERY, params[: param_index - 1]
            )
        )[0]["count"]

        QUERY = f"""
            SELECT {select_fields}
            FROM {self._get_table_name(table_name)}
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at
            OFFSET ${param_index}
        """
        params.append(offset)
        param_index += 1

        if limit != -1:
            QUERY += f" LIMIT ${param_index}"
            params.append(limit)

        rows = await self.connection_manager.fetch_query(QUERY, params)

        communities = []
        for row in rows:
            community_dict = dict(row)

            communities.append(Community(**community_dict))

        return communities, count


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
        self.collections_handler: PostgresCollectionHandler = kwargs.get("collections_handler")  # type: ignore

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
        """Create the graph tables with mandatory collection_id support."""
        QUERY = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("graph")} (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                collection_id UUID NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                statistics JSONB,
                document_ids UUID[],
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                CONSTRAINT fk_collection
                    FOREIGN KEY(collection_id)
                    REFERENCES {self._get_table_name("collections")}(collection_id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS graph_collection_id_idx
                ON {self._get_table_name("graph")} (collection_id);
        """

        await self.connection_manager.execute_query(QUERY)

        for handler in self.handlers:
            print(f"Creating tables for {handler.__class__.__name__}")
            await handler.create_tables()

    async def create(
        self,
        collection_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        graph_id: Optional[UUID] = None,
        status: str = "pending",
    ) -> GraphResponse:
        print("create in graph being called....")
        """Create a new graph associated with a collection."""
        graph_id = graph_id or uuid4()
        name = name or f"Graph {graph_id}"
        description = description or ""

        query = f"""
            INSERT INTO {self._get_table_name(PostgresGraphHandler.TABLE_NAME)}
            (id, collection_id, name, description, status)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, collection_id, name, description, status, created_at, updated_at, document_ids
        """
        params = [
            graph_id,
            collection_id,
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
                collection_id=result["collection_id"],
                name=result["name"],
                description=result["description"],
                status=result["status"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
                document_ids=result["document_ids"] or [],
            )
        except UniqueViolationError:
            raise R2RException(
                message="Graph with this ID already exists",
                status_code=409,
            )

    async def delete(self, graph_id: UUID) -> None:
        """
        Completely delete a graph and all associated data.

        This method:
        1. Removes graph associations from users
        2. Deletes all graph entities
        3. Deletes all graph relationships
        4. Deletes all graph communities and community info
        5. Removes the graph record itself

        Args:
            graph_id (UUID): ID of the graph to delete

        Returns:
            None

        Raises:
            R2RException: If deletion fails
        """
        try:
            # Remove graph_id from users
            user_update_query = f"""
                UPDATE {self._get_table_name('users')}
                SET graph_ids = array_remove(graph_ids, $1)
                WHERE $1 = ANY(graph_ids)
            """
            await self.connection_manager.execute_query(
                user_update_query, [graph_id]
            )

            # Delete all graph entities
            entity_delete_query = f"""
                DELETE FROM {self._get_table_name("graph_entity")}
                WHERE parent_id = $1
            """
            await self.connection_manager.execute_query(
                entity_delete_query, [graph_id]
            )

            # Delete all graph relationships
            relationship_delete_query = f"""
                DELETE FROM {self._get_table_name("graph_relationship")}
                WHERE parent_id = $1
            """
            await self.connection_manager.execute_query(
                relationship_delete_query, [graph_id]
            )

            # Delete all graph communities and community info
            community_delete_queries = [
                f"""DELETE FROM {self._get_table_name("graph_community_info")}
                    WHERE graph_id = $1""",
                f"""DELETE FROM {self._get_table_name("graph_community")}
                    WHERE graph_id = $1""",
            ]
            for query in community_delete_queries:
                await self.connection_manager.execute_query(query, [graph_id])

            # Finally delete the graph itself
            graph_delete_query = f"""
                DELETE FROM {self._get_table_name("graph")}
                WHERE id = $1
            """
            await self.connection_manager.execute_query(
                graph_delete_query, [graph_id]
            )

        except Exception as e:
            logger.error(f"Error deleting graph {graph_id}: {str(e)}")
            raise R2RException(f"Failed to delete graph: {str(e)}", 500)

    # async def delete(self, graph_id: UUID) -> None:
    #     """
    #     Completely delete a graph and all associated data.

    #     This method:
    #     1. Removes graph associations from users
    #     2. Deletes all graph entities
    #     3. Deletes all graph relationships
    #     4. Deletes all graph communities and community info
    #     5. Removes the graph record itself

    #     Args:
    #         graph_id (UUID): ID of the graph to delete

    #     Returns:
    #         None

    #     Raises:
    #         R2RException: If deletion fails
    #     """
    #     try:
    #         # Start transaction to ensure atomic deletion
    #         # Remove graph_id from users
    #         user_update_query = f"""
    #             UPDATE {self._get_table_name('users')}
    #             SET graph_ids = array_remove(graph_ids, $1)
    #             WHERE $1 = ANY(graph_ids)
    #         """
    #         await self.connection_manager.execute_query(user_update_query, graph_id)

    #         # Delete all graph entities
    #         entity_delete_query = f"""
    #             DELETE FROM {self._get_table_name("graph_entity")}
    #             WHERE parent_id = $1
    #         """
    #         await self.connection_manager.execute_query.execute(entity_delete_query, graph_id)

    #         # Delete all graph relationships
    #         relationship_delete_query = f"""
    #             DELETE FROM {self._get_table_name("graph_relationship")}
    #             WHERE parent_id = $1
    #         """
    #         await self.connection_manager.execute_query.execute(relationship_delete_query, graph_id)

    #         # Delete all graph communities and community info
    #         community_delete_queries = [
    #             f"""DELETE FROM {self._get_table_name("graph_community_info")}
    #             WHERE graph_id = $1""",
    #             f"""DELETE FROM {self._get_table_name("graph_community")}
    #             WHERE graph_id = $1""",
    #         ]
    #         for query in community_delete_queries:
    #             await self.connection_manager.execute_query.execute(query, graph_id)

    #         # Finally delete the graph itself
    #         graph_delete_query = f"""
    #             DELETE FROM {self._get_table_name("graph")}
    #             WHERE id = $1
    #         """
    #         await self.connection_manager.execute_query.execute(graph_delete_query, graph_id)

    #     except Exception as e:
    #         logger.error(f"Error deleting graph {graph_id}: {str(e)}")
    #         raise R2RException(f"Failed to delete graph: {str(e)}", 500)

    async def list_graphs(
        self,
        offset: int,
        limit: int,
        # filter_user_ids: Optional[list[UUID]] = None,
        filter_graph_ids: Optional[list[UUID]] = None,
        filter_collection_id: Optional[UUID] = None,
    ) -> dict[str, list[GraphResponse] | int]:
        conditions = []
        params: list[Any] = []
        param_index = 1

        if filter_graph_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(filter_graph_ids)
            param_index += 1

        # if filter_user_ids:
        #     conditions.append(f"user_id = ANY(${param_index})")
        #     params.append(filter_user_ids)
        #     param_index += 1

        if filter_collection_id:
            conditions.append(f"collection_id = ${param_index}")
            params.append(filter_collection_id)
            param_index += 1

        where_clause = (
            f"WHERE {' AND '.join(conditions)}" if conditions else ""
        )

        query = f"""
            WITH RankedGraphs AS (
                SELECT
                    id, collection_id, name, description, status, created_at, updated_at, document_ids,
                    COUNT(*) OVER() as total_entries,
                    ROW_NUMBER() OVER (PARTITION BY collection_id ORDER BY created_at DESC) as rn
                FROM {self._get_table_name("graph")}
                {where_clause}
            )
            SELECT * FROM RankedGraphs
            WHERE rn = 1
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
                    document_ids=row["document_ids"] or [],
                    name=row["name"],
                    collection_id=row["collection_id"],
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

    async def add_documents(self, id: UUID, document_ids: list[UUID]) -> bool:
        """
        Add documents to the graph by copying their entities and relationships.
        """
        # Copy entities from document_entity to graph_entity
        ENTITY_COPY_QUERY = f"""
            INSERT INTO {self._get_table_name("graph_entity")} (
                name, category, description, parent_id, description_embedding,
                chunk_ids, metadata
            )
            SELECT
                name, category, description, $1, description_embedding,
                chunk_ids, metadata
            FROM {self._get_table_name("document_entity")}
            WHERE parent_id = ANY($2)
        """
        await self.connection_manager.execute_query(
            ENTITY_COPY_QUERY, [id, document_ids]
        )

        # Copy relationships from document_relationship to graph_relationship
        RELATIONSHIP_COPY_QUERY = f"""
            INSERT INTO {self._get_table_name("graph_relationship")} (
                subject, predicate, object, description, subject_id, object_id,
                weight, chunk_ids, parent_id, metadata, description_embedding
            )
            SELECT
                subject, predicate, object, description, subject_id, object_id,
                weight, chunk_ids, $1, metadata, description_embedding
            FROM {self._get_table_name("document_relationship")}
            WHERE parent_id = ANY($2)
        """
        await self.connection_manager.execute_query(
            RELATIONSHIP_COPY_QUERY, [id, document_ids]
        )

        # Add document_ids to the graph
        UPDATE_GRAPH_QUERY = f"""
            UPDATE {self._get_table_name("graph")}
            SET document_ids = array_cat(
                CASE
                    WHEN document_ids IS NULL THEN ARRAY[]::uuid[]
                    ELSE document_ids
                END,
                $2::uuid[]
            )
            WHERE id = $1
        """
        await self.connection_manager.execute_query(
            UPDATE_GRAPH_QUERY, [id, document_ids]
        )

        return True

    async def remove_documents(
        self, id: UUID, document_ids: list[UUID]
    ) -> bool:
        """
        Remove documents from the graph by:
        1. Removing document_ids from the graph
        2. Deleting copied entities and relationships associated with those documents

        Args:
            id (UUID): Graph ID
            document_ids (list[UUID]): List of document IDs to remove

        Returns:
            bool: Success status
        """
        # Remove document_ids from the graph using array_remove with unnest
        UPDATE_GRAPH_QUERY = f"""
            UPDATE {self._get_table_name("graph")}
            SET document_ids = (
                SELECT array_agg(x)
                FROM unnest(document_ids) x
                WHERE x != ALL($2::uuid[])
            )
            WHERE id = $1
        """

        await self.connection_manager.execute_query(
            UPDATE_GRAPH_QUERY, [id, document_ids]
        )

        # Get entities to delete - modifying query to better match entities from document
        ENTITY_IDS_QUERY = f"""
            SELECT ge.id
            FROM {self._get_table_name("graph_entity")} ge
            JOIN {self._get_table_name("document_entity")} de
            ON ge.name = de.name
            WHERE ge.parent_id = $1
            AND de.parent_id = ANY($2)
        """
        entity_results = await self.connection_manager.fetch_query(
            ENTITY_IDS_QUERY, [id, document_ids]
        )
        entity_ids = [row["id"] for row in entity_results]
        print("entity_ids = ", entity_ids)

        # Get relationships to delete - modifying query to better match relationships from document
        RELATIONSHIP_IDS_QUERY = f"""
            SELECT gr.id
            FROM {self._get_table_name("graph_relationship")} gr
            JOIN {self._get_table_name("document_relationship")} dr
            ON gr.subject = dr.subject
            AND gr.predicate = dr.predicate
            AND gr.object = dr.object
            WHERE gr.parent_id = $1
            AND dr.parent_id = ANY($2)
        """
        relationship_results = await self.connection_manager.fetch_query(
            RELATIONSHIP_IDS_QUERY, [id, document_ids]
        )
        relationship_ids = [row["id"] for row in relationship_results]
        print("relationship_ids = ", relationship_ids)

        # Delete entities
        if entity_ids:
            DELETE_ENTITIES_QUERY = f"""
                DELETE FROM {self._get_table_name("graph_entity")}
                WHERE id = ANY($1)
            """
            await self.connection_manager.execute_query(
                DELETE_ENTITIES_QUERY, [entity_ids]
            )

        # Delete relationships
        if relationship_ids:
            DELETE_RELATIONSHIPS_QUERY = f"""
                DELETE FROM {self._get_table_name("graph_relationship")}
                WHERE id = ANY($1)
            """
            await self.connection_manager.execute_query(
                DELETE_RELATIONSHIPS_QUERY, [relationship_ids]
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
                ("entity", "graph_entity"),
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
                ("entity", "graph_entity"),
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
                INSERT INTO {self._get_table_name("graph_entity")}
                SELECT * FROM {self._get_table_name("entity")}
                WHERE id = ANY($1)
            """
            await self.connection_manager.execute_query(QUERY, [entity_ids])

        await self.connection_manager.execute_query(QUERY, [id, entity_ids])

        return True

    # async def remove_entities(
    #     self, id: UUID, entity_ids: list[UUID]
    # ) -> bool:
    #     """
    #     Remove entities from the graph.
    #     """
    #     QUERY = f"""
    #         UPDATE {self._get_table_name("graph_entity")}
    #         SET graph_ids = array_remove(graph_ids, $1)
    #         WHERE id = ANY($2)
    #     """
    #     await self.connection_manager.execute_query(QUERY, [id, entity_ids])

    #     # QUERY = f"""
    #     #     DELETE FROM {self._get_table_name("graph_entity")} WHERE id = ANY($1)
    #     # """
    #     # await self.connection_manager.execute_query(QUERY, [entity_ids])

    #     return True

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
            RETURNING id, name, description, status, created_at, updated_at, collection_id, document_ids
        """

        try:
            result = await self.connection_manager.fetchrow_query(
                query, params
            )

            if not result:
                raise R2RException(status_code=404, message="Graph not found")

            return GraphResponse(
                id=result["id"],
                collection_id=result["collection_id"],
                name=result["name"],
                description=result["description"],
                status=result["status"],
                created_at=result["created_at"],
                document_ids=result["document_ids"] or [],
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
                doc.id for doc in (await self.collections_handler.documents_in_collection(collection_id, offset=0, limit=-1))["results"]  # type: ignore
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
            "message": 'Ran Graph Creation Estimate (not the actual run). Note that these are estimated ranges, actual values may vary. To run the KG creation process, run `extract-triples` with `--run` in the cli, or `run_type="run"` in the client.',
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
                    await self.collections_handler.documents_in_collection(collection_id, offset=0, limit=-1)  # type: ignore
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
                    "No entities found in the graph. Please run `extract-triples` first."
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
                    "No entities found in the graph. Please run `extract-triples` first."
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
            "message": 'Ran Graph Enrichment Estimate (not the actual run). Note that these are estimated ranges, actual values may vary. To run the KG enrichment process, run `build-communities` with `--run` in the cli, or `run_type="run"` in the client.',
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
                "Entity embedding table not found. Please run `extract-triples` first.",
                404,
            )
        except Exception as e:
            logger.error(f"Error in get_deduplication_estimate: {str(e)}")
            raise HTTPException(500, "Error fetching deduplication estimate.")

    async def get_entities(
        self,
        parent_id: UUID,
        offset: int,
        limit: int,
        entity_ids: Optional[list[UUID]] = None,
        entity_names: Optional[list[str]] = None,
        include_embeddings: bool = False,
    ) -> tuple[list[Entity], int]:
        """
        Get entities for a graph.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return (-1 for no limit)
            parent_id: UUID of the collection
            entity_ids: Optional list of entity IDs to filter by
            entity_names: Optional list of entity names to filter by
            include_embeddings: Whether to include embeddings in the response

        Returns:
            Tuple of (list of entities, total count)
        """
        conditions = ["parent_id = $1"]
        params: list[Any] = [parent_id]
        param_index = 2

        if entity_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(entity_ids)
            param_index += 1

        if entity_names:
            conditions.append(f"name = ANY(${param_index})")
            params.append(entity_names)
            param_index += 1

        # Count query - uses the same conditions but without offset/limit
        COUNT_QUERY = f"""
            SELECT COUNT(*)
            FROM {self._get_table_name("graph_entity")}
            WHERE {' AND '.join(conditions)}
        """
        count = (
            await self.connection_manager.fetch_query(COUNT_QUERY, params)
        )[0]["count"]

        # Define base columns to select
        select_fields = """
            id, name, category, description, parent_id,
            chunk_ids, metadata
        """
        if include_embeddings:
            select_fields += ", description_embedding"

        # Main query for fetching entities with pagination
        QUERY = f"""
            SELECT {select_fields}
            FROM {self._get_table_name("graph_entity")}
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at
            OFFSET ${param_index}
        """
        params.append(offset)
        param_index += 1

        if limit != -1:
            QUERY += f" LIMIT ${param_index}"
            params.append(limit)

        rows = await self.connection_manager.fetch_query(QUERY, params)

        entities = []
        for row in rows:
            # # Parse JSON metadata if it's a string
            # if isinstance(row["metadata"], str):
            #     try:
            #         row["metadata"] = json.loads(row["metadata"])
            #     except json.JSONDecodeError:
            #         pass
            # entities.append(Entity(**row))
            entity_dict = dict(row)
            if isinstance(entity_dict["metadata"], str):
                try:
                    entity_dict["metadata"] = json.loads(
                        entity_dict["metadata"]
                    )
                except json.JSONDecodeError:
                    pass
            entities.append(Entity(**entity_dict))

        return entities, count

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
            SELECT graph_cluster_status FROM {self._get_table_name("collections")} WHERE collection_id = $1
        """
        status = (
            await self.connection_manager.fetch_query(QUERY, [collection_id])
        )[0]["graph_cluster_status"]
        if status == KGExtractionStatus.PROCESSING.value:
            return

        # Execute separate DELETE queries
        delete_queries = [
            f"DELETE FROM {self._get_table_name('relationship')} WHERE document_id = $1",
            f"DELETE FROM {self._get_table_name('entity')} WHERE document_id = $1",
        ]

        for query in delete_queries:
            await self.connection_manager.execute_query(query, [document_id])

        # Check if this is the last document in the collection
        # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
        documents = await self.collections_handler.documents_in_collection(
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
                UPDATE {self._get_table_name("collections")} SET graph_cluster_status = $1 WHERE collection_id = $2
            """
            await self.connection_manager.execute_query(
                QUERY, [KGExtractionStatus.PENDING, collection_id]
            )
            return None
        return None

    async def get_all_relationships(
        self,
        collection_id: UUID | None,
        graph_id: UUID | None,
        document_ids: Optional[list[UUID]] = None,
    ) -> list[Relationship]:

        logger.info(
            f"Getting all relationships for {collection_id} and {graph_id}"
        )

        # if collection_id is not None:

        #     # getting all documents for a collection
        #     if document_ids is None:
        #         QUERY = f"""
        #             select distinct document_id from {self._get_table_name("document_info")} where $1 = ANY(collection_ids)
        #         """
        #         document_ids_list = await self.connection_manager.fetch_query(
        #             QUERY, [collection_id]
        #         )
        #         document_ids = [
        #             doc_id["document_id"] for doc_id in document_ids_list
        #         ]

        QUERY = f"""
            SELECT id, subject, predicate, weight, object, parent_id FROM {self._get_table_name("graph_relationship")} WHERE parent_id = ANY($1)
        """
        relationships = await self.connection_manager.fetch_query(
            QUERY, [collection_id]
        )

        logger.info(
            f"Got {len(relationships)} relationships for {collection_id}"
        )

        # else:
        #     QUERY = f"""
        #         SELECT sid as id, subject, predicate, weight, object, document_id FROM {self._get_table_name("relationship")} WHERE $1 = ANY(graph_ids)
        #     """
        #     relationships = await self.connection_manager.fetch_query(
        #         QUERY, [graph_id]
        #     )

        logger.info(
            f"Got {len(relationships)} relationships for {collection_id or graph_id}"
        )

        return [Relationship(**relationship) for relationship in relationships]

    async def get(
        self,
        parent_id: UUID,
        store_type: StoreType,
        offset: int,
        limit: int,
        entity_names: Optional[list[str]] = None,
        relationship_types: Optional[list[str]] = None,
        relationship_id: Optional[UUID] = None,
        include_metadata: bool = False,
    ) -> tuple[list[Relationship], int]:
        """
        Get relationships from the specified store.

        Args:
            parent_id: UUID of the parent (graph_id or document_id)
            store_type: Type of store (graph or document)
            offset: Number of records to skip
            limit: Maximum number of records to return (-1 for no limit)
            entity_names: Optional list of entity names to filter by
            relationship_types: Optional list of relationship types to filter by
            relationship_id: Optional specific relationship ID to retrieve
            include_metadata: Whether to include metadata in the response

        Returns:
            Tuple of (list of relationships, total count)
        """
        table_name = self._get_relationship_table_for_store(store_type)

        # Handle single relationship retrieval
        if relationship_id:
            QUERY = f"""
                SELECT
                    id, subject, predicate, object, description,
                    subject_id, object_id, weight, chunk_ids,
                    parent_id {', metadata' if include_metadata else ''}
                FROM {self._get_table_name(table_name)}
                WHERE id = $1 AND parent_id = $2
            """
            result = await self.connection_manager.fetchrow_query(
                QUERY, [relationship_id, parent_id]
            )
            if not result:
                raise R2RException(
                    f"Relationship not found in {store_type.value} store", 404
                )
            return [Relationship(**result)], 1

        # Build conditions and parameters for listing relationships
        conditions = ["parent_id = $1"]
        params: list[Any] = [parent_id]
        param_index = 2

        if entity_names:
            conditions.append(
                f"(subject = ANY(${param_index}) OR object = ANY(${param_index}))"
            )
            params.append(entity_names)
            param_index += 1

        if relationship_types:
            conditions.append(f"predicate = ANY(${param_index})")
            params.append(relationship_types)
            param_index += 1

        # Count query - uses the same conditions but without offset/limit
        COUNT_QUERY = f"""
            SELECT COUNT(*)
            FROM {self._get_table_name(table_name)}
            WHERE {' AND '.join(conditions)}
        """
        count = (
            await self.connection_manager.fetch_query(COUNT_QUERY, params)
        )[0]["count"]

        # Main query for fetching relationships with pagination
        QUERY = f"""
            SELECT
                id, subject, predicate, object, description,
                subject_id, object_id, weight, chunk_ids,
                parent_id {', metadata' if include_metadata else ''}
            FROM {self._get_table_name(table_name)}
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at
            OFFSET ${param_index}
        """
        params.append(offset)
        param_index += 1

        if limit != -1:
            QUERY += f" LIMIT ${param_index}"
            params.append(limit)

        rows = await self.connection_manager.fetch_query(QUERY, params)

        relationships = []
        for row in rows:
            relationship_dict = dict(row)
            if isinstance(relationship_dict["metadata"], str):
                try:
                    relationship_dict["metadata"] = json.loads(
                        relationship_dict["metadata"]
                    )
                except json.JSONDecodeError:
                    pass
            relationships.append(Relationship(**relationship_dict))

        return relationships, count

    async def has_document(self, graph_id: UUID, document_id: UUID) -> bool:
        """
        Check if a document exists in the graph's document_ids array.

        Args:
            graph_id (UUID): ID of the graph to check
            document_id (UUID): ID of the document to look for

        Returns:
            bool: True if document exists in graph, False otherwise

        Raises:
            R2RException: If graph not found
        """
        QUERY = f"""
            SELECT EXISTS (
                SELECT 1
                FROM {self._get_table_name("graph")}
                WHERE id = $1
                AND document_ids IS NOT NULL
                AND $2 = ANY(document_ids)
            ) as exists;
        """

        result = await self.connection_manager.fetchrow_query(
            QUERY, [graph_id, document_id]
        )

        if result is None:
            raise R2RException(f"Graph {graph_id} not found", 404)

        return result["exists"]

    ####################### COMMUNITY METHODS #######################

    # async def check_communities_exist(
    #     self, collection_id: UUID, offset: int, limit: int
    # ) -> list[int]:
    #     QUERY = f"""
    #         SELECT distinct community_id FROM {self._get_table_name("graph_community")} WHERE graph_id = $1 AND community_id >= $2 AND community_id < $3
    #     """
    #     community_ids = await self.connection_manager.fetch_query(
    #         QUERY, [collection_id, offset, offset + limit]
    #     )
    #     return [item["community_id"] for item in community_ids]

    async def check_communities_exist(
        self, collection_id: UUID, community_ids: list[UUID]
    ) -> Set[UUID]:
        """
        Check which communities already exist in the database.

        Args:
            collection_id: The collection ID
            community_ids: List of community UUIDs to check

        Returns:
            Set of existing community UUIDs
        """
        print("collection_id = ", collection_id)
        print("community_ids = ", community_ids)
        QUERY = f"""
            SELECT community_id
            FROM {self._get_table_name("graph_community")}
            WHERE collection_id = $1 AND community_id = ANY($2)
        """
        # import pdb; pdb.set_trace()

        existing = await self.connection_manager.fetch_query(
            QUERY, [collection_id, [str(ele) for ele in community_ids]]
        )
        print("existing = ", existing)

        return {row["community_id"] for row in existing}

    async def add_community_info(
        self, communities: list[CommunityInfo]
    ) -> None:
        QUERY = f"""
            INSERT INTO {self._get_table_name("graph_community_info")} (node, cluster, parent_cluster, level, is_final_cluster, relationship_ids, collection_id, graph_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
        print(f"Communities = {communities}")
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
        parent_id: UUID,
        offset: int,
        limit: int,
        community_ids: Optional[list[UUID]] = None,
        include_embeddings: bool = False,
    ) -> tuple[list[Community], int]:
        """
        Get communities for a graph.

        Args:
            collection_id: UUID of the collection
            offset: Number of records to skip
            limit: Maximum number of records to return (-1 for no limit)
            community_ids: Optional list of community IDs to filter by
            include_embeddings: Whether to include embeddings in the response

        Returns:
            Tuple of (list of communities, total count)
        """
        conditions = ["collection_id = $1"]
        params: list[Any] = [parent_id]
        param_index = 2

        if community_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(community_ids)
            param_index += 1

        select_fields = """
            id, collection_id, name, summary, findings, rating, rating_explanation
        """
        if include_embeddings:
            select_fields += ", description_embedding"

        COUNT_QUERY = f"""
            SELECT COUNT(*)
            FROM {self._get_table_name("graph_community")}
            WHERE {' AND '.join(conditions)}
        """
        count = (
            await self.connection_manager.fetch_query(COUNT_QUERY, params)
        )[0]["count"]

        QUERY = f"""
            SELECT {select_fields}
            FROM {self._get_table_name("graph_community")}
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at
            OFFSET ${param_index}
        """
        params.append(offset)
        param_index += 1

        if limit != -1:
            QUERY += f" LIMIT ${param_index}"
            params.append(limit)

        rows = await self.connection_manager.fetch_query(QUERY, params)

        communities = []
        for row in rows:
            community_dict = dict(row)
            communities.append(Community(**community_dict))

        return communities, count

    async def get_community_details(
        self,
        community_id: int,
        collection_id: UUID | None,
        # graph_id: UUID | None,
    ) -> Tuple[int, list[Entity], list[Relationship]]:

        QUERY = f"""
            SELECT level FROM {self._get_table_name("graph_community_info")} WHERE cluster = $1 AND (collection_id = $2)
            LIMIT 1
        """
        level = (
            await self.connection_manager.fetch_query(
                QUERY, [community_id, collection_id]
            )
        )[0]["level"]

        # selecting table name based on entity level
        # check if there are any entities in the community that are not in the entity_embedding table
        query = f"""
            SELECT COUNT(*) FROM {self._get_table_name("graph_entity")} WHERE (parent_id = $1)
        """
        entity_count = (
            await self.connection_manager.fetch_query(query, [collection_id])
        )[0]["count"]
        table_name = "graph_entity" if entity_count > 0 else "entity"

        QUERY = f"""
            WITH node_relationship_ids AS (
                SELECT node, relationship_ids
                FROM {self._get_table_name("graph_community_info")}
                WHERE cluster = $1 AND (collection_id = $2)
            )
            SELECT DISTINCT
                e.id AS id,
                e.name AS name,
                e.description AS description
            FROM node_relationship_ids nti
            JOIN {self._get_table_name(table_name)} e ON e.name = nti.node;
        """
        entities = await self.connection_manager.fetch_query(
            QUERY, [community_id, collection_id]
        )
        entities = [Entity(**entity) for entity in entities]

        QUERY = f"""
            WITH node_relationship_ids AS (
                SELECT node, relationship_ids
                FROM {self._get_table_name("graph_community_info")}
                WHERE cluster = $1 and (collection_id = $2)
            )
            SELECT DISTINCT
                t.id, t.subject, t.predicate, t.object, t.weight, t.description
            FROM node_relationship_ids nti
            JOIN {self._get_table_name("graph_relationship")} t ON t.id = ANY(nti.relationship_ids);
        """
        relationships = await self.connection_manager.fetch_query(
            QUERY, [community_id, collection_id]
        )

        relationships = [
            Relationship(**relationship) for relationship in relationships
        ]

        return level, entities, relationships

    async def add_community(self, community: Community) -> None:

        # TODO: Fix in the short term.
        # we need to do this because postgres insert needs to be a string
        community.description_embedding = str(community.description_embedding)  # type: ignore[assignment]

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
            ON CONFLICT (community_id, level, graph_id, collection_id) DO UPDATE SET
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
            SELECT graph_cluster_status FROM {self._get_table_name("collections")} WHERE collection_id = $1
        """
        status = (
            await self.connection_manager.fetch_query(QUERY, [collection_id])
        )[0]["graph_cluster_status"]
        if status == KGExtractionStatus.PROCESSING.value:
            return

        # remove all relationships for these documents.
        DELETE_QUERIES = [
            f"DELETE FROM {self._get_table_name('graph_community_info')} WHERE collection_id = $1;",
            f"DELETE FROM {self._get_table_name('graph_community')} WHERE collection_id = $1;",
        ]

        # FIXME: This was using the pagination defaults from before... We need to review if this is as intended.
        document_ids_response = (
            await self.collections_handler.documents_in_collection(
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
                f"DELETE FROM {self._get_table_name('relationship')} WHERE document_id = ANY($1::uuid[]);",
                f"DELETE FROM {self._get_table_name('entity')} WHERE document_id = ANY($1::uuid[]);",
                f"DELETE FROM {self._get_table_name('graph_entity')} WHERE collection_id = $1;",
            ]

            # setting the kg_creation_status to PENDING for this collection.
            QUERY = f"""
                UPDATE {self._get_table_name("document_info")} SET extraction_status = $1 WHERE $2::uuid = ANY(collection_ids)
            """
            await self.connection_manager.execute_query(
                QUERY, [KGExtractionStatus.PENDING, collection_id]
            )

        for query in DELETE_QUERIES:
            if "community" in query or "graph_entity" in query:
                await self.connection_manager.execute_query(
                    query, [collection_id]
                )
            else:
                await self.connection_manager.execute_query(
                    query, [document_ids]
                )

        # set status to PENDING for this collection.
        QUERY = f"""
            UPDATE {self._get_table_name("collections")} SET graph_cluster_status = $1 WHERE collection_id = $2
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
            resolution: int | float = 1.0,
            randomness: int | float = 0.001,
            use_modularity: bool = True,
            random_seed: Optional[int] = None,
            weight_attribute: str = "weight",
            is_weighted: Optional[bool] = None,
            weight_default: int| float = 1.0,
            check_directed: bool = True,
        """

        # # relationships = await self.get_all_relationships(
        # #     collection_id, collection_id # , graph_id
        # # )

        # relationships = await self.relationships.get(parent_id=collection_id, store_type="graph", limit = 100)
        # logger.info(
        #     f"Got {len(relationships)} relationships for {collection_id}"
        # )

        # logger.info(f"Clustering with settings: {leiden_params}")
        # print("relationships = ", relationships)

        # relationship_ids_cache = await self._get_relationship_ids_cache(
        #     relationships
        # )[0]

        offset = 0
        page_size = 1000  # Increased batch size for efficiency
        all_relationships = []
        while True:
            relationships, count = await self.relationships.get(
                parent_id=collection_id,
                store_type=StoreType.GRAPH,
                offset=offset,
                limit=page_size,
            )

            if not relationships:
                break

            all_relationships.extend(relationships)
            offset += len(relationships)

            if offset >= count:
                break

        logger.info(
            f"Got {len(all_relationships)} relationships for {collection_id}"
        )

        relationship_ids_cache = await self._get_relationship_ids_cache(
            relationships
        )
        print("relationship_ids_cache = ", relationship_ids_cache)

        logger.info(f"Clustering with settings: {leiden_params}")
        # incremental clustering isn't enabled for v3 yet.
        # collection ID will not be null for v2
        # if not graph_id and await self._use_community_cache(  # type: ignore
        #     collection_id, relationship_ids_cache
        # ):
        #     num_communities = await self._incremental_clustering(  # type: ignore
        #         relationship_ids_cache, leiden_params, collection_id
        #     )
        # else:
        return await self._cluster_and_add_community_info(
            relationships=relationships,
            relationship_ids_cache=relationship_ids_cache,
            leiden_params=leiden_params,
            collection_id=collection_id,
            # graph_id=collection_id,
        )

    async def get_entity_map(
        self, offset: int, limit: int, document_id: UUID
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:

        QUERY1 = f"""
            WITH entities_list AS (
                SELECT DISTINCT name
                FROM {self._get_table_name("document_entity")}
                WHERE parent_id = $1
                ORDER BY name ASC
                LIMIT {limit} OFFSET {offset}
            )
            SELECT e.name, e.description, e.category,
                   (SELECT array_agg(DISTINCT x) FROM unnest(e.chunk_ids) x) AS chunk_ids,
                   e.parent_id
            FROM {self._get_table_name("document_entity")} e
            JOIN entities_list el ON e.name = el.name
            GROUP BY e.name, e.description, e.category, e.chunk_ids, e.parent_id
            ORDER BY e.name;"""

        entities_list = await self.connection_manager.fetch_query(
            QUERY1, [document_id]
        )
        print("entities_list = ", entities_list)
        entities_list = [Entity(**entity) for entity in entities_list]

        QUERY2 = f"""
            WITH entities_list AS (

                SELECT DISTINCT name
                FROM {self._get_table_name("document_entity")}
                WHERE parent_id = $1
                ORDER BY name ASC
                LIMIT {limit} OFFSET {offset}
            )

            SELECT DISTINCT t.subject, t.predicate, t.object, t.weight, t.description,
                   (SELECT array_agg(DISTINCT x) FROM unnest(t.chunk_ids) x) AS chunk_ids, t.parent_id
            FROM {self._get_table_name("document_relationship")} t
            JOIN entities_list el ON t.subject = el.name
            ORDER BY t.subject, t.predicate, t.object;
        """

        relationships_list = await self.connection_manager.fetch_query(
            QUERY2, [document_id]
        )
        relationships_list = [
            Relationship(**relationship) for relationship in relationships_list
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

    def _build_filters(
        self, filters: dict, parameters: list[Union[str, int, bytes]]
    ) -> str:
        def parse_condition(key: str, value: Any) -> str:  # type: ignore
            # nonlocal parameters
            if key == "collection_ids":
                if isinstance(value, dict):
                    op, clause = next(iter(value.items()))
                    if op == "$overlap":
                        # Match if collection_id equals any of the provided IDs
                        parameters.append(clause)  # Add the whole array of IDs
                        print("clause = ", clause)
                        print("key = ", key)
                        print("value = ", value)

                        return f"parent_id = ANY(${len(parameters)})"  # TODO - this is hard coded to assume graph id - collection id
                raise Exception(
                    "Unknown filter for `collection_ids`, only `$overlap` is supported"
                )
            elif key == "document_id":
                logger.warning(
                    "Filtering by `document_id` is not supported with graph search, ignoring."
                )
            elif key == "chunk_id":
                logger.warning(
                    "Filtering by `chunk_id` is not supported with graph search, ignoring."
                )
            elif key == "user_id":
                logger.warning(
                    "Filtering by `user_id` is not supported with graph search, ignoring. Use `collection_ids` instead."
                )

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
                        raise Exception("unknown operator")

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
                            raise Exception(
                                "argument to $in filter must be a list"
                            )
                        parameters.append(json.dumps(clause))
                        return f"{json_col}->'{key}' = ANY(SELECT jsonb_array_elements(${len(parameters)}::jsonb))"
                    elif op == "$contains":
                        if not isinstance(clause, (int, str, float, list)):
                            raise Exception(
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

    async def graph_search(
        self, query: str, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        """
        Perform semantic search with similarity scores while maintaining exact same structure.
        """
        query_embedding = kwargs.get("query_embedding", None)
        search_type = kwargs.get("search_type", "entity")
        embedding_type = kwargs.get("embedding_type", "description_embedding")
        property_names = kwargs.get("property_names", ["name", "description"])
        if "metadata" not in property_names:
            property_names.append("metadata")

        filters = kwargs.get("filters", {})
        print("filters = ", filters)
        limit = kwargs.get("limit", 10)
        use_fulltext_search = kwargs.get("use_fulltext_search", True)
        use_hybrid_search = kwargs.get("use_hybrid_search", True)
        if use_hybrid_search or use_fulltext_search:
            logger.warning(
                "Hybrid and fulltext search not supported for graph search, ignoring."
            )

        table_name = f"graph_{search_type}"
        # if  "collection_id" in filters and "collection_ids" not in property_names:
        #     property_names.append("collection_id")
        property_names_str = ", ".join(property_names)
        where_clause = ""
        params: list[Union[str, int, bytes]] = [str(query_embedding), limit]
        if filters:
            where_clause = self._build_filters(filters, params)
            where_clause = f"WHERE {where_clause}"
        # Modified query to include similarity score while keeping same structure
        QUERY = f"""
            SELECT
                {property_names_str},
                ({embedding_type} <=> $1) as similarity_score
            FROM {self._get_table_name(table_name)} {where_clause}
            ORDER BY {embedding_type} <=> $1
            LIMIT $2;
        """
        results = await self.connection_manager.fetch_query(
            QUERY, tuple(params)
        )

        for result in results:
            output = {
                property_name: result[property_name]
                for property_name in property_names
            }
            output["similarity_score"] = 1 - float(result["similarity_score"])
            print("output = ", output)
            yield output

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

        return await self._compute_leiden_communities(G, leiden_params)

    async def _cluster_and_add_community_info(
        self,
        relationships: list[Relationship],
        relationship_ids_cache: dict[str, list[int]],
        leiden_params: dict[str, Any],
        collection_id: Optional[UUID] = None,
        # graph_id: Optional[UUID] = None,
    ) -> int:

        # clear if there is any old information
        conditions = []
        if collection_id is not None:
            conditions.append("collection_id = $1")
        # if graph_id is not None:
        #     conditions.append("graph_id = $2")

        # if conditions:
        #     where_clause = " OR ".join(conditions)
        #     QUERY = f"""
        #         DELETE FROM {self._get_table_name("graph_community_info")} WHERE {where_clause}
        #     """
        #     await self.connection_manager.execute_query(
        #         QUERY, [collection_id]
        #     )

        #     QUERY = f"""
        #         DELETE FROM {self._get_table_name("graph_community")} WHERE {where_clause}
        #     """
        #     await self.connection_manager.execute_query(
        #         QUERY, [collection_id ]
        #     )

        await asyncio.sleep(0.1)

        start_time = time.time()

        logger.info(f"Creating graph and clustering for {collection_id}")

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
        print(
            "relationship_ids(item.node) = ",
            relationship_ids(hierarchical_communities[0].node),
        )
        print("community = ", hierarchical_communities[0])
        print("cluster = ", hierarchical_communities[0].cluster)
        inputs = [
            CommunityInfo(
                node=str(item.node),
                # cluster=item.cluster,
                cluster=generate_id(f"{item.cluster}_{collection_id}"),
                parent_cluster=item.parent_cluster,
                level=item.level,
                is_final_cluster=item.is_final_cluster,
                relationship_ids=relationship_ids(item.node),
                collection_id=collection_id,
                # graph_id=graph_id,
            )
            for item in hierarchical_communities
        ]

        print("inputs = ", inputs)
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
            SELECT graph_cluster_status FROM {self._get_table_name("collections")} WHERE collection_id = $1
        """
        status = (
            await self.connection_manager.fetchrow_query(
                QUERY, [collection_id]
            )
        )["graph_cluster_status"]
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
            SELECT document_id FROM {self._get_table_name("document_info")} WHERE $1 = ANY(collection_ids) and extraction_status = $2
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
            DELETE FROM {self._get_table_name("graph_community")} WHERE collection_id = $1 AND community_id = ANY($2)
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
                    # cluster=community.cluster + max_cluster_id,
                    cluster=generate_id(
                        f"{community.cluster + max_cluster_id}_{collection_id}"
                    ),
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

    async def get_existing_document_entity_chunk_ids(
        self, document_id: UUID
    ) -> list[str]:
        QUERY = f"""
            SELECT DISTINCT unnest(chunk_ids) AS chunk_id FROM {self._get_table_name("document_entity")} WHERE parent_id = $1
        """
        return [
            item["chunk_id"]
            for item in await self.connection_manager.fetch_query(
                QUERY, [document_id]
            )
        ]

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

        conditions = ["parent_id = $1"]
        params = [str(document_id)]

        # if entity_table_name == "collection_entity":
        #     if document_id:
        #         raise ValueError(
        #             "document_id is not supported for collection_entity table"
        #         )
        #     params.append(str(collection_id))
        # elif collection_id:
        #     conditions.append(
        #         f"""
        #         document_id = ANY(
        #             SELECT document_id FROM {self._get_table_name("document_info")}
        #             WHERE $1 = ANY(collection_ids)
        #         )
        #         """
        #     )
        #     params.append(str(collection_id))
        # else:
        #     conditions.append("document_id = $1")
        #     params.append(str(document_id))

        count_value = "DISTINCT name" if distinct else "*"

        QUERY = f"""
            SELECT COUNT({count_value}) FROM {self._get_table_name(entity_table_name)}
            WHERE {" AND ".join(conditions)}
        """
        print("QUERY = ", QUERY)
        return (await self.connection_manager.fetch_query(QUERY, params))[0][
            "count"
        ]

    async def update_entity_descriptions(self, entities: list[Entity]):

        query = f"""
            UPDATE {self._get_table_name("graph_entity")}
            SET description = $3, description_embedding = $4
            WHERE name = $1 AND graph_id = $2
        """

        inputs = [
            (
                entity.name,
                entity.parent_id,
                entity.description,
                entity.description_embedding,
            )
            for entity in entities
        ]

        await self.connection_manager.execute_many(query, inputs)  # type: ignore


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
    exclude_metadata: list[str] = [],
) -> list[UUID]:
    """
    Bulk insert objects into the specified table using jsonb_to_recordset.
    """

    # Exclude specified metadata and prepare data
    cleaned_objects = []
    for obj in objects:
        cleaned_obj = {
            k: v
            for k, v in obj.items()
            if k not in exclude_metadata and v is not None
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
