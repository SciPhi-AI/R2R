import asyncio
import contextlib
import csv
import datetime
import json
import logging
import os
import tempfile
import time
from typing import IO, Any, AsyncGenerator, Optional, Tuple
from uuid import UUID

import asyncpg
import httpx
from asyncpg.exceptions import UniqueViolationError
from fastapi import HTTPException

from core.base.abstractions import (
    Community,
    Entity,
    Graph,
    GraphExtractionStatus,
    R2RException,
    Relationship,
    StoreType,
    VectorQuantizationType,
)
from core.base.api.models import GraphResponse
from core.base.providers.database import Handler
from core.base.utils import (
    _get_vector_column_str,
    generate_entity_document_id,
)

from .base import PostgresConnectionManager
from .collections import PostgresCollectionsHandler

logger = logging.getLogger()


class PostgresEntitiesHandler(Handler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.project_name: str = kwargs.get("project_name")  # type: ignore
        self.connection_manager: PostgresConnectionManager = kwargs.get(
            "connection_manager"
        )  # type: ignore
        self.dimension: int = kwargs.get("dimension")  # type: ignore
        self.quantization_type: VectorQuantizationType = kwargs.get(
            "quantization_type"
        )  # type: ignore
        self.relationships_handler: PostgresRelationshipsHandler = (
            PostgresRelationshipsHandler(*args, **kwargs)
        )

    def _get_table_name(self, table: str) -> str:
        """Get the fully qualified table name."""
        return f'"{self.project_name}"."{table}"'

    def _get_entity_table_for_store(self, store_type: StoreType) -> str:
        """Get the appropriate table name for the store type."""
        return f"{store_type.value}_entities"

    def _get_parent_constraint(self, store_type: StoreType) -> str:
        """Get the appropriate foreign key constraint for the store type."""
        if store_type == StoreType.GRAPHS:
            return f"""
                CONSTRAINT fk_graph
                    FOREIGN KEY(parent_id)
                    REFERENCES {self._get_table_name("graphs")}(id)
                    ON DELETE CASCADE
            """
        else:
            return f"""
                CONSTRAINT fk_document
                    FOREIGN KEY(parent_id)
                    REFERENCES {self._get_table_name("documents")}(id)
                    ON DELETE CASCADE
            """

    async def create_tables(self) -> None:
        """Create separate tables for graph and document entities."""
        vector_column_str = _get_vector_column_str(
            self.dimension, self.quantization_type
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
            with contextlib.suppress(json.JSONDecodeError):
                metadata = json.loads(metadata)

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
            WHERE {" AND ".join(conditions)}
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
            WHERE {" AND ".join(conditions)}
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
                with contextlib.suppress(json.JSONDecodeError):
                    entity_dict["metadata"] = json.loads(
                        entity_dict["metadata"]
                    )

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
            with contextlib.suppress(json.JSONDecodeError):
                metadata = json.loads(metadata)

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
            SET {", ".join(update_fields)}
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
            ) from e

    async def delete(
        self,
        parent_id: UUID,
        entity_ids: Optional[list[UUID]] = None,
        store_type: StoreType = StoreType.GRAPHS,
    ) -> None:
        """Delete entities from the specified store. If entity_ids is not
        provided, deletes all entities for the given parent_id.

        Args:
            parent_id (UUID): Parent ID (collection_id or document_id)
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

    async def get_duplicate_name_blocks(
        self,
        parent_id: UUID,
        store_type: StoreType,
    ) -> list[list[Entity]]:
        """Find all groups of entities that share identical names within the
        same parent.

        Returns a list of entity groups, where each group contains entities
        with the same name. For each group, includes the n most dissimilar
        descriptions based on cosine similarity.
        """
        table_name = self._get_entity_table_for_store(store_type)

        # First get the duplicate names and their descriptions with embeddings
        query = f"""
            WITH duplicates AS (
                SELECT name
                FROM {self._get_table_name(table_name)}
                WHERE parent_id = $1
                GROUP BY name
                HAVING COUNT(*) > 1
            )
            SELECT
                e.id, e.name, e.category, e.description,
                e.parent_id, e.chunk_ids, e.metadata
            FROM {self._get_table_name(table_name)} e
            WHERE e.parent_id = $1
            AND e.name IN (SELECT name FROM duplicates)
            ORDER BY e.name;
        """

        rows = await self.connection_manager.fetch_query(query, [parent_id])

        # Group entities by name
        name_groups: dict[str, list[Entity]] = {}
        for row in rows:
            entity_dict = dict(row)
            if isinstance(entity_dict["metadata"], str):
                with contextlib.suppress(json.JSONDecodeError):
                    entity_dict["metadata"] = json.loads(
                        entity_dict["metadata"]
                    )

            entity = Entity(**entity_dict)
            name_groups.setdefault(entity.name, []).append(entity)

        return list(name_groups.values())

    async def merge_duplicate_name_blocks(
        self,
        parent_id: UUID,
        store_type: StoreType,
    ) -> list[tuple[list[Entity], Entity]]:
        """Merge entities that share identical names.

        Returns list of tuples: (original_entities, merged_entity)
        """
        duplicate_blocks = await self.get_duplicate_name_blocks(
            parent_id, store_type
        )
        merged_results: list[tuple[list[Entity], Entity]] = []

        for block in duplicate_blocks:
            # Create a new merged entity from the block
            merged_entity = await self._create_merged_entity(block)
            merged_results.append((block, merged_entity))

            table_name = self._get_entity_table_for_store(store_type)
            async with self.connection_manager.transaction():
                # Insert the merged entity
                new_id = await self._insert_merged_entity(
                    merged_entity, table_name
                )

                merged_entity.id = new_id

                # Get the old entity IDs
                old_ids = [str(entity.id) for entity in block]

                relationship_table = self.relationships_handler._get_relationship_table_for_store(
                    store_type
                )

                # Update relationships where old entities appear as subjects
                subject_update_query = f"""
                    UPDATE {self._get_table_name(relationship_table)}
                    SET subject_id = $1
                    WHERE subject_id = ANY($2::uuid[])
                    AND parent_id = $3
                """
                await self.connection_manager.execute_query(
                    subject_update_query, [new_id, old_ids, parent_id]
                )

                # Update relationships where old entities appear as objects
                object_update_query = f"""
                    UPDATE {self._get_table_name(relationship_table)}
                    SET object_id = $1
                    WHERE object_id = ANY($2::uuid[])
                    AND parent_id = $3
                """
                await self.connection_manager.execute_query(
                    object_update_query, [new_id, old_ids, parent_id]
                )

                # Delete the original entities
                delete_query = f"""
                    DELETE FROM {self._get_table_name(table_name)}
                    WHERE id = ANY($1::uuid[])
                """
                await self.connection_manager.execute_query(
                    delete_query, [old_ids]
                )

        return merged_results

    async def _insert_merged_entity(
        self, entity: Entity, table_name: str
    ) -> UUID:
        """Insert merged entity and return its new ID."""
        new_id = generate_entity_document_id()

        query = f"""
            INSERT INTO {self._get_table_name(table_name)}
            (id, name, category, description, parent_id, chunk_ids, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """

        values = [
            new_id,
            entity.name,
            entity.category,
            entity.description,
            entity.parent_id,
            entity.chunk_ids,
            json.dumps(entity.metadata) if entity.metadata else None,
        ]

        result = await self.connection_manager.fetch_query(query, values)
        return result[0]["id"]

    async def _create_merged_entity(self, entities: list[Entity]) -> Entity:
        """Create a merged entity from a list of duplicate entities.

        Uses various strategies to combine fields.
        """
        if not entities:
            raise ValueError("Cannot merge empty list of entities")

        # Take the first non-None category, or None if all are None
        category = next(
            (e.category for e in entities if e.category is not None), None
        )

        # Combine descriptions with newlines if they differ
        descriptions = {e.description for e in entities if e.description}
        description = "\n\n".join(descriptions) if descriptions else None

        # Combine chunk_ids, removing duplicates
        chunk_ids = list(
            {
                chunk_id
                for entity in entities
                for chunk_id in (entity.chunk_ids or [])
            }
        )

        # Merge metadata dictionaries
        merged_metadata: dict[str, Any] = {}
        for entity in entities:
            if entity.metadata:
                merged_metadata |= entity.metadata

        # Create new merged entity (without actually inserting to DB)
        return Entity(
            id=UUID(
                "00000000-0000-0000-0000-000000000000"
            ),  # Placeholder UUID
            name=entities[0].name,  # All entities in block have same name
            category=category,
            description=description,
            parent_id=entities[0].parent_id,
            chunk_ids=chunk_ids or None,
            metadata=merged_metadata or None,
        )

    async def export_to_csv(
        self,
        parent_id: UUID,
        store_type: StoreType,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        """Creates a CSV file from the PostgreSQL data and returns the path to
        the temp file."""
        valid_columns = {
            "id",
            "name",
            "category",
            "description",
            "parent_id",
            "chunk_ids",
            "metadata",
            "created_at",
            "updated_at",
        }

        if not columns:
            columns = list(valid_columns)
        elif invalid_cols := set(columns) - valid_columns:
            raise ValueError(f"Invalid columns: {invalid_cols}")

        select_stmt = f"""
            SELECT
                id::text,
                name,
                category,
                description,
                parent_id::text,
                chunk_ids::text,
                metadata::text,
                to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at
            FROM {self._get_table_name(self._get_entity_table_for_store(store_type))}
        """

        conditions = ["parent_id = $1"]
        params: list[Any] = [parent_id]
        param_index = 2

        if filters:
            for field, value in filters.items():
                if field not in valid_columns:
                    continue

                if isinstance(value, dict):
                    for op, val in value.items():
                        if op == "$eq":
                            conditions.append(f"{field} = ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$gt":
                            conditions.append(f"{field} > ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$lt":
                            conditions.append(f"{field} < ${param_index}")
                            params.append(val)
                            param_index += 1
                else:
                    # Direct equality
                    conditions.append(f"{field} = ${param_index}")
                    params.append(value)
                    param_index += 1

        if conditions:
            select_stmt = f"{select_stmt} WHERE {' AND '.join(conditions)}"

        select_stmt = f"{select_stmt} ORDER BY created_at DESC"

        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", delete=True, suffix=".csv"
            )
            writer = csv.writer(temp_file, quoting=csv.QUOTE_ALL)

            async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
                async with conn.transaction():
                    cursor = await conn.cursor(select_stmt, *params)

                    if include_header:
                        writer.writerow(columns)

                    chunk_size = 1000
                    while True:
                        rows = await cursor.fetch(chunk_size)
                        if not rows:
                            break
                        for row in rows:
                            row_dict = {
                                "id": row[0],
                                "name": row[1],
                                "category": row[2],
                                "description": row[3],
                                "parent_id": row[4],
                                "chunk_ids": row[5],
                                "metadata": row[6],
                                "created_at": row[7],
                                "updated_at": row[8],
                            }
                            writer.writerow([row_dict[col] for col in columns])

            temp_file.flush()
            return temp_file.name, temp_file

        except Exception as e:
            if temp_file:
                temp_file.close()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to export data: {str(e)}",
            ) from e


class PostgresRelationshipsHandler(Handler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.project_name: str = kwargs.get("project_name")  # type: ignore
        self.connection_manager: PostgresConnectionManager = kwargs.get(
            "connection_manager"
        )  # type: ignore
        self.dimension: int = kwargs.get("dimension")  # type: ignore
        self.quantization_type: VectorQuantizationType = kwargs.get(
            "quantization_type"
        )  # type: ignore

    def _get_table_name(self, table: str) -> str:
        """Get the fully qualified table name."""
        return f'"{self.project_name}"."{table}"'

    def _get_relationship_table_for_store(self, store_type: StoreType) -> str:
        """Get the appropriate table name for the store type."""
        return f"{store_type.value}_relationships"

    def _get_parent_constraint(self, store_type: StoreType) -> str:
        """Get the appropriate foreign key constraint for the store type."""
        if store_type == StoreType.GRAPHS:
            return f"""
                CONSTRAINT fk_graph
                    FOREIGN KEY(parent_id)
                    REFERENCES {self._get_table_name("graphs")}(id)
                    ON DELETE CASCADE
            """
        else:
            return f"""
                CONSTRAINT fk_document
                    FOREIGN KEY(parent_id)
                    REFERENCES {self._get_table_name("documents")}(id)
                    ON DELETE CASCADE
            """

    async def create_tables(self) -> None:
        """Create separate tables for graph and document relationships."""
        for store_type in StoreType:
            table_name = self._get_relationship_table_for_store(store_type)
            parent_constraint = self._get_parent_constraint(store_type)
            vector_column_str = _get_vector_column_str(
                self.dimension, self.quantization_type
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
            with contextlib.suppress(json.JSONDecodeError):
                metadata = json.loads(metadata)

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
        """Get relationships from the specified store.

        Args:
            parent_id: UUID of the parent (collection_id or document_id)
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
            WHERE {" AND ".join(conditions)}
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
            WHERE {" AND ".join(conditions)}
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
                with contextlib.suppress(json.JSONDecodeError):
                    relationship_dict["metadata"] = json.loads(
                        relationship_dict["metadata"]
                    )
            elif not include_metadata:
                relationship_dict.pop("metadata", None)
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
            with contextlib.suppress(json.JSONDecodeError):
                metadata = json.loads(metadata)

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
            SET {", ".join(update_fields)}
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
            ) from e

    async def delete(
        self,
        parent_id: UUID,
        relationship_ids: Optional[list[UUID]] = None,
        store_type: StoreType = StoreType.GRAPHS,
    ) -> None:
        """Delete relationships from the specified store. If relationship_ids
        is not provided, deletes all relationships for the given parent_id.

        Args:
            parent_id: UUID of the parent (collection_id or document_id)
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

    async def export_to_csv(
        self,
        parent_id: UUID,
        store_type: StoreType,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        """Creates a CSV file from the PostgreSQL data and returns the path to
        the temp file."""
        valid_columns = {
            "id",
            "subject",
            "predicate",
            "object",
            "description",
            "subject_id",
            "object_id",
            "weight",
            "chunk_ids",
            "parent_id",
            "metadata",
            "created_at",
            "updated_at",
        }

        if not columns:
            columns = list(valid_columns)
        elif invalid_cols := set(columns) - valid_columns:
            raise ValueError(f"Invalid columns: {invalid_cols}")

        select_stmt = f"""
            SELECT
                id::text,
                subject,
                predicate,
                object,
                description,
                subject_id::text,
                object_id::text,
                weight,
                chunk_ids::text,
                parent_id::text,
                metadata::text,
                to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at
            FROM {self._get_table_name(self._get_relationship_table_for_store(store_type))}
        """

        conditions = ["parent_id = $1"]
        params: list[Any] = [parent_id]
        param_index = 2

        if filters:
            for field, value in filters.items():
                if field not in valid_columns:
                    continue

                if isinstance(value, dict):
                    for op, val in value.items():
                        if op == "$eq":
                            conditions.append(f"{field} = ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$gt":
                            conditions.append(f"{field} > ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$lt":
                            conditions.append(f"{field} < ${param_index}")
                            params.append(val)
                            param_index += 1
                else:
                    # Direct equality
                    conditions.append(f"{field} = ${param_index}")
                    params.append(value)
                    param_index += 1

        if conditions:
            select_stmt = f"{select_stmt} WHERE {' AND '.join(conditions)}"

        select_stmt = f"{select_stmt} ORDER BY created_at DESC"

        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", delete=True, suffix=".csv"
            )
            writer = csv.writer(temp_file, quoting=csv.QUOTE_ALL)

            async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
                async with conn.transaction():
                    cursor = await conn.cursor(select_stmt, *params)

                    if include_header:
                        writer.writerow(columns)

                    chunk_size = 1000
                    while True:
                        rows = await cursor.fetch(chunk_size)
                        if not rows:
                            break
                        for row in rows:
                            writer.writerow(row)

            temp_file.flush()
            return temp_file.name, temp_file

        except Exception as e:
            if temp_file:
                temp_file.close()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to export data: {str(e)}",
            ) from e


class PostgresCommunitiesHandler(Handler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.project_name: str = kwargs.get("project_name")  # type: ignore
        self.connection_manager: PostgresConnectionManager = kwargs.get(
            "connection_manager"
        )  # type: ignore
        self.dimension: int = kwargs.get("dimension")  # type: ignore
        self.quantization_type: VectorQuantizationType = kwargs.get(
            "quantization_type"
        )  # type: ignore

    async def create_tables(self) -> None:
        vector_column_str = _get_vector_column_str(
            self.dimension, self.quantization_type
        )

        query = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name("graphs_communities")} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
            UNIQUE (community_id, level, collection_id)
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
        table_name = "graphs_communities"

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
            ) from e

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
        table_name = "graphs_communities"
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
            ) from e

    async def delete(
        self,
        parent_id: UUID,
        community_id: UUID,
    ) -> None:
        table_name = "graphs_communities"

        params = [community_id, parent_id]

        # Delete the community
        query = f"""
            DELETE FROM {self._get_table_name(table_name)}
            WHERE id = $1 AND collection_id = $2
        """

        try:
            await self.connection_manager.execute_query(query, params)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while deleting the community: {e}",
            ) from e

    async def delete_all_communities(
        self,
        parent_id: UUID,
    ) -> None:
        table_name = "graphs_communities"

        params = [parent_id]

        # Delete all communities for the parent_id
        query = f"""
            DELETE FROM {self._get_table_name(table_name)}
            WHERE collection_id = $1
        """

        try:
            await self.connection_manager.execute_query(query, params)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while deleting communities: {e}",
            ) from e

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
        table_name = "graphs_communities"

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
            WHERE {" AND ".join(conditions)}
        """

        count = (
            await self.connection_manager.fetch_query(
                COUNT_QUERY, params[: param_index - 1]
            )
        )[0]["count"]

        QUERY = f"""
            SELECT {select_fields}
            FROM {self._get_table_name(table_name)}
            WHERE {" AND ".join(conditions)}
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

    async def export_to_csv(
        self,
        parent_id: UUID,
        store_type: StoreType,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        """Creates a CSV file from the PostgreSQL data and returns the path to
        the temp file."""
        valid_columns = {
            "id",
            "collection_id",
            "community_id",
            "level",
            "name",
            "summary",
            "findings",
            "rating",
            "rating_explanation",
            "created_at",
            "updated_at",
            "metadata",
        }

        if not columns:
            columns = list(valid_columns)
        elif invalid_cols := set(columns) - valid_columns:
            raise ValueError(f"Invalid columns: {invalid_cols}")

        table_name = "graphs_communities"

        select_stmt = f"""
            SELECT
                id::text,
                collection_id::text,
                community_id::text,
                level,
                name,
                summary,
                findings::text,
                rating,
                rating_explanation,
                to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at,
                metadata::text
            FROM {self._get_table_name(table_name)}
        """

        conditions = ["collection_id = $1"]
        params: list[Any] = [parent_id]
        param_index = 2

        if filters:
            for field, value in filters.items():
                if field not in valid_columns:
                    continue

                if isinstance(value, dict):
                    for op, val in value.items():
                        if op == "$eq":
                            conditions.append(f"{field} = ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$gt":
                            conditions.append(f"{field} > ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$lt":
                            conditions.append(f"{field} < ${param_index}")
                            params.append(val)
                            param_index += 1
                else:
                    # Direct equality
                    conditions.append(f"{field} = ${param_index}")
                    params.append(value)
                    param_index += 1

        if conditions:
            select_stmt = f"{select_stmt} WHERE {' AND '.join(conditions)}"

        select_stmt = f"{select_stmt} ORDER BY created_at DESC"

        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", delete=True, suffix=".csv"
            )
            writer = csv.writer(temp_file, quoting=csv.QUOTE_ALL)

            async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
                async with conn.transaction():
                    cursor = await conn.cursor(select_stmt, *params)

                    if include_header:
                        writer.writerow(columns)

                    chunk_size = 1000
                    while True:
                        rows = await cursor.fetch(chunk_size)
                        if not rows:
                            break
                        for row in rows:
                            writer.writerow(row)

            temp_file.flush()
            return temp_file.name, temp_file

        except Exception as e:
            if temp_file:
                temp_file.close()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to export data: {str(e)}",
            ) from e


class PostgresGraphsHandler(Handler):
    """Handler for Knowledge Graph METHODS in PostgreSQL."""

    TABLE_NAME = "graphs"

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.project_name: str = kwargs.get("project_name")  # type: ignore
        self.connection_manager: PostgresConnectionManager = kwargs.get(
            "connection_manager"
        )  # type: ignore
        self.dimension: int = kwargs.get("dimension")  # type: ignore
        self.quantization_type: VectorQuantizationType = kwargs.get(
            "quantization_type"
        )  # type: ignore
        self.collections_handler: PostgresCollectionsHandler = kwargs.get(
            "collections_handler"
        )  # type: ignore

        self.entities = PostgresEntitiesHandler(*args, **kwargs)
        self.relationships = PostgresRelationshipsHandler(*args, **kwargs)
        self.communities = PostgresCommunitiesHandler(*args, **kwargs)

        self.handlers = [
            self.entities,
            self.relationships,
            self.communities,
        ]

    async def create_tables(self) -> None:
        """Create the graph tables with mandatory collection_id support."""
        QUERY = f"""
            CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresGraphsHandler.TABLE_NAME)} (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                collection_id UUID NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                document_ids UUID[],
                metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS graph_collection_id_idx
                ON {self._get_table_name("graphs")} (collection_id);
        """

        await self.connection_manager.execute_query(QUERY)

        for handler in self.handlers:
            await handler.create_tables()

    async def create(
        self,
        collection_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: str = "pending",
    ) -> GraphResponse:
        """Create a new graph associated with a collection."""

        name = name or f"Graph {collection_id}"
        description = description or ""

        query = f"""
            INSERT INTO {self._get_table_name(PostgresGraphsHandler.TABLE_NAME)}
            (id, collection_id, name, description, status)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, collection_id, name, description, status, created_at, updated_at, document_ids
        """
        params = [
            collection_id,
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
            ) from None

    async def reset(self, parent_id: UUID) -> None:
        """Completely reset a graph and all associated data."""

        await self.entities.delete(
            parent_id=parent_id, store_type=StoreType.GRAPHS
        )
        await self.relationships.delete(
            parent_id=parent_id, store_type=StoreType.GRAPHS
        )
        await self.communities.delete_all_communities(parent_id=parent_id)

        # Now, update the graph record to remove any attached document IDs.
        # This sets document_ids to an empty UUID array.
        query = f"""
            UPDATE {self._get_table_name(PostgresGraphsHandler.TABLE_NAME)}
            SET document_ids = ARRAY[]::uuid[]
            WHERE id = $1;
        """
        await self.connection_manager.execute_query(query, [parent_id])

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
                FROM {self._get_table_name(PostgresGraphsHandler.TABLE_NAME)}
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
            ) from e

    async def get(
        self, offset: int, limit: int, graph_id: Optional[UUID] = None
    ):
        if graph_id is None:
            params = [offset, limit]

            QUERY = f"""
                SELECT * FROM {self._get_table_name(PostgresGraphsHandler.TABLE_NAME)}
                OFFSET $1 LIMIT $2
            """

            ret = await self.connection_manager.fetch_query(QUERY, params)

            COUNT_QUERY = f"""
                SELECT COUNT(*) FROM {self._get_table_name(PostgresGraphsHandler.TABLE_NAME)}
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
                SELECT * FROM {self._get_table_name(PostgresGraphsHandler.TABLE_NAME)} WHERE id = $1
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
        """Add documents to the graph by copying their entities and
        relationships."""
        # Copy entities from document_entity to graphs_entities
        ENTITY_COPY_QUERY = f"""
            INSERT INTO {self._get_table_name("graphs_entities")} (
                name, category, description, parent_id, description_embedding,
                chunk_ids, metadata
            )
            SELECT
                name, category, description, $1, description_embedding,
                chunk_ids, metadata
            FROM {self._get_table_name("documents_entities")}
            WHERE parent_id = ANY($2)
        """
        await self.connection_manager.execute_query(
            ENTITY_COPY_QUERY, [id, document_ids]
        )

        # Copy relationships from documents_relationships to graphs_relationships
        RELATIONSHIP_COPY_QUERY = f"""
            INSERT INTO {self._get_table_name("graphs_relationships")} (
                subject, predicate, object, description, subject_id, object_id,
                weight, chunk_ids, parent_id, metadata, description_embedding
            )
            SELECT
                subject, predicate, object, description, subject_id, object_id,
                weight, chunk_ids, $1, metadata, description_embedding
            FROM {self._get_table_name("documents_relationships")}
            WHERE parent_id = ANY($2)
        """
        await self.connection_manager.execute_query(
            RELATIONSHIP_COPY_QUERY, [id, document_ids]
        )

        # Add document_ids to the graph
        UPDATE_GRAPH_QUERY = f"""
            UPDATE {self._get_table_name(PostgresGraphsHandler.TABLE_NAME)}
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

    async def update(
        self,
        collection_id: UUID,
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
        params.append(collection_id)

        query = f"""
            UPDATE {self._get_table_name(PostgresGraphsHandler.TABLE_NAME)}
            SET {", ".join(update_fields)}
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
            ) from e

    async def get_entities(
        self,
        parent_id: UUID,
        offset: int,
        limit: int,
        entity_ids: Optional[list[UUID]] = None,
        entity_names: Optional[list[str]] = None,
        include_embeddings: bool = False,
    ) -> tuple[list[Entity], int]:
        """Get entities for a graph.

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
            FROM {self._get_table_name("graphs_entities")}
            WHERE {" AND ".join(conditions)}
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
            FROM {self._get_table_name("graphs_entities")}
            WHERE {" AND ".join(conditions)}
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
            entity_dict = dict(row)
            if isinstance(entity_dict["metadata"], str):
                with contextlib.suppress(json.JSONDecodeError):
                    entity_dict["metadata"] = json.loads(
                        entity_dict["metadata"]
                    )

            entities.append(Entity(**entity_dict))

        return entities, count

    async def get_relationships(
        self,
        parent_id: UUID,
        offset: int,
        limit: int,
        relationship_ids: Optional[list[UUID]] = None,
        relationship_types: Optional[list[str]] = None,
        include_embeddings: bool = False,
    ) -> tuple[list[Relationship], int]:
        """Get relationships for a graph.

        Args:
            parent_id: UUID of the graph
            offset: Number of records to skip
            limit: Maximum number of records to return (-1 for no limit)
            relationship_ids: Optional list of relationship IDs to filter by
            relationship_types: Optional list of relationship types to filter by
            include_metadata: Whether to include metadata in the response

        Returns:
            Tuple of (list of relationships, total count)
        """
        conditions = ["parent_id = $1"]
        params: list[Any] = [parent_id]
        param_index = 2

        if relationship_ids:
            conditions.append(f"id = ANY(${param_index})")
            params.append(relationship_ids)
            param_index += 1

        if relationship_types:
            conditions.append(f"predicate = ANY(${param_index})")
            params.append(relationship_types)
            param_index += 1

        # Count query - uses the same conditions but without offset/limit
        COUNT_QUERY = f"""
            SELECT COUNT(*)
            FROM {self._get_table_name("graphs_relationships")}
            WHERE {" AND ".join(conditions)}
        """
        count = (
            await self.connection_manager.fetch_query(COUNT_QUERY, params)
        )[0]["count"]

        # Define base columns to select
        select_fields = """
            id, subject, predicate, object, weight, chunk_ids, parent_id, metadata
        """
        if include_embeddings:
            select_fields += ", description_embedding"

        # Main query for fetching relationships with pagination
        QUERY = f"""
            SELECT {select_fields}
            FROM {self._get_table_name("graphs_relationships")}
            WHERE {" AND ".join(conditions)}
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
                with contextlib.suppress(json.JSONDecodeError):
                    relationship_dict["metadata"] = json.loads(
                        relationship_dict["metadata"]
                    )

            relationships.append(Relationship(**relationship_dict))

        return relationships, count

    async def add_entities(
        self,
        entities: list[Entity],
        table_name: str,
        conflict_columns: list[str] | None = None,
    ) -> asyncpg.Record:
        """Upsert entities into the entities_raw table. These are raw entities
        extracted from the document.

        Args:
            entities: list[Entity]: list of entities to upsert
            collection_name: str: name of the collection

        Returns:
            result: asyncpg.Record: result of the upsert operation
        """
        if not conflict_columns:
            conflict_columns = []
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

    async def get_all_relationships(
        self,
        collection_id: UUID | None,
        graph_id: UUID | None,
        document_ids: Optional[list[UUID]] = None,
    ) -> list[Relationship]:
        QUERY = f"""
            SELECT id, subject, predicate, weight, object, parent_id FROM {self._get_table_name("graphs_relationships")} WHERE parent_id = ANY($1)
        """
        relationships = await self.connection_manager.fetch_query(
            QUERY, [collection_id]
        )

        return [Relationship(**relationship) for relationship in relationships]

    async def has_document(self, graph_id: UUID, document_id: UUID) -> bool:
        """Check if a document exists in the graph's document_ids array.

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
                FROM {self._get_table_name("graphs")}
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

    async def get_communities(
        self,
        parent_id: UUID,
        offset: int,
        limit: int,
        community_ids: Optional[list[UUID]] = None,
        include_embeddings: bool = False,
    ) -> tuple[list[Community], int]:
        """Get communities for a graph.

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
            FROM {self._get_table_name("graphs_communities")}
            WHERE {" AND ".join(conditions)}
        """
        count = (
            await self.connection_manager.fetch_query(COUNT_QUERY, params)
        )[0]["count"]

        QUERY = f"""
            SELECT {select_fields}
            FROM {self._get_table_name("graphs_communities")}
            WHERE {" AND ".join(conditions)}
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

    async def add_community(self, community: Community) -> None:
        # TODO: Fix in the short term.
        # we need to do this because postgres insert needs to be a string
        community.description_embedding = str(community.description_embedding)  # type: ignore[assignment]

        non_null_attrs = {
            k: v for k, v in community.__dict__.items() if v is not None
        }
        columns = ", ".join(non_null_attrs.keys())
        placeholders = ", ".join(
            f"${i + 1}" for i in range(len(non_null_attrs))
        )

        conflict_columns = ", ".join(
            [f"{k} = EXCLUDED.{k}" for k in non_null_attrs]
        )

        QUERY = f"""
            INSERT INTO {self._get_table_name("graphs_communities")} ({columns})
            VALUES ({placeholders})
            ON CONFLICT (community_id, level, collection_id) DO UPDATE SET
                {conflict_columns}
            """

        await self.connection_manager.execute_many(
            QUERY, [tuple(non_null_attrs.values())]
        )

    async def delete(self, collection_id: UUID) -> None:
        graphs = await self.get(graph_id=collection_id, offset=0, limit=-1)

        if len(graphs["results"]) == 0:
            raise R2RException(
                message=f"Graph not found for collection {collection_id}",
                status_code=404,
            )
        await self.reset(collection_id)
        # set status to PENDING for this collection.
        QUERY = f"""
            UPDATE {self._get_table_name("collections")} SET graph_cluster_status = $1 WHERE id = $2
        """
        await self.connection_manager.execute_query(
            QUERY, [GraphExtractionStatus.PENDING, collection_id]
        )
        # Delete the graph
        QUERY = f"""
            DELETE FROM {self._get_table_name("graphs")} WHERE collection_id = $1
        """
        try:
            await self.connection_manager.execute_query(QUERY, [collection_id])
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while deleting the graph: {e}",
            ) from e

    async def perform_graph_clustering(
        self,
        collection_id: UUID,
        leiden_params: dict[str, Any],
    ) -> Tuple[int, Any]:
        """Calls the external clustering service to cluster the graph."""

        offset = 0
        page_size = 1000
        all_relationships = []
        while True:
            relationships, count = await self.relationships.get(
                parent_id=collection_id,
                store_type=StoreType.GRAPHS,
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
            f"Clustering over {len(all_relationships)} relationships for {collection_id} with settings: {leiden_params}"
        )
        if len(all_relationships) == 0:
            raise R2RException(
                message="No relationships found for clustering",
                status_code=400,
            )

        return await self._cluster_and_add_community_info(
            relationships=all_relationships,
            leiden_params=leiden_params,
            collection_id=collection_id,
        )

    async def _call_clustering_service(
        self, relationships: list[Relationship], leiden_params: dict[str, Any]
    ) -> list[dict]:
        """Calls the external Graspologic clustering service, sending
        relationships and parameters.

        Expects a response with 'communities' field.
        """
        # Convert relationships to a JSON-friendly format
        rel_data = []
        for r in relationships:
            rel_data.append(
                {
                    "id": str(r.id),
                    "subject": r.subject,
                    "object": r.object,
                    "weight": r.weight if r.weight is not None else 1.0,
                }
            )

        endpoint = os.environ.get("CLUSTERING_SERVICE_URL")
        if not endpoint:
            raise ValueError("CLUSTERING_SERVICE_URL not set.")

        url = f"{endpoint}/cluster"

        payload = {"relationships": rel_data, "leiden_params": leiden_params}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=3600)
            response.raise_for_status()

        data = response.json()
        return data.get("communities", [])

    async def _create_graph_and_cluster(
        self,
        relationships: list[Relationship],
        leiden_params: dict[str, Any],
    ) -> Any:
        """Create a graph and cluster it."""

        return await self._call_clustering_service(
            relationships, leiden_params
        )

    async def _cluster_and_add_community_info(
        self,
        relationships: list[Relationship],
        leiden_params: dict[str, Any],
        collection_id: UUID,
    ) -> Tuple[int, Any]:
        logger.info(f"Creating graph and clustering for {collection_id}")

        await asyncio.sleep(0.1)
        start_time = time.time()

        hierarchical_communities = await self._create_graph_and_cluster(
            relationships=relationships,
            leiden_params=leiden_params,
        )

        logger.info(
            f"Computing Leiden communities completed, time {time.time() - start_time:.2f} seconds."
        )

        if not hierarchical_communities:
            num_communities = 0
        else:
            num_communities = (
                max(item["cluster"] for item in hierarchical_communities) + 1
            )

        logger.info(
            f"Generated {num_communities} communities, time {time.time() - start_time:.2f} seconds."
        )

        return num_communities, hierarchical_communities

    async def get_entity_map(
        self, offset: int, limit: int, document_id: UUID
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        QUERY1 = f"""
            WITH entities_list AS (
                SELECT DISTINCT name
                FROM {self._get_table_name("documents_entities")}
                WHERE parent_id = $1
                ORDER BY name ASC
                LIMIT {limit} OFFSET {offset}
            )
            SELECT e.name, e.description, e.category,
                   (SELECT array_agg(DISTINCT x) FROM unnest(e.chunk_ids) x) AS chunk_ids,
                   e.parent_id
            FROM {self._get_table_name("documents_entities")} e
            JOIN entities_list el ON e.name = el.name
            GROUP BY e.name, e.description, e.category, e.chunk_ids, e.parent_id
            ORDER BY e.name;"""

        entities_list = await self.connection_manager.fetch_query(
            QUERY1, [document_id]
        )
        entities_list = [Entity(**entity) for entity in entities_list]

        QUERY2 = f"""
            WITH entities_list AS (

                SELECT DISTINCT name
                FROM {self._get_table_name("documents_entities")}
                WHERE parent_id = $1
                ORDER BY name ASC
                LIMIT {limit} OFFSET {offset}
            )

            SELECT DISTINCT t.subject, t.predicate, t.object, t.weight, t.description,
                   (SELECT array_agg(DISTINCT x) FROM unnest(t.chunk_ids) x) AS chunk_ids, t.parent_id
            FROM {self._get_table_name("documents_relationships")} t
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

    async def graph_search(
        self, query: str, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        """Perform semantic search with similarity scores while maintaining
        exact same structure."""

        query_embedding = kwargs.get("query_embedding", None)
        if query_embedding is None:
            raise ValueError(
                "query_embedding must be provided for semantic search"
            )

        search_type = kwargs.get(
            "search_type", "entities"
        )  # entities | relationships | communities
        embedding_type = kwargs.get("embedding_type", "description_embedding")
        property_names = kwargs.get("property_names", ["name", "description"])

        # Add metadata if not present
        if "metadata" not in property_names:
            property_names.append("metadata")

        filters = kwargs.get("filters", {})
        limit = kwargs.get("limit", 10)
        use_fulltext_search = kwargs.get("use_fulltext_search", True)
        use_hybrid_search = kwargs.get("use_hybrid_search", True)

        if use_hybrid_search or use_fulltext_search:
            logger.warning(
                "Hybrid and fulltext search not supported for graph search, ignoring."
            )

        table_name = f"graphs_{search_type}"
        property_names_str = ", ".join(property_names)

        # Build the WHERE clause from filters
        params: list[str | int | bytes] = [
            json.dumps(query_embedding),
            limit,
        ]
        conditions_clause = self._build_filters(filters, params, search_type)
        where_clause = (
            f"WHERE {conditions_clause}" if conditions_clause else ""
        )

        # Construct the query
        # Note: For vector similarity, we use <=> for distance. The smaller the number, the more similar.
        # We'll convert that to similarity_score by doing (1 - distance).
        QUERY = f"""
            SELECT
                {property_names_str},
                ({embedding_type} <=> $1) as similarity_score
            FROM {self._get_table_name(table_name)}
            {where_clause}
            ORDER BY {embedding_type} <=> $1
            LIMIT $2;
        """

        results = await self.connection_manager.fetch_query(
            QUERY, tuple(params)
        )

        for result in results:
            output = {
                prop: result[prop] for prop in property_names if prop in result
            }
            output["similarity_score"] = (
                1 - float(result["similarity_score"])
                if result.get("similarity_score")
                else "n/a"
            )
            yield output

    def _build_filters(
        self, filter_dict: dict, parameters: list[Any], search_type: str
    ) -> str:
        """Build a WHERE clause from a nested filter dictionary for the graph
        search.

        - If search_type == "communities", we normally filter by `collection_id`.
        - Otherwise (entities/relationships), we normally filter by `parent_id`.
        - If user provides `"collection_ids": {...}`, we interpret that as wanting
        to filter by multiple collection IDs (i.e. 'parent_id IN (...)' or
        'collection_id IN (...)').
        """

        # The usual "base" column used by your code
        base_id_column = (
            "collection_id" if search_type == "communities" else "parent_id"
        )

        def parse_condition(key: str, value: Any) -> str:
            # ----------------------------------------------------------------------
            # 1) If it's the normal base_id_column (like "parent_id" or "collection_id")
            # ----------------------------------------------------------------------
            if key == base_id_column:
                if isinstance(value, dict):
                    op, clause = next(iter(value.items()))
                    if op == "$eq":
                        # single equality
                        parameters.append(str(clause))
                        return f"{base_id_column} = ${len(parameters)}::uuid"
                    elif op in ("$in", "$overlap"):
                        # treat both $in/$overlap as "IN the set" for a single column
                        array_val = [str(x) for x in clause]
                        parameters.append(array_val)
                        return f"{base_id_column} = ANY(${len(parameters)}::uuid[])"
                    # handle other operators as needed
                else:
                    # direct equality
                    parameters.append(str(value))
                    return f"{base_id_column} = ${len(parameters)}::uuid"

            # ----------------------------------------------------------------------
            # 2) SPECIAL: if user specifically sets "collection_ids" in filters
            #    We interpret that to mean "Look for rows whose parent_id (or collection_id)
            #    is in the array of values" – i.e. we do the same logic but we forcibly
            #    direct it to the same column: parent_id or collection_id.
            # ----------------------------------------------------------------------
            elif key == "collection_ids":
                # If we are searching communities, the relevant field is `collection_id`.
                # If searching entities/relationships, the relevant field is `parent_id`.
                col_to_use = (
                    "collection_id"
                    if search_type == "communities"
                    else "parent_id"
                )

                if isinstance(value, dict):
                    op, clause = next(iter(value.items()))
                    if op == "$eq":
                        # single equality => col_to_use = clause
                        parameters.append(str(clause))
                        return f"{col_to_use} = ${len(parameters)}::uuid"
                    elif op in ("$in", "$overlap"):
                        # "col_to_use = ANY($param::uuid[])"
                        array_val = [str(x) for x in clause]
                        parameters.append(array_val)
                        return (
                            f"{col_to_use} = ANY(${len(parameters)}::uuid[])"
                        )
                    # add more if you want, e.g. $ne, $gt, etc.
                else:
                    # direct equality scenario: "collection_ids": "some-uuid"
                    parameters.append(str(value))
                    return f"{col_to_use} = ${len(parameters)}::uuid"

            # ----------------------------------------------------------------------
            # 3) If key starts with "metadata.", handle metadata-based filters
            # ----------------------------------------------------------------------
            elif key.startswith("metadata."):
                field = key.split("metadata.")[1]
                if isinstance(value, dict):
                    op, clause = next(iter(value.items()))
                    if op == "$eq":
                        parameters.append(clause)
                        return f"(metadata->>'{field}') = ${len(parameters)}"
                    elif op == "$ne":
                        parameters.append(clause)
                        return f"(metadata->>'{field}') != ${len(parameters)}"
                    elif op == "$gt":
                        parameters.append(clause)
                        return f"(metadata->>'{field}')::float > ${len(parameters)}::float"
                    # etc...
                else:
                    parameters.append(value)
                    return f"(metadata->>'{field}') = ${len(parameters)}"

            # ----------------------------------------------------------------------
            # 4) Not recognized => return empty so we skip it
            # ----------------------------------------------------------------------
            return ""

        # --------------------------------------------------------------------------
        # 5) parse_filter() is the recursive walker that sees $and/$or or normal fields
        # --------------------------------------------------------------------------
        def parse_filter(fd: dict) -> str:
            filter_conditions = []
            for k, v in fd.items():
                if k == "$and":
                    and_parts = [parse_filter(sub) for sub in v if sub]
                    and_parts = [x for x in and_parts if x.strip()]
                    if and_parts:
                        filter_conditions.append(
                            f"({' AND '.join(and_parts)})"
                        )
                elif k == "$or":
                    or_parts = [parse_filter(sub) for sub in v if sub]
                    or_parts = [x for x in or_parts if x.strip()]
                    if or_parts:
                        filter_conditions.append(f"({' OR '.join(or_parts)})")
                else:
                    c = parse_condition(k, v)
                    if c and c.strip():
                        filter_conditions.append(c)

            if not filter_conditions:
                return ""
            if len(filter_conditions) == 1:
                return filter_conditions[0]
            return " AND ".join(filter_conditions)

        return parse_filter(filter_dict)

    async def get_existing_document_entity_chunk_ids(
        self, document_id: UUID
    ) -> list[str]:
        QUERY = f"""
            SELECT DISTINCT unnest(chunk_ids) AS chunk_id FROM {self._get_table_name("documents_entities")} WHERE parent_id = $1
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

        count_value = "DISTINCT name" if distinct else "*"

        QUERY = f"""
            SELECT COUNT({count_value}) FROM {self._get_table_name(entity_table_name)}
            WHERE {" AND ".join(conditions)}
        """

        return (await self.connection_manager.fetch_query(QUERY, params))[0][
            "count"
        ]

    async def update_entity_descriptions(self, entities: list[Entity]):
        query = f"""
            UPDATE {self._get_table_name("graphs_entities")}
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
    conflict_columns: list[str] | None = None,
    exclude_metadata: list[str] | None = None,
) -> list[UUID]:
    """Bulk insert objects into the specified table using
    jsonb_to_recordset."""

    if conflict_columns is None:
        conflict_columns = []
    if exclude_metadata is None:
        exclude_metadata = []

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
