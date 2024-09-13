import io
import logging
from contextlib import contextmanager
from typing import Any, BinaryIO, Callable, Iterator, Optional, Union
from uuid import UUID

from psycopg2 import Error as PostgresError
from psycopg2.extensions import connection as pg_connection
from psycopg2.extensions import lobject
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from core.base import FileConfig, R2RException
from core.base.providers import FileProvider
from core.providers.database.postgres import PostgresDBProvider

logger = logging.getLogger(__name__)


class PostgresFileProvider(FileProvider):
    def __init__(self, config: FileConfig, db_provider: PostgresDBProvider):
        super().__init__()
        self.config = config
        self.db_provider = db_provider
        self.vx = db_provider.vx
        self.create_table()

    def _get_table_name(self, base_name: str) -> str:
        return f"{base_name}"

    @contextmanager
    def get_session(self) -> Iterator[Any]:
        with self.vx.Session() as sess:
            yield sess

    def execute_query(
        self, query: Union[str, text], params: Optional[dict[str, Any]] = None
    ) -> Any:
        with self.get_session() as sess:
            if isinstance(query, str):
                query = text(query)
            result = sess.execute(query, params or {})
            sess.commit()
            return result

    @contextmanager
    def get_connection(self) -> Iterator[pg_connection]:
        with self.get_session() as sess:
            connection = sess.connection().connection
            try:
                yield connection
            finally:
                connection.close()

    def execute_with_connection(
        self, operation: Callable[[pg_connection], Any]
    ) -> Any:
        with self.get_connection() as conn:
            return operation(conn)

    @contextmanager
    def get_lobject(self, oid: int = 0, mode: str = "rb") -> Iterator[lobject]:
        with self.get_connection() as conn:
            lobj = conn.lobject(oid, mode)
            try:
                yield lobj
            finally:
                lobj.close()

    def read_lob(self, oid: int) -> bytes:
        with self.get_lobject(oid, "rb") as lobj:
            return lobj.read()

    def delete_lob(self, oid: int) -> None:
        with self.get_connection() as conn:
            conn.lobject(oid, "wb").unlink()

    def execute_lob_query(
        self,
        query: Union[str, TextClause],
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if isinstance(query, TextClause):
                    query = query.text
                elif not isinstance(query, str):
                    raise TypeError(
                        "Query must be a string or SQLAlchemy TextClause object"
                    )
                cur.execute(query, params or {})
                return cur.fetchone()

    def create_table(self):
        query = text(
            f"""
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
        )
        try:
            self.execute_query(query)
            logger.info(
                f"Created table {self._get_table_name('file_storage')}"
            )
        except PostgresError as e:
            logger.error(f"Failed to create table: {e}")
            raise

    def upsert_file(
        self,
        document_id: UUID,
        file_name: str,
        file_oid: int,
        file_size: int,
        file_type: Optional[str] = None,
    ) -> None:
        query = text(
            f"""
        INSERT INTO {self._get_table_name('file_storage')}
        (document_id, file_name, file_oid, file_size, file_type)
        VALUES (:document_id, :file_name, :file_oid, :file_size, :file_type)
        ON CONFLICT (document_id) DO UPDATE SET
            file_name = EXCLUDED.file_name,
            file_oid = EXCLUDED.file_oid,
            file_size = EXCLUDED.file_size,
            file_type = EXCLUDED.file_type,
            updated_at = NOW();
        """
        )
        result = self.execute_query(
            query,
            {
                "document_id": document_id,
                "file_name": file_name,
                "file_oid": file_oid,
                "file_size": file_size,
                "file_type": file_type,
            },
        )
        if not result:
            raise R2RException(
                status_code=500,
                message=f"Failed to upsert file for document {document_id}",
            )

    def store_file(self, document_id, file_name, file_content, file_type=None):
        file_size = file_content.getbuffer().nbytes

        try:
            with self.vx.Session() as session:
                conn = session.connection().connection
                with conn.cursor() as cur:
                    cur.execute("BEGIN")
                    try:
                        cur.execute("SELECT lo_create(0)")
                        oid = cur.fetchone()[0]
                        large_obj = conn.lobject(oid, "wb")
                        large_obj.write(file_content.getvalue())
                        large_obj.close()

                        self.upsert_file(
                            document_id, file_name, oid, file_size, file_type
                        )
                        cur.execute("COMMIT")
                    except Exception as e:
                        cur.execute("ROLLBACK")
                        raise
        except Exception as e:
            raise R2RException(
                status_code=500,
                message=f"Failed to store file for document {document_id}: {e}",
            ) from e

    def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        query = text(
            f"""
        SELECT file_name, file_oid, file_size
        FROM {self._get_table_name('file_storage')}
        WHERE document_id = %(document_id)s
        """
        )
        result = self.execute_lob_query(query, {"document_id": document_id})
        if not result:
            raise R2RException(
                status_code=404,
                message=f"File for document {document_id} not found",
            )

        file_name, oid, file_size = result
        file_content = self.read_lob(oid)
        return file_name, io.BytesIO(file_content), file_size

    def delete_file(self, document_id: UUID) -> bool:
        query = f"""
        SELECT file_oid FROM {self._get_table_name('file_storage')}
        WHERE document_id = :document_id
        """
        result = self.execute_lob_query(query, {"document_id": document_id})

        if result is None:
            raise R2RException(
                status_code=404,
                message=f"File for document {document_id} not found",
            )

        oid = result[0]
        self.delete_lob(oid)

        delete_query = f"""
        DELETE FROM {self._get_table_name('file_storage')}
        WHERE document_id = :document_id
        """
        self.execute_query(delete_query, {"document_id": document_id})

        return True

    def get_files_overview(
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
            conditions.append("document_id = ANY(:document_ids)")
            params["document_ids"] = filter_document_ids

        if filter_file_names:
            conditions.append("file_name = ANY(:file_names)")
            params["file_names"] = filter_file_names

        query = f"""
            SELECT document_id, file_name, file_oid, file_size, file_type, created_at, updated_at
            FROM {self._get_table_name('file_storage')}
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += """
            ORDER BY created_at DESC
            OFFSET :offset
        """
        if limit != -1:
            query += " LIMIT :limit"

        query = text(query)

        results = self.execute_query(query, params).fetchall()

        if results is None:
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
