import json
import logging
import os
from abc import abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from ..providers.base import Provider, ProviderConfig
from .base import RunType

logger = logging.getLogger(__name__)


class RunInfoLog(BaseModel):
    run_id: UUID
    run_type: str
    timestamp: datetime
    user_id: UUID


class LoggingConfig(ProviderConfig):
    provider: str = "local"
    log_table: str = "logs"
    log_info_table: str = "log_info"
    logging_path: Optional[str] = None

    def validate_config(self) -> None:
        pass

    @property
    def supported_providers(self) -> list[str]:
        return ["local", "postgres"]


class RunLoggingProvider(Provider):
    @abstractmethod
    async def close(self):
        pass

    @abstractmethod
    async def log(
        self,
        run_id: UUID,
        key: str,
        value: str,
    ):
        pass

    @abstractmethod
    async def get_logs(
        self,
        run_ids: list[UUID],
        limit_per_run: int,
    ) -> list:
        pass

    @abstractmethod
    async def info_log(
        self,
        run_id: UUID,
        run_type: RunType,
        user_id: UUID,
    ):
        pass

    @abstractmethod
    async def get_info_logs(
        self,
        offset: int = 0,
        limit: int = 100,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        pass

    @abstractmethod
    async def score_completion(
        self, run_id: UUID, message_id: UUID, score: float
    ) -> str:
        pass


class LocalRunLoggingProvider(RunLoggingProvider):
    def __init__(self, config: LoggingConfig):
        self.log_table = config.log_table
        self.log_info_table = config.log_info_table
        # TODO - Should we re-consider this naming convention?
        # e.g. it is confusing to have `R2R_PROJECT_NAME` refer
        # to a global project name that is used in non-Postgres contexts
        self.project_name = os.getenv("R2R_PROJECT_NAME", "default")
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
                "Please install aiosqlite to use the LocalRunLoggingProvider."
            )

    async def _init(self):
        self.conn = await self.aiosqlite.connect(self.logging_path)

        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.project_name}_{self.log_table} (
                timestamp DATETIME,
                run_id TEXT,
                key TEXT,
                value TEXT
            )
            """
        )
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.project_name}_{self.log_info_table} (
                timestamp DATETIME,
                run_id TEXT UNIQUE,
                run_type TEXT,
                user_id TEXT
            )
        """
        )
        await self.conn.commit()

    async def __aenter__(self):
        if self.conn is None:
            await self._init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def log(
        self,
        run_id: UUID,
        key: str,
        value: str,
    ):
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        await self.conn.execute(
            f"""
            INSERT INTO {self.project_name}_{self.log_table} (timestamp, run_id, key, value)
            VALUES (datetime('now'), ?, ?, ?)
            """,
            (str(run_id), key, value),
        )
        await self.conn.commit()

    async def info_log(
        self,
        run_id: UUID,
        run_type: RunType,
        user_id: UUID,
    ):
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        await self.conn.execute(
            f"""
            INSERT INTO {self.project_name}_{self.log_info_table} (timestamp, run_id, run_type, user_id)
            VALUES (datetime('now'), ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
            timestamp = datetime('now'),
            run_type = excluded.run_type,
            user_id = excluded.user_id
            """,
            (str(run_id), run_type, str(user_id)),
        )
        await self.conn.commit()

    async def get_info_logs(
        self,
        offset: int = 0,
        limit: int = 100,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        cursor = await self.conn.cursor()
        query = "SELECT run_id, run_type, timestamp, user_id"
        query += f" FROM {self.project_name}_{self.log_info_table}"
        conditions = []
        params = []
        if run_type_filter:
            conditions.append("run_type = ?")
            params.append(run_type_filter)
        if user_ids:
            conditions.append(f"user_id IN ({','.join(['?']*len(user_ids))})")
            params.extend([str(user_id) for user_id in user_ids])
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        return [
            RunInfoLog(
                run_id=UUID(row[0]),
                run_type=row[1],
                timestamp=datetime.fromisoformat(row[2]),
                user_id=UUID(row[3]),
            )
            for row in rows
        ]

    async def get_logs(
        self,
        run_ids: list[UUID],
        limit_per_run: int = 10,
    ) -> list:
        if not run_ids:
            raise ValueError("No run ids provided.")
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        cursor = await self.conn.cursor()
        placeholders = ",".join(["?" for _ in run_ids])
        query = f"""
        SELECT run_id, key, value, timestamp
        FROM {self.project_name}_{self.log_table}
        WHERE run_id IN ({placeholders})
        ORDER BY timestamp DESC
        """

        params = [str(run_id) for run_id in run_ids]

        await cursor.execute(query, params)
        rows = await cursor.fetchall()

        # Post-process the results to limit per run_id and ensure only requested run_ids are included
        result = []
        run_id_count = {str(run_id): 0 for run_id in run_ids}
        for row in rows:
            row_dict = dict(zip([d[0] for d in cursor.description], row))
            row_run_id = row_dict["run_id"]
            if (
                row_run_id in run_id_count
                and run_id_count[row_run_id] < limit_per_run
            ):
                row_dict["run_id"] = UUID(row_dict["run_id"])
                result.append(row_dict)
                run_id_count[row_run_id] += 1
        return result

    async def score_completion(
        self, run_id: UUID, message_id: UUID, score: float
    ):
        if not self.conn:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )
        cursor = await self.conn.cursor()

        await cursor.execute(
            f"SELECT value FROM {self.project_name}_{self.log_table} WHERE run_id = ? AND key = 'completion_record'",
            (str(run_id),),
        )
        row = await cursor.fetchone()

        if row:
            completion_record = json.loads(row[0])

            if completion_record.get("message_id") == str(message_id):
                if (
                    "score" not in completion_record
                    or completion_record["score"] is None
                ):
                    completion_record["score"] = [score]
                elif isinstance(completion_record["score"], list):
                    completion_record["score"] = [
                        x for x in completion_record["score"] if x is not None
                    ]
                    completion_record["score"].append(score)
                else:
                    completion_record["score"] = [
                        completion_record["score"],
                        score,
                    ]

                await cursor.execute(
                    f"UPDATE {self.project_name}_{self.log_table} SET value = ? WHERE run_id = ? AND key = 'completion_record'",
                    (json.dumps(completion_record), str(run_id)),
                )

                await self.conn.commit()
                return {"message": "Score updated successfully."}

        return {"message": "Score not updated."}


