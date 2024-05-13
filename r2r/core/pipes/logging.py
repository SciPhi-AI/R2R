import logging
import os
import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

import aiosqlite

logger = logging.getLogger(__name__)


class PipeLoggingProvider(ABC):
    @abstractmethod
    async def close(self):
        pass

    @abstractmethod
    async def log(self, pipe_run_id: uuid.UUID, key: str, value: str):
        pass

    @abstractmethod
    async def get_run_ids(
        self, key: Optional[str] = None, pipeline_type: Optional[str] = None
    ) -> List[str]:
        pass

    @abstractmethod
    async def get_logs(self, run_ids: List[str], max_logs: int) -> list:
        pass


class LocalPipeLoggingProvider(PipeLoggingProvider):
    def __init__(
        self,
        data_collection="logs",
        info_collection="logs_pipeline_info",
        logging_path=None,
    ):
        self.data_collection = data_collection
        self.info_collection = info_collection
        self.logging_path = logging_path or os.getenv(
            "LOCAL_DB_PATH", "local.sqlite"
        )
        if not self.logging_path:
            raise ValueError(
                "Please set the environment variable LOCAL_DB_PATH."
            )
        self.conn = None

    async def init(self):
        self.conn = await aiosqlite.connect(self.logging_path)
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.data_collection} (
                timestamp DATETIME,
                pipe_run_id TEXT,
                key TEXT,
                value TEXT
            )
            """
        )
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.info_collection} (
                timestamp DATETIME,
                pipe_run_id TEXT UNIQUE,
                pipeline_type TEXT
            )
        """
        )
        await self.conn.commit()

    async def __aenter__(self):
        if self.conn is None:
            await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def log(
        self,
        pipe_run_id: uuid.UUID,
        key: str,
        value: str,
        is_pipeline_info=False,
    ):
        collection = (
            self.info_collection if is_pipeline_info else self.data_collection
        )

        if is_pipeline_info:
            collection = self.info_collection
            if not key == "pipeline_type":
                raise ValueError("Metadata keys must be 'pipeline_type'")
            await self.conn.execute(
                f"INSERT INTO {collection} (timestamp, pipe_run_id, pipeline_type) VALUES (datetime('now'), ?, ?)",
                (str(pipe_run_id), value),
            )
        else:
            collection = self.data_collection
            await self.conn.execute(
                f"INSERT INTO {collection} (timestamp, pipe_run_id, key, value) VALUES (datetime('now'), ?, ?, ?)",
                (str(pipe_run_id), key, value),
            )
        await self.conn.commit()

    async def get_run_ids(
        self, pipeline_type: Optional[str] = None, limit: int = 10
    ) -> List[str]:
        cursor = await self.conn.cursor()
        query = f"SELECT pipe_run_id FROM {self.info_collection}"
        conditions = []
        params = []
        if pipeline_type:
            conditions.append("pipeline_type = ?")
            params.append(pipeline_type)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ?"  # Order by timestamp descending
        params.append(limit)
        await cursor.execute(query, params)
        return [row[0] for row in await cursor.fetchall()]

    async def get_logs(self, run_ids: List[str], limit_per_run: int = 10) -> list:
        if not run_ids:
            raise ValueError("No run ids provided.")

        try:
            cursor = await self.conn.cursor()
            # Using a window function to partition by pipe_run_id and limit rows per id
            placeholders = ",".join(["?" for _ in run_ids])  # placeholders for run_ids
            query = f"""
            SELECT *
            FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY pipe_run_id ORDER BY timestamp DESC) as rn
                FROM {self.data_collection}
                WHERE pipe_run_id IN ({placeholders})
            )
            WHERE rn <= ?
            ORDER BY timestamp DESC
            """
            # We need to pass the limit as many times as there are run_ids plus once more for the WHERE clause in the subquery
            params = run_ids + [limit_per_run]
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
            return [
                {desc[0]: row[i] for i, desc in enumerate(cursor.description)}
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to fetch logs: {e}")
            raise

class PipeLoggingConnectionSingleton:
    _instance = None
    _is_configured = False

    SUPPORTED_PROVIDERS = {
        "local": LocalPipeLoggingProvider,
    }

    @classmethod
    def get_instance(cls):
        return cls.SUPPORTED_PROVIDERS[cls._provider](
                cls.data_collection, cls.info_collection
            )

    @classmethod
    def configure(
        cls,
        provider="local",
        data_collection="logs",
        info_collection="logs_pipeline_info",
    ):
        if not cls._is_configured:
            cls._provider = provider
            cls.data_collection = data_collection
            cls.info_collection = info_collection
            cls._is_configured = True
        else:
            raise Exception(
                "PipeLoggingConnectionSingleton is already configured."
            )

    async def log(
        cls,
        pipe_run_id: uuid.UUID,
        key: str,
        value: str,
        is_pipeline_info=False,
    ):
        try:
            async with cls.get_instance() as provider:
                await provider.log(
                    pipe_run_id, key, value, is_pipeline_info=is_pipeline_info
                )
        except Exception as e:
            logger.error(f"Error logging data: {e}")

    async def get_run_ids(
        cls, pipeline_type: Optional[str] = None, limit: int = 10
    ) -> List[str]:
        async with cls.get_instance() as provider:
            return await provider.get_run_ids(pipeline_type, limit)

    async def get_logs(cls, run_ids: List[str]) -> list:
        async with cls.get_instance() as provider:
            return await provider.get_logs(run_ids)