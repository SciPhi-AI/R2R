import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional, Sequence, Union

import asyncpg

logger = logging.getLogger()


class SemaphoreConnectionPool:
    def __init__(self, connection_string, postgres_configuration_settings):
        self.connection_string = connection_string
        self.postgres_configuration_settings = postgres_configuration_settings

    async def initialize(self):
        try:
            logger.info(
                f"Connecting with {int(self.postgres_configuration_settings.max_connections * 0.9)} connections to `asyncpg.create_pool`."
            )

            self.semaphore = asyncio.Semaphore(
                int(self.postgres_configuration_settings.max_connections * 0.9)
            )

            self.pool = await asyncpg.create_pool(
                self.connection_string,
                max_size=self.postgres_configuration_settings.max_connections,
            )

            logger.info(
                "Successfully connected to Postgres database and created connection pool."
            )
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to connect to relational database."
            ) from e

    @asynccontextmanager
    async def get_connection(self):
        async with self.semaphore:
            async with self.pool.acquire() as conn:
                yield conn

    async def close(self):
        await self.pool.close()


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
