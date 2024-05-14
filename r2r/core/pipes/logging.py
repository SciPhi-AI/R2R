import json
import logging
import os
import uuid
from abc import abstractmethod
from datetime import datetime
from typing import List, Optional

import asyncpg

from ..providers.base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class LoggingConfig(ProviderConfig):
    provider: str = "local"
    log_table: str = "logs"
    log_info_table: str = "logs_pipeline_info"
    logging_path: Optional[str] = None

    def validate(self) -> None:
        pass

    @property
    def supported_providers(self) -> List[str]:
        return ["local", "postgres", "redis"]


class PipeLoggingProvider(Provider):
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
    async def get_logs(
        self, run_ids: List[str], limit_per_run_and_type: int
    ) -> list:
        pass


class LocalPipeLoggingProvider(PipeLoggingProvider):
    def __init__(self, config: LoggingConfig):
        self.log_table = config.log_table
        self.log_info_table = config.log_info_table
        self.logging_path = config.logging_path or os.getenv(
            "LOCAL_DB_PATH", "local.sqlite"
        )
        if not self.logging_path:
            raise ValueError(
                "Please set the environment variable LOCAL_DB_PATH."
            )
        self.conn = None
        try:
            import aiosqlite

            self.aiosqlite = aiosqlite
        except ImportError:
            raise ImportError(
                "Please install aiosqlite to use the LocalPipeLoggingProvider."
            )

    async def init(self):
        self.conn = await self.aiosqlite.connect(self.logging_path)
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.log_table} (
                timestamp DATETIME,
                pipe_run_id TEXT,
                key TEXT,
                value TEXT
            )
            """
        )
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.log_info_table} (
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
            self.log_info_table if is_pipeline_info else self.log_table
        )

        if is_pipeline_info:
            if key != "pipeline_type":
                raise ValueError("Metadata keys must be 'pipeline_type'")
            await self.conn.execute(
                f"INSERT INTO {collection} (timestamp, pipe_run_id, pipeline_type) VALUES (datetime('now'), ?, ?)",
                (str(pipe_run_id), value),
            )
        else:
            await self.conn.execute(
                f"INSERT INTO {collection} (timestamp, pipe_run_id, key, value) VALUES (datetime('now'), ?, ?, ?)",
                (str(pipe_run_id), key, value),
            )
        await self.conn.commit()

    async def get_run_ids(
        self, pipeline_type: Optional[str] = None, limit: int = 10
    ) -> List[uuid.UUID]:
        cursor = await self.conn.cursor()
        query = f"SELECT pipe_run_id FROM {self.log_info_table}"
        conditions = []
        params = []
        if pipeline_type:
            conditions.append("pipeline_type = ?")
            params.append(pipeline_type)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        await cursor.execute(query, params)
        return [uuid.UUID(row[0]) for row in await cursor.fetchall()]

    async def get_logs(
        self, run_ids: List[uuid.UUID], limit_per_run_and_type: int = 10
    ) -> list:
        if not run_ids:
            raise ValueError("No run ids provided.")
        cursor = await self.conn.cursor()
        placeholders = ",".join(["?" for _ in run_ids])
        query = f"""
        SELECT *
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY pipe_run_id ORDER BY timestamp DESC) as rn
            FROM {self.log_table}
            WHERE pipe_run_id IN ({placeholders})
        )
        WHERE rn <= ?
        ORDER BY timestamp DESC
        """
        params = [str(ele) for ele in run_ids] + [limit_per_run_and_type]
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        new_rows = []
        for row in rows:
            new_rows.append(
                (row[0], uuid.UUID(row[1]), row[2], row[3], row[4])
            )
        return [
            {desc[0]: row[i] for i, desc in enumerate(cursor.description)}
            for row in new_rows
        ]


class PostgresLoggingConfig(LoggingConfig):
    provider: str = "postgres"
    log_table: str = "logs"
    log_info_table: str = "logs_pipeline_info"

    def validate(self) -> None:
        required_env_vars = [
            "POSTGRES_DBNAME",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_HOST",
            "POSTGRES_PORT",
        ]
        for var in required_env_vars:
            if not os.getenv(var):
                raise ValueError(f"Environment variable {var} is not set.")

    @property
    def supported_providers(self) -> List[str]:
        return ["postgres"]


class PostgresPipeLoggingProvider(PipeLoggingProvider):
    def __init__(self, config: PostgresLoggingConfig):
        self.log_table = config.log_table
        self.log_info_table = config.log_info_table
        self.config = config
        self.conn = None
        if not os.getenv("POSTGRES_DBNAME"):
            raise ValueError(
                "Please set the environment variable POSTGRES_DBNAME."
            )
        if not os.getenv("POSTGRES_USER"):
            raise ValueError(
                "Please set the environment variable POSTGRES_USER."
            )
        if not os.getenv("POSTGRES_PASSWORD"):
            raise ValueError(
                "Please set the environment variable POSTGRES_PASSWORD."
            )
        if not os.getenv("POSTGRES_HOST"):
            raise ValueError(
                "Please set the environment variable POSTGRES_HOST."
            )
        if not os.getenv("POSTGRES_PORT"):
            raise ValueError(
                "Please set the environment variable POSTGRES_PORT."
            )

    async def init(self):
        self.conn = await asyncpg.connect(
            database=os.getenv("POSTGRES_DBNAME"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
        )
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.log_table} (
                timestamp TIMESTAMPTZ,
                pipe_run_id UUID,
                key TEXT,
                value TEXT
            )
            """
        )
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.log_info_table} (
                timestamp TIMESTAMPTZ,
                pipe_run_id UUID UNIQUE,
                pipeline_type TEXT
            )
        """
        )

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
            self.log_info_table if is_pipeline_info else self.log_table
        )

        if is_pipeline_info:
            if key != "pipeline_type":
                raise ValueError("Metadata keys must be 'pipeline_type'")
            await self.conn.execute(
                f"INSERT INTO {collection} (timestamp, pipe_run_id, pipeline_type) VALUES (NOW(), $1, $2)",
                pipe_run_id,
                value,
            )
        else:
            await self.conn.execute(
                f"INSERT INTO {collection} (timestamp, pipe_run_id, key, value) VALUES (NOW(), $1, $2, $3)",
                pipe_run_id,
                key,
                value,
            )

    async def get_run_ids(
        self, pipeline_type: Optional[str] = None, limit: int = 10
    ) -> List[uuid.UUID]:
        query = f"SELECT pipe_run_id FROM {self.log_info_table}"
        conditions = []
        params = []
        if pipeline_type:
            conditions.append("pipeline_type = $1")
            params.append(pipeline_type)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT $2"
        params.append(limit)
        rows = await self.conn.fetch(query, *params)
        return [row["pipe_run_id"] for row in rows]

    async def get_logs(
        self, run_ids: List[uuid.UUID], limit_per_run_and_type: int = 10
    ) -> list:
        if not run_ids:
            raise ValueError("No run ids provided.")

        placeholders = ",".join([f"${i+1}" for i in range(len(run_ids))])
        query = f"""
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY pipe_run_id ORDER BY timestamp DESC) as rn
            FROM {self.log_table}
            WHERE pipe_run_id::text IN ({placeholders})
        ) sub
        WHERE sub.rn <= ${len(run_ids) + 1}
        ORDER BY sub.timestamp DESC
        """
        params = [str(run_id) for run_id in run_ids] + [limit_per_run_and_type]
        rows = await self.conn.fetch(query, *params)
        return [{key: row[key] for key in row.keys()} for row in rows]


class RedisLoggingConfig(LoggingConfig):
    provider: str = "redis"
    log_table: str = "logs"
    log_info_table: str = "logs_pipeline_info"

    def validate(self) -> None:
        required_env_vars = ["REDIS_CLUSTER_IP", "REDIS_CLUSTER_PORT"]
        for var in required_env_vars:
            if not os.getenv(var):
                raise ValueError(f"Environment variable {var} is not set.")

    @property
    def supported_providers(self) -> List[str]:
        return ["redis"]


class RedisPipeLoggingProvider(PipeLoggingProvider):
    def __init__(self, config: RedisLoggingConfig):
        if not all(
            [
                os.getenv("REDIS_CLUSTER_IP"),
                os.getenv("REDIS_CLUSTER_PORT"),
            ]
        ):
            raise ValueError(
                "Please set the environment variables REDIS_CLUSTER_IP and REDIS_CLUSTER_PORT to run `LoggingDatabaseConnection` with `redis`."
            )
        try:
            from redis.asyncio import Redis
        except ImportError:
            raise ValueError(
                "Error, `redis` is not installed. Please install it using `pip install redis`."
            )

        cluster_ip = os.getenv("REDIS_CLUSTER_IP")
        port = os.getenv("REDIS_CLUSTER_PORT")
        self.redis = Redis(host=cluster_ip, port=port, decode_responses=True)
        self.log_key = config.log_table
        self.log_info_key = config.log_info_table

    async def close(self):
        await self.redis.close()

    async def log(
        self,
        pipe_run_id: uuid.UUID,
        key: str,
        value: str,
        is_pipeline_info=False,
    ):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "pipe_run_id": str(pipe_run_id),
            "key": key,
            "value": value,
        }
        if is_pipeline_info:
            if key != "pipeline_type":
                raise ValueError("Metadata keys must be 'pipeline_type'")
            log_entry["pipeline_type"] = value
            await self.redis.hset(
                self.log_info_key, str(pipe_run_id), json.dumps(log_entry)
            )
        else:
            await self.redis.lpush(
                f"{self.log_key}:{pipe_run_id}", json.dumps(log_entry)
            )

    async def get_run_ids(
        self, pipeline_type: Optional[str] = None, limit: int = 10
    ) -> List[uuid.UUID]:
        if pipeline_type:
            keys = await self.redis.hkeys(self.log_info_key)
            matched_ids = []
            for key in keys:
                log_entry = json.loads(
                    await self.redis.hget(self.log_info_key, key)
                )
                if log_entry["pipeline_type"] == pipeline_type:
                    matched_ids.append(uuid.UUID(log_entry["pipe_run_id"]))
            return matched_ids[:limit]
        else:
            keys = await self.redis.hkeys(self.log_info_key)
            return [uuid.UUID(key) for key in keys[:limit]]

    async def get_logs(
        self, run_ids: List[uuid.UUID], limit_per_run_and_type: int = 10
    ) -> list:
        logs = []
        for run_id in run_ids:
            raw_logs = await self.redis.lrange(
                f"{self.log_key}:{run_id}", 0, limit_per_run_and_type - 1
            )
            for raw_log in raw_logs:
                json_log = json.loads(raw_log)
                json_log["pipe_run_id"] = uuid.UUID(json_log["pipe_run_id"])
                logs.append(json_log)
        return logs


class PipeLoggingConnectionSingleton:
    _instance = None
    _is_configured = False

    SUPPORTED_PROVIDERS = {
        "local": LocalPipeLoggingProvider,
        "postgres": PostgresPipeLoggingProvider,
        "redis": RedisPipeLoggingProvider,
    }

    @classmethod
    def get_instance(cls):
        return cls.SUPPORTED_PROVIDERS[cls._config.provider](cls._config)

    @classmethod
    def configure(
        cls, logging_config: Optional[LoggingConfig] = LoggingConfig()
    ):
        if not cls._is_configured:
            cls._config = logging_config
            cls._is_configured = True
        else:
            raise Exception(
                "PipeLoggingConnectionSingleton is already configured."
            )

    @classmethod
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

    @classmethod
    async def get_run_ids(
        cls, pipeline_type: Optional[str] = None, limit: int = 10
    ) -> List[uuid.UUID]:
        async with cls.get_instance() as provider:
            return await provider.get_run_ids(pipeline_type, limit)

    @classmethod
    async def get_logs(
        cls, run_ids: List[uuid.UUID], limit_per_run_and_type: int = 10
    ) -> list:
        async with cls.get_instance() as provider:
            return await provider.get_logs(run_ids, limit_per_run_and_type)
