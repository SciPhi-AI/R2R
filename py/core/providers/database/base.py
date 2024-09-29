from typing import Any, Optional, Sequence, Union

from sqlalchemy import TextClause, text

from .vecs import Client


# TODO: This should be defined at the mixin, not here
def execute_query(
    vx: Client,
    query: Union[str, TextClause],
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
        self.conditions: list[str] = []
        self.params: dict = {}
        self.select_fields = "*"
        self.operation = "SELECT"
        self.limit_value: Optional[int] = None
        self.insert_data: Optional[dict] = None

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


class DatabaseMixin:
    def get_config(self):
        if hasattr(self, "config"):
            return self.config
        raise AttributeError("Config not set in the provider class")

    def _get_table_name(self, base_name: str) -> str:
        raise NotImplementedError("Subclasses must implement this method")

    def execute_query(
        self,
        query: Union[str, TextClause],
        params: Optional[Union[dict[str, Any], Sequence[Any]]] = None,
    ):
        raise NotImplementedError("Subclasses must implement this method")

    def fetch_query(
        self,
        query: Union[str, TextClause],
        params: Optional[Union[dict[str, Any], Sequence[Any]]] = None,
    ):
        raise NotImplementedError("Subclasses must implement this method")

    def fetchrow_query(
        self,
        query: Union[str, TextClause],
        params: Optional[Union[dict[str, Any], Sequence[Any]]] = None,
    ):
        raise NotImplementedError("Subclasses must implement this method")

    def create_table(self):
        raise NotImplementedError("Subclasses must implement this method")
