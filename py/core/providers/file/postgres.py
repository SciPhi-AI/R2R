import asyncio
import io
import logging
from contextlib import asynccontextmanager
from typing import Any, BinaryIO, Optional
from uuid import UUID

from psycopg2 import Error as PostgresError

from core.base import FileConfig, R2RException
from core.base.providers import FileProvider
from core.providers.database.postgres import PostgresDBProvider

logger = logging.getLogger(__name__)


class PostgresFileProvider(FileProvider):
    def __init__(self, config: FileConfig, db_provider: PostgresDBProvider):
        super().__init__()
        self.config = config
        self.db_provider = db_provider
        self.conn = db_provider.conn
        asyncio.create_task(self.create_table())

    def _get_table_name(self, base_name: str) -> str:
        return f"{base_name}"

    async def execute_query(
        self, query: str, params: Optional[dict[str, Any]] = None
    ) -> Any:
        return await self.conn.execute(query, *params.values())

    async def execute_fetchrow(
        self, query: str, params: Optional[dict[str, Any]] = None
    ) -> Any:
        return await self.conn.fetchrow(query, *params.values())

    async def execute_fetch(
        self, query: str, params: Optional[dict[str, Any]] = None
    ) -> Any:
        return await self.conn.fetch(query, *params.values())

    @asynccontextmanager
    async def get_connection(self):
        yield self.db_provider.conn  # Directly use the asyncpg connection

    async def create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name('file_storage')} (
            document_id UUID PRIMARY KEY,
            file_name TEXT NOT NULL,
            file_oid OID NOT NULL,
            file_size BIGINT NOT NULL,
            file_type TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        try:
            await self.execute_query(query)
            logger.info(
                f"Created table {self._get_table_name('file_storage')}"
            )
        except PostgresError as e:
            logger.error(f"Failed to create table: {e}")
            raise

    async def upsert_file(
        self,
        document_id: UUID,
        file_name: str,
        file_oid: int,
        file_size: int,
        file_type: Optional[str] = None,
    ) -> None:
        query = f"""
        INSERT INTO {self._get_table_name('file_storage')}
        (document_id, file_name, file_oid, file_size, file_type)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (document_id) DO UPDATE SET
            file_name = EXCLUDED.file_name,
            file_oid = EXCLUDED.file_oid,
            file_size = EXCLUDED.file_size,
            file_type = EXCLUDED.file_type,
            updated_at = NOW();
        """
        params = (document_id, file_name, file_oid, file_size, file_type)
        result = await self.conn.execute(query, *params)
        if not result:
            raise R2RException(
                status_code=500,
                message=f"Failed to upsert file for document {document_id}",
            )

    async def store_file(
        self, document_id, file_name, file_content, file_type=None
    ):
        file_size = file_content.getbuffer().nbytes

        async with self.get_connection() as conn:
            try:
                async with conn.transaction():
                    oid = await conn.fetchval("SELECT lo_create(0)")
                    large_obj = conn.lobject(oid, "wb")
                    large_obj.write(file_content.getvalue())
                    large_obj.close()

                    await self.upsert_file(
                        document_id, file_name, oid, file_size, file_type
                    )
            except Exception as e:
                raise R2RException(
                    status_code=500,
                    message=f"Failed to store file for document {document_id}: {e}",
                ) from e

    async def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        query = f"""
        SELECT file_name, file_oid, file_size
        FROM {self._get_table_name('file_storage')}
        WHERE document_id = $1
        """
        result = await self.execute_fetchrow(
            query, {"document_id": document_id}
        )
        if not result:
            raise R2RException(
                status_code=404,
                message=f"File for document {document_id} not found",
            )

        file_name, oid, file_size = result
        file_content = await self.read_lob(oid)
        return file_name, io.BytesIO(file_content), file_size

    async def read_lob(self, oid: int) -> bytes:
        async with self.get_connection() as conn:
            lobj = conn.lobject(oid, "rb")
            try:
                return lobj.read()
            finally:
                lobj.close()

    async def delete_file(self, document_id: UUID) -> bool:
        query = f"""
        SELECT file_oid FROM {self._get_table_name('file_storage')}
        WHERE document_id = $1
        """
        result = await self.execute_fetchrow(
            query, {"document_id": document_id}
        )
        if result is None:
            raise R2RException(
                status_code=404,
                message=f"File for document {document_id} not found",
            )

        oid = result["file_oid"]
        await self.delete_lob(oid)

        delete_query = f"""
        DELETE FROM {self._get_table_name('file_storage')}
        WHERE document_id = $1
        """
        await self.conn.execute(delete_query, document_id)

        return True

    async def delete_lob(self, oid: int) -> None:
        async with self.get_connection() as conn:
            await conn.lobject(oid, "wb").unlink()

    async def get_files_overview(
        self,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        conditions = []
        params = {"offset": offset}
        if limit != -1:
            params["limit"] = limit

        if filter_document_ids:
            conditions.append("document_id = ANY($1)")
            params["document_ids"] = filter_document_ids

        if filter_file_names:
            conditions.append("file_name = ANY($2)")
            params["file_names"] = filter_file_names

        query = f"""
            SELECT document_id, file_name, file_oid, file_size, file_type, created_at, updated_at
            FROM {self._get_table_name('file_storage')}
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += """
            ORDER BY created_at DESC
            OFFSET $3
        """
        if limit != -1:
            query += " LIMIT $4"

        results = await self.conn.fetch(query, *params.values())

        if results is None:
            raise R2RException(
                status_code=404,
                message="No files found with the given filters",
            )

        return [
            {
                "document_id": row["document_id"],
                "file_name": row["file_name"],
                "file_oid": row["file_oid"],
                "file_size": row["file_size"],
                "file_type": row["file_type"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in results
        ]