class PostgresLoggingConfig(LoggingConfig):
    provider: str = "postgres"
    log_table: str = "logs"
    log_info_table: str = "log_info"

    def validate_config(self) -> None:
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
    def supported_providers(self) -> list[str]:
        return ["postgres"]


class PostgresRunLoggingProvider(RunLoggingProvider):
    def __init__(self, config: PostgresLoggingConfig):
        self.log_table = config.log_table
        self.log_info_table = config.log_info_table
        self.config = config
        self.project_name = config.app.project_name or os.getenv(
            "R2R_PROJECT_NAME", "default"
        )
        self.pool = None
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

    async def _init(self):
        self.pool = await asyncpg.create_pool(
            database=os.getenv("POSTGRES_DBNAME"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            statement_cache_size=0,  # Disable statement caching
        )
        async with self.pool.acquire() as conn:

            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.project_name}.{self.log_table} (
                    timestamp TIMESTAMPTZ,
                    run_id UUID,
                    key TEXT,
                    value TEXT
                )
                """
            )
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.project_name}.{self.log_info_table} (
                    timestamp TIMESTAMPTZ,
                    run_id UUID UNIQUE,
                    run_type TEXT,
                    user_id UUID
                )
            """
            )

    async def __aenter__(self):
        if self.pool is None:
            await self._init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def log(
        self,
        run_id: UUID,
        key: str,
        value: str,
    ):
        if not self.pool:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO {self.project_name}.{self.log_table} (timestamp, run_id, key, value) VALUES (NOW(), $1, $2, $3)",
                run_id,
                key,
                value,
            )

    async def info_log(
        self,
        run_id: UUID,
        run_type: RunType,
        user_id: UUID,
    ):
        if not self.pool:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO {self.project_name}.{self.log_info_table} (timestamp, run_id, run_type, user_id) VALUES (NOW(), $1, $2, $3)",
                run_id,
                run_type,
                user_id,
            )

    async def get_info_logs(
        self,
        offset: int = 0,
        limit: int = 100,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        if not self.pool:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        query = f"SELECT run_id, run_type, timestamp, user_id FROM {self.project_name}.{self.log_info_table}"
        conditions = []
        params = []
        param_count = 1

        if run_type_filter:
            conditions.append(f"run_type = ${param_count}")
            params.append(run_type_filter)
            param_count += 1

        if user_ids:
            conditions.append(f"user_id = ANY(${param_count}::uuid[])")
            params.append(user_ids)
            param_count += 1

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY timestamp DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
        params.extend([limit, offset])

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [
                RunInfoLog(
                    run_id=row["run_id"],
                    run_type=row["run_type"],
                    timestamp=row["timestamp"],
                    user_id=row["user_id"],
                )
                for row in rows
            ]

    async def get_logs(
        self, run_ids: list[UUID], limit_per_run: int = 10
    ) -> list:
        if not run_ids:
            raise ValueError("No run ids provided.")
        if not self.pool:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        placeholders = ",".join([f"${i + 1}" for i in range(len(run_ids))])
        query = f"""
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY timestamp DESC) as rn
            FROM {self.project_name}.{self.log_table}
            WHERE run_id::text IN ({placeholders})
        ) sub
        WHERE sub.rn <= ${len(run_ids) + 1}
        ORDER BY sub.timestamp DESC
        """
        params = [str(run_id) for run_id in run_ids] + [limit_per_run]
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [{key: row[key] for key in row.keys()} for row in rows]

    async def score_completion(
        self, run_id: UUID, message_id: UUID, score: float
    ):
        if not self.pool:
            raise ValueError(
                "Initialize the connection pool before attempting to log."
            )

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT value FROM {self.project_name}.{self.log_table} WHERE run_id = $1 AND key = 'completion_record'",
                run_id,
            )

            if row:
                completion_record = json.loads(row["value"])

                if completion_record.get("message_id") == str(message_id):
                    if (
                        "score" not in completion_record
                        or completion_record["score"] is None
                    ):
                        completion_record["score"] = [score]
                    elif isinstance(completion_record["score"], list):
                        completion_record["score"] = [
                            x
                            for x in completion_record["score"]
                            if x is not None
                        ]
                        completion_record["score"].append(score)
                    else:
                        completion_record["score"] = [
                            completion_record["score"],
                            score,
                        ]

                    await conn.execute(
                        f"UPDATE {self.project_name}.{self.log_table} SET value = $1 WHERE run_id = $2 AND key = 'completion_record'",
                        json.dumps(completion_record),
                        run_id,
                    )
                    return {"message": "Score updated successfully."}

        return {"message": "Score not updated."}


