import logging
from io import BytesIO
from typing import BinaryIO, Optional
from uuid import UUID

from psycopg2 import Error as PostgresError
from sqlalchemy import text

from core.base.providers import DatabaseConfig, FileProvider
from core.providers.database.vecs import Client

from .base import DatabaseMixin

logger = logging.getLogger(__name__)


class FileInfo:
    def __init__(
        self,
        document_id: UUID,
        file_name: str,
        file_oid: int,
        file_size: int,
        file_type: Optional[str],
        created_at: str,
        updated_at: str,
    ):
        self.document_id = document_id
        self.file_name = file_name
        self.file_oid = file_oid
        self.file_size = file_size
        self.file_type = file_type
        self.created_at = created_at
        self.updated_at = updated_at

    def convert_to_db_entry(self):
        return {
            "document_id": self.document_id,
            "file_name": self.file_name,
            "file_oid": self.file_oid,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class FileMixin(DatabaseMixin):
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
        CREATE INDEX IF NOT EXISTS idx_file_name_{self.collection_name}
        ON {self._get_table_name('file_storage')} (file_name);
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
        try:
            self.execute_query(
                query,
                {
                    "document_id": document_id,
                    "file_name": file_name,
                    "file_oid": file_oid,
                    "file_size": file_size,
                    "file_type": file_type,
                },
            )
            logger.info(f"Upserted file for document {document_id}")
        except PostgresError as e:
            logger.error(
                f"Failed to upsert file for document {document_id}: {e}"
            )
            raise

    def store_file(
        self,
        document_id: UUID,
        file_name: str,
        file_content: BytesIO,
        file_type: Optional[str] = None,
    ) -> None:
        file_size = file_content.getbuffer().nbytes

        try:
            with self.vx.Session() as sess:
                with sess.begin():
                    conn = sess.connection().connection
                    lobject = conn.lobject(mode="wb")
                    oid = lobject.oid
                    lobject.write(file_content.read())

                self.upsert_file(
                    document_id, file_name, oid, file_size, file_type
                )

            logger.info(f"Stored file for document {document_id} successfully")
        except Exception as e:
            logger.error(
                f"Failed to store file for document {document_id}: {e}"
            )
            raise

    def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        query = text(
            f"""
        SELECT file_name, file_oid, file_size
        FROM {self._get_table_name('file_storage')}
        WHERE document_id = :document_id
        """
        )
        try:
            with self.vx.Session() as sess:
                result = sess.execute(
                    query, {"document_id": document_id}
                ).fetchone()

                if result is None:
                    logger.warning(
                        f"File for document {document_id} not found"
                    )
                    return None

                file_name, oid, file_size = result

                class LOBjectWrapper:
                    def __init__(self, sess, oid):
                        self.sess = sess
                        self.oid = oid
                        self.lobj = None

                    def __enter__(self):
                        conn = self.sess.connection().connection
                        self.lobj = conn.lobject(oid=self.oid, mode="rb")
                        return self.lobj

                    def __exit__(self, exc_type, exc_val, exc_tb):
                        if self.lobj:
                            self.lobj.close()

            logger.info(
                f"Retrieved file for document {document_id} successfully"
            )
            return file_name, LOBjectWrapper(sess, oid), file_size
        except Exception as e:
            logger.error(
                f"Failed to retrieve file for document {document_id}: {e}"
            )
            raise

    def delete_file(self, document_id: UUID) -> bool:
        try:
            with self.vx.Session() as sess:
                with sess.begin():
                    # First, get the OID
                    query = text(
                        f"""
                    SELECT file_oid FROM {self._get_table_name('file_storage')}
                    WHERE document_id = :document_id
                    """
                    )
                    result = sess.execute(
                        query, {"document_id": document_id}
                    ).fetchone()

                    if result is None:
                        logger.warning(
                            f"File for document {document_id} not found for deletion"
                        )
                        return False

                    oid = result[0]

                    # Then, delete the large object
                    conn = sess.connection().connection
                    lobj = conn.lobject(oid, mode="rb")
                    lobj.unlink()

                    # Finally, delete the metadata
                    query = text(
                        f"""
                    DELETE FROM {self._get_table_name('file_storage')}
                    WHERE document_id = :document_id
                    """
                    )
                    sess.execute(query, {"document_id": document_id})

            logger.info(
                f"Deleted file for document {document_id} successfully"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to delete file for document {document_id}: {e}"
            )
            return False

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

        try:
            with self.vx.Session() as sess:
                results = sess.execute(query, params).fetchall()
            logger.info(f"Retrieved {len(results)} file overviews")
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
        except Exception as e:
            logger.error(f"Failed to get files overview: {e}")
            raise


class PostgresFileProvider(FileProvider, FileMixin):
    def __init__(
        self, config: DatabaseConfig, vx: Client, collection_name: str
    ):
        FileProvider.__init__(self, config)
        self.vx = vx
        self.collection_name = collection_name

    def store_file(self, document_id, file_name, file_content, file_type=None):
        return FileMixin.store_file(
            self, document_id, file_name, file_content, file_type
        )

    def retrieve_file(self, document_id):
        return FileMixin.retrieve_file(self, document_id)

    def delete_file(self, document_id):
        return self.delete_file(document_id)

    def get_files_overview(
        self,
        filter_document_ids=None,
        filter_file_names=None,
        offset=0,
        limit=100,
    ):
        return FileMixin.get_files_overview(
            self, filter_document_ids, filter_file_names, offset, limit
        )

    def _get_table_name(self, base_name: str) -> str:
        return f"{base_name}_{self.collection_name}"
