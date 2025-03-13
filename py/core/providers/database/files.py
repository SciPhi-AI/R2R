import io
import logging
from datetime import datetime
from io import BytesIO
from typing import BinaryIO, Optional
from uuid import UUID
from zipfile import ZipFile

import asyncpg
from fastapi import HTTPException

from core.base import Handler, R2RException

from .base import PostgresConnectionManager

logger = logging.getLogger()


class PostgresFilesHandler(Handler):
    """PostgreSQL implementation of the FileHandler."""

    TABLE_NAME = "files"

    connection_manager: PostgresConnectionManager

    async def create_tables(self) -> None:
        """Create the necessary tables for file storage."""
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresFilesHandler.TABLE_NAME)} (
            document_id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            oid OID NOT NULL,
            size BIGINT NOT NULL,
            type TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- Create trigger for updating the updated_at timestamp
        CREATE OR REPLACE FUNCTION {self.project_name}.update_files_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS update_files_updated_at
        ON {self._get_table_name(PostgresFilesHandler.TABLE_NAME)};

        CREATE TRIGGER update_files_updated_at
            BEFORE UPDATE ON {self._get_table_name(PostgresFilesHandler.TABLE_NAME)}
            FOR EACH ROW
            EXECUTE FUNCTION {self.project_name}.update_files_updated_at();
        """
        await self.connection_manager.execute_query(query)

    async def upsert_file(
        self,
        document_id: UUID,
        file_name: str,
        file_oid: int,
        file_size: int,
        file_type: Optional[str] = None,
    ) -> None:
        """Add or update a file entry in storage."""
        query = f"""
        INSERT INTO {self._get_table_name(PostgresFilesHandler.TABLE_NAME)}
        (document_id, name, oid, size, type)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (document_id) DO UPDATE SET
            name = EXCLUDED.name,
            oid = EXCLUDED.oid,
            size = EXCLUDED.size,
            type = EXCLUDED.type,
            updated_at = NOW();
        """
        await self.connection_manager.execute_query(
            query, [document_id, file_name, file_oid, file_size, file_type]
        )

    async def store_file(
        self,
        document_id: UUID,
        file_name: str,
        file_content: io.BytesIO,
        file_type: Optional[str] = None,
    ) -> None:
        """Store a new file in the database."""
        size = file_content.getbuffer().nbytes

        async with (
            self.connection_manager.pool.get_connection() as conn  # type: ignore
        ):
            async with conn.transaction():
                oid = await conn.fetchval("SELECT lo_create(0)")
                await self._write_lobject(conn, oid, file_content)
                await self.upsert_file(
                    document_id, file_name, oid, size, file_type
                )

    async def _write_lobject(
        self, conn, oid: int, file_content: io.BytesIO
    ) -> None:
        """Write content to a large object."""
        lobject = await conn.fetchval("SELECT lo_open($1, $2)", oid, 0x20000)

        try:
            chunk_size = 8192  # 8 KB chunks
            while True:
                if chunk := file_content.read(chunk_size):
                    await conn.execute(
                        "SELECT lowrite($1, $2)", lobject, chunk
                    )
                else:
                    break

            await conn.execute("SELECT lo_close($1)", lobject)

        except Exception as e:
            await conn.execute("SELECT lo_unlink($1)", oid)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to write to large object: {e}",
            ) from e

    async def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        """Retrieve a file from storage."""
        query = f"""
        SELECT name, oid, size
        FROM {self._get_table_name(PostgresFilesHandler.TABLE_NAME)}
        WHERE document_id = $1
        """

        result = await self.connection_manager.fetchrow_query(
            query, [document_id]
        )
        if not result:
            raise R2RException(
                status_code=404,
                message=f"File for document {document_id} not found",
            )

        file_name, oid, size = (
            result["name"],
            result["oid"],
            result["size"],
        )

        async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
            file_content = await self._read_lobject(conn, oid)
            return file_name, io.BytesIO(file_content), size

    async def retrieve_files_as_zip(
        self,
        document_ids: Optional[list[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[str, BinaryIO, int]:
        """Retrieve multiple files and return them as a zip file."""

        query = f"""
        SELECT document_id, name, oid, size
        FROM {self._get_table_name(PostgresFilesHandler.TABLE_NAME)}
        WHERE 1=1
        """
        params: list = []

        if document_ids:
            query += f" AND document_id = ANY(${len(params) + 1})"
            params.append([str(doc_id) for doc_id in document_ids])

        if start_date:
            query += f" AND created_at >= ${len(params) + 1}"
            params.append(start_date)

        if end_date:
            query += f" AND created_at <= ${len(params) + 1}"
            params.append(end_date)

        query += " ORDER BY created_at DESC"

        results = await self.connection_manager.fetch_query(query, params)

        if not results:
            raise R2RException(
                status_code=404,
                message="No files found matching the specified criteria",
            )

        zip_buffer = BytesIO()
        total_size = 0

        async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
            with ZipFile(zip_buffer, "w") as zip_file:
                for record in results:
                    file_content = await self._read_lobject(
                        conn, record["oid"]
                    )

                    zip_file.writestr(record["name"], file_content)
                    total_size += record["size"]

        zip_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"files_export_{timestamp}.zip"

        return zip_filename, zip_buffer, zip_buffer.getbuffer().nbytes

    async def _read_lobject(self, conn, oid: int) -> bytes:
        """Read content from a large object."""
        file_data = io.BytesIO()
        chunk_size = 8192

        async with conn.transaction():
            try:
                lo_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_largeobject_metadata WHERE oid = $1);",
                    oid,
                )
                if not lo_exists:
                    raise R2RException(
                        status_code=404,
                        message=f"Large object {oid} not found.",
                    )

                lobject = await conn.fetchval(
                    "SELECT lo_open($1, 262144)", oid
                )

                if lobject is None:
                    raise R2RException(
                        status_code=404,
                        message=f"Failed to open large object {oid}.",
                    )

                while True:
                    chunk = await conn.fetchval(
                        "SELECT loread($1, $2)", lobject, chunk_size
                    )
                    if not chunk:
                        break
                    file_data.write(chunk)
            except asyncpg.exceptions.UndefinedObjectError:
                raise R2RException(
                    status_code=404,
                    message=f"Failed to read large object {oid}",
                ) from None
            finally:
                await conn.execute("SELECT lo_close($1)", lobject)

        return file_data.getvalue()

    async def delete_file(self, document_id: UUID) -> bool:
        """Delete a file from storage."""
        query = f"""
        SELECT oid FROM {self._get_table_name(PostgresFilesHandler.TABLE_NAME)}
        WHERE document_id = $1
        """

        async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
            async with conn.transaction():
                oid = await conn.fetchval(query, document_id)
                if not oid:
                    raise R2RException(
                        status_code=404,
                        message=f"File for document {document_id} not found",
                    )

                await self._delete_lobject(conn, oid)

                delete_query = f"""
                DELETE FROM {self._get_table_name(PostgresFilesHandler.TABLE_NAME)}
                WHERE document_id = $1
                """
                await conn.execute(delete_query, document_id)

        return True

    async def _delete_lobject(self, conn, oid: int) -> None:
        """Delete a large object."""
        await conn.execute("SELECT lo_unlink($1)", oid)

    async def get_files_overview(
        self,
        offset: int,
        limit: int,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
    ) -> list[dict]:
        """Get an overview of stored files."""
        conditions = []
        params: list[str | list[str] | int] = []
        query = f"""
        SELECT document_id, name, oid, size, type, created_at, updated_at
        FROM {self._get_table_name(PostgresFilesHandler.TABLE_NAME)}
        """

        if filter_document_ids:
            conditions.append(f"document_id = ANY(${len(params) + 1})")
            params.append([str(doc_id) for doc_id in filter_document_ids])

        if filter_file_names:
            conditions.append(f"name = ANY(${len(params) + 1})")
            params.append(filter_file_names)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY created_at DESC OFFSET ${len(params) + 1} LIMIT ${len(params) + 2}"
        params.extend([offset, limit])

        results = await self.connection_manager.fetch_query(query, params)

        if not results:
            raise R2RException(
                status_code=404,
                message="No files found with the given filters",
            )

        return [
            {
                "document_id": row["document_id"],
                "file_name": row["name"],
                "file_oid": row["oid"],
                "file_size": row["size"],
                "file_type": row["type"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in results
        ]
