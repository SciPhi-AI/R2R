from io import BytesIO
from typing import Optional
from uuid import UUID, uuid4

from core.base import DatabaseProvider

from .base import DatabaseMixin


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
        self.execute_query(query)

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
        self.execute_query(query, file_info.convert_to_db_entry())

    def store_file(
        self,
        file_name: str,
        file_content: BytesIO,
        file_type: Optional[str] = None,
    ) -> UUID:
        file_id = uuid4()
        file_size = file_content.getbuffer().nbytes

        with self.vx.cursor() as cur:
            # Create a Large Object
            lobj = self.vx.lobject(mode="wb")
            oid = lobj.oid

            # Write the file content to the Large Object
            lobj.write(file_content.read())
            lobj.close()

        file_info = FileInfo(
            id=file_id,
            file_name=file_name,
            file_oid=oid,
            file_size=file_size,
            file_type=file_type,
            created_at=None,  # Let the database set these
            updated_at=None,
        )
        self.upsert_file(file_info)

        return file_id

    def retrieve_file(
        self, file_id: UUID
    ) -> Optional[tuple[str, BytesIO, int]]:
        query = f"""
        SELECT file_name, file_oid, file_size
        FROM {self._get_table_name('file_storage')}
        WHERE file_id = :file_id
        """
        result = self.execute_query(query, {"file_id": file_id}).fetchone()

        if result is None:
            return None

        file_name, oid, file_size = result
        lobj = self.vx.lobject(oid=oid, mode="rb")
        file_content = lobj.read()
        lobj.close()

        return file_name, BytesIO(file_content), file_size

    def delete_file(self, file_id: UUID) -> bool:
        query = f"""
        DELETE FROM {self._get_table_name('file_storage')}
        WHERE file_id = :file_id
        RETURNING file_oid
        """
        result = self.execute_query(query, {"file_id": file_id}).fetchone()

        if result is None:
            return False

        oid = result[0]
        self.vx.lobject(oid=oid).unlink()

        return True

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
            conditions.append("file_id = ANY(:file_ids)")
            params["file_ids"] = filter_file_ids

        if filter_file_names:
            conditions.append("file_name = ANY(:file_names)")
            params["file_names"] = filter_file_names

        query = f"""
            SELECT file_id, file_name, file_oid, file_size, file_type, created_at, updated_at
            FROM {self._get_table_name('file_storage')}
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        limit_clause = "" if limit == -1 else "LIMIT :limit"
        query += f"""
            ORDER BY created_at DESC
            OFFSET :offset
            {limit_clause}
        """

        results = self.execute_query(query, params).fetchall()
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
