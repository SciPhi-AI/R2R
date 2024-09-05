from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional, Union

from psycopg2.extensions import connection as pg_connection
from sqlalchemy import text

from uuid import UUID

from .vecs import Client


def execute_query(
    vx: Client,
    query: Union[str, text],
    params: Optional[dict[str, Any]] = None,
):
    with vx.Session() as sess:
        if isinstance(query, str):
            query = text(query)
        result = sess.execute(query, params or {})
        sess.commit()
        return result


class QueryBuilder:
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.conditions = []
        self.params = {}
        self.select_fields = "*"
        self.operation = "SELECT"
        self.insert_data = None
        self.limit_value = None

    def select(self, fields: list[str]):
        self.select_fields = ", ".join(fields)
        return self

    def insert(self, data: dict):
        self.operation = "INSERT"
        self.insert_data = data
        return self

    def delete(self):
        self.operation = "DELETE"
        return self

    def where(self, condition: str, **kwargs):
        self.conditions.append(condition)
        self.params.update(kwargs)
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def build(self):
        if self.operation == "SELECT":
            query = f"SELECT {self.select_fields} FROM {self.table_name}"
        elif self.operation == "INSERT":
            columns = ", ".join(self.insert_data.keys())
            values = ", ".join(f":{key}" for key in self.insert_data.keys())
            query = (
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({values})"
            )
            self.params.update(self.insert_data)
        elif self.operation == "DELETE":
            query = f"DELETE FROM {self.table_name}"
        else:
            raise ValueError(f"Unsupported operation: {self.operation}")

        if self.conditions:
            query += " WHERE " + " AND ".join(self.conditions)

        if self.limit_value is not None and self.operation == "SELECT":
            query += f" LIMIT {self.limit_value}"

        return query, self.params
    
    def upsert_file(self, document_id: UUID, file_name: str, file_oid: int, file_size: int, file_type: Optional[str] = None) -> None:
        query_builder = QueryBuilder(self._get_table_name('file_storage'))
        query, params = query_builder.insert({
            "document_id": document_id,
            "file_name": file_name,
            "file_oid": file_oid,
            "file_size": file_size,
            "file_type": file_type
        }).build()
        
        # Add ON CONFLICT clause
        query += " ON CONFLICT (document_id) DO UPDATE SET " \
                "file_name = EXCLUDED.file_name, " \
                "file_oid = EXCLUDED.file_oid, " \
                "file_size = EXCLUDED.file_size, " \
                "file_type = EXCLUDED.file_type, " \
                "updated_at = NOW()"
        
        result = self.execute_query(text(query), params)
        if not result:
            raise R2RException(status_code=500, message=f"Failed to upsert file for document {document_id}")


class DatabaseMixin:
    vx: Client

    def _get_table_name(self, base_name: str) -> str:
        raise NotImplementedError("Subclasses must implement this method")

    @contextmanager
    def get_session(self) -> Iterator[Any]:
        raise NotImplementedError("Subclasses must implement this method")

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

    def create_table(self):
        raise NotImplementedError("Subclasses must implement this method")
