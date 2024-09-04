import logging
from io import BytesIO
from typing import BinaryIO, Optional
from uuid import UUID, uuid4

from psycopg2 import Error as PostgresError

from .base import DatabaseMixin

logger = logging.getLogger(__name__)


class FileInfo:
    def __init__(
        self,
        id: UUID,
        file_name: str,
        file_oid: int,
        file_size: int,
        file_type: Optional[str],
        created_at: str,
        updated_at: str,
    ):
        self.id = id
        self.file_name = file_name
        self.file_oid = file_oid
        self.file_size = file_size
        self.file_type = file_type
        self.created_at = created_at
        self.updated_at = updated_at

    def convert_to_db_entry(self):
        return {
            "file_id": self.id,
            "file_name": self.file_name,
            "file_oid": self.file_oid,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class PostgresFileProvider(DatabaseMixin):
    def create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name('file_storage')} (
            file_id UUID PRIMARY KEY,
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
        try:
            self.execute_query(query)
            logger.info(
                f"Created table {self._get_table_name('file_storage')}"
            )
        except PostgresError as e:
            logger.error(f"Failed to create table: {e}")
            raise

    def upsert_file(self, file_info: FileInfo) -> None:
        query = f"""
        INSERT INTO {self._get_table_name('file_storage')}
        (file_id, file_name, file_oid, file_size, file_type, created_at, updated_at)
        VALUES (:file_id, :file_name, :file_oid, :file_size, :file_type, :created_at, :updated_at)
        ON CONFLICT (file_id) DO UPDATE SET
            file_name = EXCLUDED.file_name,
            file_oid = EXCLUDED.file_oid,
            file_size = EXCLUDED.file_size,
            file_type = EXCLUDED.file_type,
            updated_at = EXCLUDED.updated_at;
        """
        try:
            self.execute_query(query, file_info.convert_to_db_entry())
            logger.info(f"Upserted file {file_info.id}")
        except PostgresError as e:
            logger.error(f"Failed to upsert file {file_info.id}: {e}")
            raise

    def store_file(
        self,
        file_name: str,
        file_content: BytesIO,
        file_type: Optional[str] = None,
    ) -> UUID:
        file_id = uuid4()
        file_size = file_content.getbuffer().nbytes

        try:
            with self.vx.cursor() as cur:
                with self.vx.lobject(mode="wb") as lobj:
                    oid = lobj.oid
                    lobj.write(file_content.read())

            file_info = FileInfo(
                id=file_id,
                file_name=file_name,
                file_oid=oid,
                file_size=file_size,
                file_type=file_type,
                created_at=None,
                updated_at=None,
            )
            self.upsert_file(file_info)

            logger.info(f"Stored file {file_id} successfully")
            return file_id
        except PostgresError as e:
            logger.error(f"Failed to store file {file_name}: {e}")
            raise

    def retrieve_file(
        self, file_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        query = f"""
        SELECT file_name, file_oid, file_size
        FROM {self._get_table_name('file_storage')}
        WHERE file_id = %s
        """
        try:
            result = self.execute_query(query, (file_id,)).fetchone()

            if result is None:
                logger.warning(f"File {file_id} not found")
                return None

            file_name, oid, file_size = result

            class LOBjectWrapper:
                def __init__(self, vx, oid):
                    self.vx = vx
                    self.oid = oid
                    self.lobj = None

                def __enter__(self):
                    self.lobj = self.vx.lobject(oid=self.oid, mode="rb")
                    return self.lobj

                def __exit__(self, exc_type, exc_val, exc_tb):
                    if self.lobj:
                        self.lobj.close()

            logger.info(f"Retrieved file {file_id} successfully")
            return file_name, LOBjectWrapper(self.vx, oid), file_size
        except PostgresError as e:
            logger.error(f"Failed to retrieve file {file_id}: {e}")
            raise

    def delete_file(self, file_id: UUID) -> bool:
        try:
            with self.vx.cursor() as cur:
                # First, get the OID
                query = f"""
                SELECT file_oid FROM {self._get_table_name('file_storage')}
                WHERE file_id = %s
                """
                cur.execute(query, (file_id,))
                result = cur.fetchone()

                if result is None:
                    logger.warning(f"File {file_id} not found for deletion")
                    return False

                oid = result[0]

                # Then, delete the large object
                lobj = self.vx.lobject(oid, mode="rb")
                lobj.unlink()

                # Finally, delete the metadata
                query = f"""
                DELETE FROM {self._get_table_name('file_storage')}
                WHERE file_id = %s
                """
                cur.execute(query, (file_id,))

            self.vx.commit()
            logger.info(f"Deleted file {file_id} successfully")
            return True
        except PostgresError as e:
            self.vx.rollback()
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False

    def get_files_overview(
        self,
        filter_file_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[FileInfo]:
        conditions = []
        params = {"offset": offset}
        if limit != -1:
            params["limit"] = limit

        if filter_file_ids:
            conditions.append("file_id = ANY(%s)")
            params["file_ids"] = filter_file_ids

        if filter_file_names:
            conditions.append("file_name = ANY(%s)")
            params["file_names"] = filter_file_names

        query = f"""
            SELECT file_id, file_name, file_oid, file_size, file_type, created_at, updated_at
            FROM {self._get_table_name('file_storage')}
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += """
            ORDER BY created_at DESC
            OFFSET %(offset)s
        """
        if limit != -1:
            query += " LIMIT %(limit)s"

        try:
            results = self.execute_query(query, params).fetchall()
            logger.info(f"Retrieved {len(results)} file overviews")
            return [
                FileInfo(
                    id=row[0],
                    file_name=row[1],
                    file_oid=row[2],
                    file_size=row[3],
                    file_type=row[4],
                    created_at=row[5],
                    updated_at=row[6],
                )
                for row in results
            ]
        except PostgresError as e:
            logger.error(f"Failed to get files overview: {e}")
            raise
