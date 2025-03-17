import csv
import json
import logging
import tempfile
from typing import IO, Any, Optional
from uuid import UUID, uuid4

from asyncpg.exceptions import UniqueViolationError
from fastapi import HTTPException

from core.base import (
    DatabaseConfig,
    GraphExtractionStatus,
    Handler,
    R2RException,
    generate_default_user_collection_id,
)
from core.base.abstractions import (
    DocumentResponse,
    DocumentType,
    IngestionStatus,
)
from core.base.api.models import CollectionResponse

from .base import PostgresConnectionManager

logger = logging.getLogger()


class PostgresCollectionsHandler(Handler):
    TABLE_NAME = "collections"

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        config: DatabaseConfig,
    ):
        self.config = config
        super().__init__(project_name, connection_manager)

    async def create_tables(self) -> None:
        # 1. Create the table if it does not exist.
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresCollectionsHandler.TABLE_NAME)} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            owner_id UUID,
            name TEXT NOT NULL,
            description TEXT,
            graph_sync_status TEXT DEFAULT 'pending',
            graph_cluster_status TEXT DEFAULT 'pending',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            user_count INT DEFAULT 0,
            document_count INT DEFAULT 0
        );
        """
        await self.connection_manager.execute_query(create_table_query)

        # 2. Check for duplicate rows that would violate the uniqueness constraint.
        check_duplicates_query = f"""
        SELECT owner_id, name, COUNT(*) AS cnt
        FROM {self._get_table_name(PostgresCollectionsHandler.TABLE_NAME)}
        GROUP BY owner_id, name
        HAVING COUNT(*) > 1
        """
        duplicates = await self.connection_manager.fetch_query(
            check_duplicates_query
        )
        if duplicates:
            logger.warning(
                "Cannot add unique constraint (owner_id, name) because duplicates exist. "
                "Please resolve duplicates first. Found duplicates: %s",
                duplicates,
            )
            return  # or raise an exception, depending on your use case

        # 3. Parse the qualified table name into schema and table.
        qualified_table = self._get_table_name(
            PostgresCollectionsHandler.TABLE_NAME
        )
        if "." in qualified_table:
            schema, table = qualified_table.split(".", 1)
        else:
            schema = "public"
            table = qualified_table

        # 4. Add the unique constraint if it does not already exist.
        alter_table_constraint = f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON c.conrelid = t.oid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE t.relname = '{table}'
                AND n.nspname = '{schema}'
                AND c.conname = 'unique_owner_collection_name'
            ) THEN
                ALTER TABLE {qualified_table}
                ADD CONSTRAINT unique_owner_collection_name
                UNIQUE (owner_id, name);
            END IF;
        END;
        $$;
        """
        await self.connection_manager.execute_query(alter_table_constraint)

    async def collection_exists(self, collection_id: UUID) -> bool:
        """Check if a collection exists."""
        query = f"""
            SELECT 1 FROM {self._get_table_name(PostgresCollectionsHandler.TABLE_NAME)}
            WHERE id = $1
        """
        result = await self.connection_manager.fetchrow_query(
            query, [collection_id]
        )
        return result is not None

    async def create_collection(
        self,
        owner_id: UUID,
        name: Optional[str] = None,
        description: str | None = None,
        collection_id: Optional[UUID] = None,
    ) -> CollectionResponse:
        if not name and not collection_id:
            name = self.config.default_collection_name
            collection_id = generate_default_user_collection_id(owner_id)

        query = f"""
            INSERT INTO {self._get_table_name(PostgresCollectionsHandler.TABLE_NAME)}
            (id, owner_id, name, description)
            VALUES ($1, $2, $3, $4)
            RETURNING id, owner_id, name, description, graph_sync_status, graph_cluster_status, created_at, updated_at
        """
        params = [
            collection_id or uuid4(),
            owner_id,
            name,
            description,
        ]

        try:
            result = await self.connection_manager.fetchrow_query(
                query=query,
                params=params,
            )
            if not result:
                raise R2RException(
                    status_code=404, message="Collection not found"
                )

            return CollectionResponse(
                id=result["id"],
                owner_id=result["owner_id"],
                name=result["name"],
                description=result["description"],
                graph_cluster_status=result["graph_cluster_status"],
                graph_sync_status=result["graph_sync_status"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
                user_count=0,
                document_count=0,
            )
        except UniqueViolationError:
            raise R2RException(
                message="Collection with this ID already exists",
                status_code=409,
            ) from None
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while creating the collection: {e}",
            ) from e

    async def update_collection(
        self,
        collection_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> CollectionResponse:
        """Update an existing collection."""
        if not await self.collection_exists(collection_id):
            raise R2RException(status_code=404, message="Collection not found")

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
            WITH updated_collection AS (
                UPDATE {self._get_table_name(PostgresCollectionsHandler.TABLE_NAME)}
                SET {", ".join(update_fields)}
                WHERE id = ${param_index}
                RETURNING id, owner_id, name, description, graph_sync_status, graph_cluster_status, created_at, updated_at
            )
            SELECT
                uc.*,
                COUNT(DISTINCT u.id) FILTER (WHERE u.id IS NOT NULL) as user_count,
                COUNT(DISTINCT d.id) FILTER (WHERE d.id IS NOT NULL) as document_count
            FROM updated_collection uc
            LEFT JOIN {self._get_table_name("users")} u ON uc.id = ANY(u.collection_ids)
            LEFT JOIN {self._get_table_name("documents")} d ON uc.id = ANY(d.collection_ids)
            GROUP BY uc.id, uc.owner_id, uc.name, uc.description, uc.graph_sync_status, uc.graph_cluster_status, uc.created_at, uc.updated_at
        """
        try:
            result = await self.connection_manager.fetchrow_query(
                query, params
            )
            if not result:
                raise R2RException(
                    status_code=404, message="Collection not found"
                )

            return CollectionResponse(
                id=result["id"],
                owner_id=result["owner_id"],
                name=result["name"],
                description=result["description"],
                graph_sync_status=result["graph_sync_status"],
                graph_cluster_status=result["graph_cluster_status"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
                user_count=result["user_count"],
                document_count=result["document_count"],
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while updating the collection: {e}",
            ) from e

    async def delete_collection_relational(self, collection_id: UUID) -> None:
        # Remove collection_id from users
        user_update_query = f"""
            UPDATE {self._get_table_name("users")}
            SET collection_ids = array_remove(collection_ids, $1)
            WHERE $1 = ANY(collection_ids)
        """
        await self.connection_manager.execute_query(
            user_update_query, [collection_id]
        )

        # Remove collection_id from documents
        document_update_query = f"""
            WITH updated AS (
                UPDATE {self._get_table_name("documents")}
                SET collection_ids = array_remove(collection_ids, $1)
                WHERE $1 = ANY(collection_ids)
                RETURNING 1
            )
            SELECT COUNT(*) AS affected_rows FROM updated
        """
        await self.connection_manager.fetchrow_query(
            document_update_query, [collection_id]
        )

        # Delete the collection
        delete_query = f"""
            DELETE FROM {self._get_table_name(PostgresCollectionsHandler.TABLE_NAME)}
            WHERE id = $1
            RETURNING id
        """
        deleted = await self.connection_manager.fetchrow_query(
            delete_query, [collection_id]
        )

        if not deleted:
            raise R2RException(status_code=404, message="Collection not found")

    async def documents_in_collection(
        self, collection_id: UUID, offset: int, limit: int
    ) -> dict[str, list[DocumentResponse] | int]:
        """Get all documents in a specific collection with pagination.

        Args:
            collection_id (UUID): The ID of the collection to get documents from.
            offset (int): The number of documents to skip.
            limit (int): The maximum number of documents to return.
        Returns:
            List[DocumentResponse]: A list of DocumentResponse objects representing the documents in the collection.
        Raises:
            R2RException: If the collection doesn't exist.
        """
        if not await self.collection_exists(collection_id):
            raise R2RException(status_code=404, message="Collection not found")
        query = f"""
            SELECT d.id, d.owner_id, d.type, d.metadata, d.title, d.version,
                d.size_in_bytes, d.ingestion_status, d.extraction_status, d.created_at, d.updated_at, d.summary,
                COUNT(*) OVER() AS total_entries
            FROM {self._get_table_name("documents")} d
            WHERE $1 = ANY(d.collection_ids)
            ORDER BY d.created_at DESC
            OFFSET $2
        """

        conditions = [collection_id, offset]
        if limit != -1:
            query += " LIMIT $3"
            conditions.append(limit)

        results = await self.connection_manager.fetch_query(query, conditions)
        documents = [
            DocumentResponse(
                id=row["id"],
                collection_ids=[collection_id],
                owner_id=row["owner_id"],
                document_type=DocumentType(row["type"]),
                metadata=json.loads(row["metadata"]),
                title=row["title"],
                version=row["version"],
                size_in_bytes=row["size_in_bytes"],
                ingestion_status=IngestionStatus(row["ingestion_status"]),
                extraction_status=GraphExtractionStatus(
                    row["extraction_status"]
                ),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                summary=row["summary"],
            )
            for row in results
        ]
        total_entries = results[0]["total_entries"] if results else 0

        return {"results": documents, "total_entries": total_entries}

    async def get_collections_overview(
        self,
        offset: int,
        limit: int,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_collection_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[CollectionResponse] | int]:
        conditions = []
        params: list[Any] = []
        param_index = 1

        if filter_user_ids:
            conditions.append(f"""
                c.id IN (
                    SELECT unnest(collection_ids)
                    FROM {self.project_name}.users
                    WHERE id = ANY(${param_index})
                )
            """)
            params.append(filter_user_ids)
            param_index += 1

        if filter_document_ids:
            conditions.append(f"""
                c.id IN (
                    SELECT unnest(collection_ids)
                    FROM {self.project_name}.documents
                    WHERE id = ANY(${param_index})
                )
            """)
            params.append(filter_document_ids)
            param_index += 1

        if filter_collection_ids:
            conditions.append(f"c.id = ANY(${param_index})")
            params.append(filter_collection_ids)
            param_index += 1

        where_clause = (
            f"WHERE {' AND '.join(conditions)}" if conditions else ""
        )

        query = f"""
            SELECT
                c.*,
                COUNT(*) OVER() as total_entries
            FROM {self.project_name}.collections c
            {where_clause}
            ORDER BY created_at DESC
            OFFSET ${param_index}
        """
        params.append(offset)
        param_index += 1

        if limit != -1:
            query += f" LIMIT ${param_index}"
            params.append(limit)

        try:
            results = await self.connection_manager.fetch_query(query, params)

            if not results:
                return {"results": [], "total_entries": 0}

            total_entries = results[0]["total_entries"] if results else 0

            collections = [CollectionResponse(**row) for row in results]

            return {"results": collections, "total_entries": total_entries}
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while fetching collections: {e}",
            ) from e

    async def assign_document_to_collection_relational(
        self,
        document_id: UUID,
        collection_id: UUID,
    ) -> UUID:
        """Assign a document to a collection.

        Args:
            document_id (UUID): The ID of the document to assign.
            collection_id (UUID): The ID of the collection to assign the document to.

        Raises:
            R2RException: If the collection doesn't exist, if the document is not found,
                        or if there's a database error.
        """
        try:
            if not await self.collection_exists(collection_id):
                raise R2RException(
                    status_code=404, message="Collection not found"
                )

            # First, check if the document exists
            document_check_query = f"""
                SELECT 1 FROM {self._get_table_name("documents")}
                WHERE id = $1
            """
            document_exists = await self.connection_manager.fetchrow_query(
                document_check_query, [document_id]
            )

            if not document_exists:
                raise R2RException(
                    status_code=404, message="Document not found"
                )

            # If document exists, proceed with the assignment
            assign_query = f"""
                UPDATE {self._get_table_name("documents")}
                SET collection_ids = array_append(collection_ids, $1)
                WHERE id = $2 AND NOT ($1 = ANY(collection_ids))
                RETURNING id
            """
            result = await self.connection_manager.fetchrow_query(
                assign_query, [collection_id, document_id]
            )

            if not result:
                # Document exists but was already assigned to the collection
                raise R2RException(
                    status_code=409,
                    message="Document is already assigned to the collection",
                )

            update_collection_query = f"""
                UPDATE {self._get_table_name("collections")}
                SET document_count = document_count + 1
                WHERE id = $1
            """
            await self.connection_manager.execute_query(
                query=update_collection_query, params=[collection_id]
            )

            return collection_id

        except R2RException:
            # Re-raise R2RExceptions as they are already handled
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error '{e}' occurred while assigning the document to the collection",
            ) from e

    async def remove_document_from_collection_relational(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        """Remove a document from a collection.

        Args:
            document_id (UUID): The ID of the document to remove.
            collection_id (UUID): The ID of the collection to remove the document from.

        Raises:
            R2RException: If the collection doesn't exist or if the document is not in the collection.
        """
        if not await self.collection_exists(collection_id):
            raise R2RException(status_code=404, message="Collection not found")

        query = f"""
            UPDATE {self._get_table_name("documents")}
            SET collection_ids = array_remove(collection_ids, $1)
            WHERE id = $2 AND $1 = ANY(collection_ids)
            RETURNING id
        """
        result = await self.connection_manager.fetchrow_query(
            query, [collection_id, document_id]
        )

        if not result:
            raise R2RException(
                status_code=404,
                message="Document not found in the specified collection",
            )

        await self.decrement_collection_document_count(
            collection_id=collection_id
        )

    async def decrement_collection_document_count(
        self, collection_id: UUID, decrement_by: int = 1
    ) -> None:
        """Decrement the document count for a collection.

        Args:
            collection_id (UUID): The ID of the collection to update
            decrement_by (int): Number to decrease the count by (default: 1)
        """
        collection_query = f"""
            UPDATE {self._get_table_name("collections")}
            SET document_count = document_count - $1
            WHERE id = $2
        """
        await self.connection_manager.execute_query(
            collection_query, [decrement_by, collection_id]
        )

    async def export_to_csv(
        self,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        """Creates a CSV file from the PostgreSQL data and returns the path to
        the temp file."""
        valid_columns = {
            "id",
            "owner_id",
            "name",
            "description",
            "graph_sync_status",
            "graph_cluster_status",
            "created_at",
            "updated_at",
            "user_count",
            "document_count",
        }

        if not columns:
            columns = list(valid_columns)
        elif invalid_cols := set(columns) - valid_columns:
            raise ValueError(f"Invalid columns: {invalid_cols}")

        select_stmt = f"""
            SELECT
                id::text,
                owner_id::text,
                name,
                description,
                graph_sync_status,
                graph_cluster_status,
                to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at,
                user_count,
                document_count
            FROM {self._get_table_name(self.TABLE_NAME)}
        """

        params = []
        if filters:
            conditions = []
            param_index = 1

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
                                "owner_id": row[1],
                                "name": row[2],
                                "description": row[3],
                                "graph_sync_status": row[4],
                                "graph_cluster_status": row[5],
                                "created_at": row[6],
                                "updated_at": row[7],
                                "user_count": row[8],
                                "document_count": row[9],
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

    async def get_collection_by_name(
        self, owner_id: UUID, name: str
    ) -> Optional[CollectionResponse]:
        """Fetch a collection by owner_id + name combination.

        Return None if not found.
        """
        query = f"""
            SELECT
                id, owner_id, name, description, graph_sync_status,
                graph_cluster_status, created_at, updated_at, user_count, document_count
            FROM {self._get_table_name(PostgresCollectionsHandler.TABLE_NAME)}
            WHERE owner_id = $1 AND name = $2
            LIMIT 1
        """
        result = await self.connection_manager.fetchrow_query(
            query, [owner_id, name]
        )
        if not result:
            raise R2RException(
                status_code=404,
                message="No collection found with the specified name",
            )
        return CollectionResponse(
            id=result["id"],
            owner_id=result["owner_id"],
            name=result["name"],
            description=result["description"],
            graph_sync_status=result["graph_sync_status"],
            graph_cluster_status=result["graph_cluster_status"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            user_count=result["user_count"],
            document_count=result["document_count"],
        )
