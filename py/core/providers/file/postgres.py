import io
import logging
from typing import BinaryIO, Optional
from uuid import UUID

import asyncpg

from core.base import FileConfig, R2RException
from core.base.providers import FileProvider
from core.providers.database.postgres import PostgresDBProvider

logger = logging.getLogger(__name__)


class PostgresFileProvider(FileProvider):
    def __init__(self, config: FileConfig, db_provider: PostgresDBProvider):
        super().__init__()
        self.config = config
        self.db_provider = db_provider
        self.pool = None

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._close_connection()

    async def _close_connection(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def initialize(self):
        self.pool = await asyncpg.create_pool(
            self.db_provider.connection_string
        )
        logger.info(
            "File provider successfully connected to Postgres database."
        )

        async with self.pool.acquire() as conn:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "lo";')

        await self.create_table()

    def _get_table_name(self, base_name: str) -> str:
        return f"{base_name}"

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
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(query)

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
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    query,
                    document_id,
                    file_name,
                    file_oid,
                    file_size,
                    file_type,
                )

    async def store_file(
        self, document_id, file_name, file_content: io.BytesIO, file_type=None
    ):
        file_size = file_content.getbuffer().nbytes
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                oid = await conn.fetchval("SELECT lo_create(0)")
                await self._write_lobject(conn, oid, file_content)
                await self.upsert_file(
                    document_id, file_name, oid, file_size, file_type
                )

    async def _write_lobject(self, conn, oid, file_content):
        # Open the large object
        lobject = await conn.fetchval(
            "SELECT lo_open($1, $2)", oid, 0x20000
        )  # 0x20000 is INV_WRITE flag

        try:
            # Write the content in chunks
            chunk_size = 8192  # 8 KB chunks
            while True:
                chunk = file_content.read(chunk_size)
                if not chunk:
                    break
                await conn.execute("SELECT lowrite($1, $2)", lobject, chunk)

            # Close the large object
            await conn.execute("SELECT lo_close($1)", lobject)

        except Exception as e:
            # Handle exceptions, rollback the transaction if necessary
            await conn.execute(
                "SELECT lo_unlink($1)", oid
            )  # Delete the large object
            raise R2RException(
                status_code=500,
                message=f"Failed to write to large object: {e}",
            )

    async def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        query = f"""
        SELECT file_name, file_oid, file_size
        FROM {self._get_table_name('file_storage')}
        WHERE document_id = $1
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                result = await conn.fetchrow(query, document_id)
                if not result:
                    raise R2RException(
                        status_code=404,
                        message=f"File for document {document_id} not found",
                    )
                file_name, oid, file_size = result
                file_content = await self._read_lobject(conn, oid)
                return file_name, io.BytesIO(file_content), file_size

    async def _read_lobject(self, conn, oid: int) -> bytes:
        file_data = io.BytesIO()
        chunk_size = 8192

        async with conn.transaction():
            try:
                # Check if the large object exists before opening
                lo_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_largeobject WHERE loid = $1)",
                    oid,
                )
                if not lo_exists:
                    raise R2RException(
                        status_code=404,
                        message=f"Large object {oid} not found.",
                    )

                # Open the large object and fetch its descriptor
                lobject = await conn.fetchval(
                    "SELECT lo_open($1, 262144)", oid
                )  # INV_READ

                # Ensure the descriptor is valid before reading
                if lobject is None:
                    raise R2RException(
                        status_code=404,
                        message=f"Failed to open large object {oid}.",
                    )

                # Read the large object in chunks
                while True:
                    chunk = await conn.fetchval(
                        "SELECT loread($1, $2)", lobject, chunk_size
                    )
                    if not chunk:
                        break
                    file_data.write(chunk)
            except asyncpg.exceptions.UndefinedObjectError as e:
                # Handle large object not found
                raise R2RException(
                    status_code=404,
                    message=f"Failed to read large object {oid}: {e}",
                )
            finally:
                # Always close the large object
                await conn.execute("SELECT lo_close($1)", lobject)

        return file_data.getvalue()

    async def delete_file(self, document_id: UUID) -> bool:
        query = f"""
        SELECT file_oid FROM {self._get_table_name('file_storage')}
        WHERE document_id = $1
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                result = await conn.fetchval(query, document_id)
                if not result:
                    raise R2RException(
                        status_code=404,
                        message=f"File for document {document_id} not found",
                    )
                oid = result
                await self._delete_lobject(conn, oid)

                delete_query = f"""
                DELETE FROM {self._get_table_name('file_storage')}
                WHERE document_id = $1
                """
                await conn.execute(delete_query, document_id)
        return True

    async def _delete_lobject(self, conn, oid: int) -> None:
        await conn.execute("SELECT lo_unlink($1)", oid)

    # Implementation of get_files_overview
    async def get_files_overview(
        self,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        conditions = []
        params = []

        if filter_document_ids:
            conditions.append("document_id = ANY($1)")
            params.append(filter_document_ids)

        if filter_file_names:
            conditions.append("file_name = ANY($2)")
            params.append(filter_file_names)

        query = f"""
        SELECT document_id, file_name, file_oid, file_size, file_type, created_at, updated_at
        FROM {self._get_table_name('file_storage')}
        """

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC OFFSET $3 LIMIT $4"
        params.extend([offset, limit])

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                results = await conn.fetch(query, *params)

        if not results:
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