class RunLoggingSingleton:
    _instance = None
    _is_configured = False
    _config: Optional[LoggingConfig] = None

    SUPPORTED_PROVIDERS = {
        "local": LocalRunLoggingProvider,
        "postgres": PostgresRunLoggingProvider,
    }

    @classmethod
    def get_instance(cls):
        return cls.SUPPORTED_PROVIDERS[cls._config.provider](cls._config)

    @classmethod
    def configure(cls, logging_config: LoggingConfig):
        if not cls._is_configured:
            cls._config = logging_config
            cls._is_configured = True
        else:
            raise Exception("RunLoggingSingleton is already configured.")

    @classmethod
    async def log(
        cls,
        run_id: UUID,
        key: str,
        value: str,
    ):
        try:
            async with cls.get_instance() as provider:
                await provider.log(run_id, key, value)
        except Exception as e:
            logger.error(f"Error logging data {(run_id, key, value)}: {e}")

    @classmethod
    async def info_log(
        cls,
        run_id: UUID,
        run_type: RunType,
        user_id: UUID,
    ):
        try:
            async with cls.get_instance() as provider:
                await provider.info_log(run_id, run_type, user_id)
        except Exception as e:
            logger.error(
                f"Error logging info data {(run_id, run_type, user_id)}: {e}"
            )

    @classmethod
    async def get_info_logs(
        cls,
        offset: int = 0,
        limit: int = 100,
        run_type_filter: Optional[RunType] = None,
        user_ids: Optional[list[UUID]] = None,
    ) -> list[RunInfoLog]:
        async with cls.get_instance() as provider:
            return await provider.get_info_logs(
                offset=offset,
                limit=limit,
                run_type_filter=run_type_filter,
                user_ids=user_ids,
            )

    @classmethod
    async def get_logs(
        cls,
        run_ids: list[UUID],
        limit_per_run: int = 10,
    ) -> list:
        async with cls.get_instance() as provider:
            return await provider.get_logs(run_ids, limit_per_run)

    @classmethod
    async def score_completion(
        cls, run_id: UUID, message_id: UUID, score: float
    ):
        async with cls.get_instance() as provider:
            return await provider.score_completion(run_id, message_id, score)
