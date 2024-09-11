"""
TODO: Adapt to work in a truly async manner.
    Large objects aren't supported in asyncpg as a dedicated API. https://github.com/MagicStack/asyncpg/issues/826
    To work around this, we are forced to use psychopg2, with some workarounds to make it non-blocking.
"""

import io
import logging
from typing import BinaryIO, Optional
from uuid import UUID

import psycopg2
import psycopg2.extras
from fastapi.concurrency import run_in_threadpool
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
        self.conn = None

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await run_in_threadpool(self._close_connection)

    def _close_connection(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    async def initialize(self):
        await run_in_threadpool(self._initialize)

    def _initialize(self):
        self.conn = psycopg2.connect(self.db_provider.connection_string)
        if not self.conn:
            raise R2RException(
                status_code=500,
                message="Failed to initialize file provider database connection.",
            )
        logger.info(
            "File provider successfully connected to Postgres database."
        )
        self.create_table()

    def _get_table_name(self, base_name: str) -> str:
        return f"{base_name}"

    def create_table(self):
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
            with self.conn.cursor() as cursor:
                cursor.execute(query)
                self.conn.commit()
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
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (document_id) DO UPDATE SET
            file_name = EXCLUDED.file_name,
            file_oid = EXCLUDED.file_oid,
            file_size = EXCLUDED.file_size,
            file_type = EXCLUDED.file_type,
            updated_at = NOW();
        """
        params = (document_id, file_name, file_oid, file_size, file_type)
        await run_in_threadpool(self._execute_query, query, params)

    def _execute_query(self, query, params=None):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, params)
                self.conn.commit()
        except PostgresError as e:
            logger.error(f"Query execution failed: {e}")
            raise R2RException(
                status_code=500, message="Database query failed."
            )

    async def store_file(
        self, document_id, file_name, file_content, file_type=None
    ):
        file_size = file_content.getbuffer().nbytes

        try:
            oid = await run_in_threadpool(self._create_lobject)
            await run_in_threadpool(self._write_lobject, oid, file_content)

            await self.upsert_file(
                document_id, file_name, oid, file_size, file_type
            )
        except Exception as e:
            raise R2RException(
                status_code=500,
                message=f"Failed to store file for document {document_id}: {e}",
            ) from e

    def _create_lobject(self):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT lo_create(0)")
            oid = cursor.fetchone()[0]
            self.conn.commit()
            return oid

    def _write_lobject(self, oid, file_content):
        lobj = self.conn.lobject(oid, "wb")
        lobj.write(file_content.getvalue())
        lobj.close()
        self.conn.commit()

    async def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        query = f"""
        SELECT file_name, file_oid, file_size
        FROM {self._get_table_name('file_storage')}
        WHERE document_id = %s
        """
        result = await run_in_threadpool(
            self._execute_fetchrow, query, (document_id,)
        )
        if not result:
            raise R2RException(
                status_code=404,
                message=f"File for document {document_id} not found",
            )

        file_name, oid, file_size = result
        file_content = await run_in_threadpool(self._read_lob, oid)
        return file_name, io.BytesIO(file_content), file_size

    def _execute_fetchrow(self, query, params):
        with self.conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def _read_lob(self, oid: int) -> bytes:
        lobj = self.conn.lobject(oid, "rb")
        file_data = lobj.read()
        lobj.close()
        return file_data

    async def delete_file(self, document_id: UUID) -> bool:
        query = f"""
        SELECT file_oid FROM {self._get_table_name('file_storage')}
        WHERE document_id = %s
        """
        result = await run_in_threadpool(
            self._execute_fetchrow, query, (document_id,)
        )
        if not result:
            raise R2RException(
                status_code=404,
                message=f"File for document {document_id} not found",
            )

        oid = result[0]
        await run_in_threadpool(self._delete_lob, oid)

        delete_query = f"""
        DELETE FROM {self._get_table_name('file_storage')}
        WHERE document_id = %s
        """
        await run_in_threadpool(
            self._execute_query, delete_query, (document_id,)
        )
        return True

    def _delete_lob(self, oid: int) -> None:
        lobj = self.conn.lobject(oid, "wb")
        lobj.unlink()
        lobj.close()

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
            conditions.append("document_id = ANY(%s)")
            params.append(filter_document_ids)

        if filter_file_names:
            conditions.append("file_name = ANY(%s)")
            params.append(filter_file_names)

        query = f"""
        SELECT document_id, file_name, file_oid, file_size, file_type, created_at, updated_at
        FROM {self._get_table_name('file_storage')}
        """

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC OFFSET %s LIMIT %s"
        params.extend([offset, limit])

        results = await run_in_threadpool(self._execute_fetch, query, params)

        if not results:
            raise R2RException(
                status_code=404,
                message="No files found with the given filters",
            )

        return [
            {
                "document_id": row[0],
                "file_name": row[1],
                "file_oid": row[2],
                "file_size": row[3],
                "file_type": row[4],
                "created_at": row[5],
                "updated_at": row[6],
            }
            for row in results
        ]

    def _execute_fetch(self, query, params):
        with self.conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
