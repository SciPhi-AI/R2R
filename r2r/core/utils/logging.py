import functools
import json
import logging
import os
import types
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# TODO - Move Run Types to a global enum
RUN_TYPES = [
    "ingestion",
    "embedding",
    "search",
    "rag",
    "evaluation",
    "scraper",
]


class LoggingProvider(ABC):
    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def log(
        self,
        timestamp,
        pipe_run_id,
        pipe_run_type,
        method,
        result,
        log_level,
    ):
        pass

    @abstractmethod
    def get_logs(
        self, max_logs: int, pipe_run_type: Optional[str] = None
    ) -> list:
        pass


class PostgresLoggingProvider(LoggingProvider):
    def __init__(self, collection_name="logs"):
        self.conn = None
        self.collection_name = collection_name
        self.db_module = self._import_db_module()
        self._init()

    def _import_db_module(self):
        try:
            import psycopg2

            return psycopg2
        except ImportError:
            raise ValueError(
                "Error, `psycopg2` is not installed. Please install it using `pip install psycopg2`."
            )

    def _init(self):
        if not all(
            [
                os.getenv("POSTGRES_DBNAME"),
                os.getenv("POSTGRES_USER"),
                os.getenv("POSTGRES_PASSWORD"),
                os.getenv("POSTGRES_HOST"),
                os.getenv("POSTGRES_PORT"),
            ]
        ):
            raise ValueError(
                "Please set the environment variables POSTGRES_DBNAME, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, and POSTGRES_PORT to run `LoggingDatabaseConnection` with `postgres`."
            )
        self.conn = self.db_module.connect(
            dbname=os.getenv("POSTGRES_DBNAME"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
        )
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.collection_name} (
                    timestamp TIMESTAMP,
                    pipe_run_id UUID,
                    pipe_run_type TEXT,
                    method TEXT,
                    result TEXT,
                    log_level TEXT
                )
            """
            )
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

    def log(
        self,
        pipe_run_id,
        pipe_run_type,
        method,
        result,
        log_level,
    ):
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {self.collection_name} (timestamp, pipe_run_id, pipe_run_type, method, result, log_level) VALUES (NOW(), %s, %s, %s, %s, %s)",
                    (
                        str(pipe_run_id),
                        pipe_run_type,
                        method,
                        str(result),
                        log_level,
                    ),
                )
            self.conn.commit()
        except Exception as e:
            # Handle any exceptions that occur during the logging process
            logger.error(
                f"Error occurred while logging to the PostgreSQL database: {str(e)}"
            )

    def get_logs(self, max_logs: int, pipe_run_type=None) -> list:
        logs = []
        with self.conn.cursor() as cur:
            if pipe_run_type:
                cur.execute(
                    f"SELECT * FROM {self.collection_name} WHERE pipe_run_type = %s ORDER BY timestamp DESC LIMIT %s",
                    (pipe_run_type, max_logs),
                )
            else:
                cur.execute(
                    f"SELECT * FROM {self.collection_name} ORDER BY timestamp DESC LIMIT %s",
                    (max_logs,),
                )
            colnames = [desc[0] for desc in cur.description]
            logs = [dict(zip(colnames, row)) for row in cur.fetchall()]
        self.conn.commit()
        return logs


class LocalLoggingProvider(LoggingProvider):
    def __init__(self, collection_name="logs"):
        self.conn = None
        self.collection_name = collection_name
        logging_path = os.getenv("LOCAL_DB_PATH", "local.sqlite")
        if not logging_path:
            raise ValueError(
                "Please set the environment variable LOCAL_DB_PATH to run `LoggingDatabaseConnection` with `local`."
            )
        self.logging_path = logging_path
        self.db_module = self._import_db_module()
        self._init()

    def _import_db_module(self):
        try:
            import sqlite3

            return sqlite3
        except ImportError:
            raise ValueError(
                "Error, `sqlite3` is not installed. Please install it using `pip install sqlite3`."
            )

    def _init(self):
        self.conn = self.db_module.connect(self.logging_path)
        self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.collection_name} (
                timestamp DATETIME,
                pipe_run_id TEXT,
                pipe_run_type TEXT,
                method TEXT,
                result TEXT,
                log_level TEXT
            )
            """
        )
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

    def log(
        self,
        pipe_run_id,
        pipe_run_type,
        method,
        result,
        log_level,
    ):
        try:
            with self.db_module.connect(self.logging_path) as conn:
                conn.execute(
                    f"INSERT INTO {self.collection_name} (timestamp, pipe_run_id, pipe_run_type, method, result, log_level) VALUES (datetime('now'), ?, ?, ?, ?, ?)",
                    (
                        str(pipe_run_id),
                        pipe_run_type,
                        method,
                        str(result),
                        log_level,
                    ),
                )
                conn.commit()
        except Exception as e:
            # Handle any exceptions that occur during the logging process
            logger.error(
                f"Error occurred while logging to the local database: {str(e)}"
            )

    def get_logs(self, max_logs: int, pipe_run_type=None) -> list:
        logs = []
        with self.db_module.connect(self.logging_path) as conn:
            cur = conn.cursor()
            if pipe_run_type:
                cur.execute(
                    f"SELECT * FROM {self.collection_name} WHERE pipe_run_type = ? ORDER BY timestamp DESC LIMIT ?",
                    (pipe_run_type, max_logs),
                )
            else:
                cur.execute(
                    f"SELECT * FROM {self.collection_name} ORDER BY timestamp DESC LIMIT ?",
                    (max_logs,),
                )
            colnames = [desc[0] for desc in cur.description]
            results = cur.fetchall()
            logs = [dict(zip(colnames, row)) for row in results]
        return logs


class RedisLoggingProvider(LoggingProvider):
    def __init__(self, collection_name="logs"):
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
            from redis import Redis
        except ImportError:
            raise ValueError(
                "Error, `redis` is not installed. Please install it using `pip install redis`."
            )

        cluster_ip = os.getenv("REDIS_CLUSTER_IP")
        port = os.getenv("REDIS_CLUSTER_PORT")
        self.redis = Redis(cluster_ip, port, decode_responses=True)
        self.log_key = collection_name

    def connect(self):
        pass

    def close(self):
        pass

    def log(
        self,
        pipe_run_id,
        pipe_run_type,
        method,
        result,
        log_level,
    ):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "pipe_run_id": str(pipe_run_id),
            "pipe_run_type": pipe_run_type,
            "method": method,
            "result": str(result),
            "log_level": log_level,
        }
        try:
            # Save log entry under a key that includes the pipe_run_type
            type_specific_key = f"{self.log_key}:{pipe_run_type}"
            self.redis.lpush(type_specific_key, json.dumps(log_entry))
        except Exception as e:
            logger.error(f"Error occurred while logging to Redis: {str(e)}")

    def get_logs(self, max_logs: int, pipe_run_type=None) -> list:
        if pipe_run_type:
            if pipe_run_type not in RUN_TYPES:
                raise ValueError(
                    f"Error, `{pipe_run_type}` is not in LoggingDatabaseConnection's list of supported run types."
                )
            # Fetch logs for a specific type
            key_to_fetch = f"{self.log_key}:{pipe_run_type}"
            logs = self.redis.lrange(key_to_fetch, 0, max_logs - 1)
            return [json.loads(log) for log in logs]
        else:
            # Fetch logs for all types
            all_logs = []
            for run_type in RUN_TYPES:
                key_to_fetch = f"{self.log_key}:{run_type}"
                logs = self.redis.lrange(key_to_fetch, 0, max_logs - 1)
                all_logs.extend([json.loads(log) for log in logs])
            # Sort logs by timestamp if needed and slice to max_logs
            all_logs.sort(key=lambda x: x["timestamp"], reverse=True)
            return all_logs[:max_logs]


class LoggingDatabaseConnection:
    """
    A class to connect to a database and log the execution of methods to it.
    """

    supported_providers = {
        "postgres": PostgresLoggingProvider,
        "local": LocalLoggingProvider,
        "redis": RedisLoggingProvider,
    }

    def __init__(
        self,
        provider="postgres",
        collection_name="logs",
    ):
        if provider not in self.supported_providers:
            raise ValueError(
                f"Error, `{provider}` is not in LoggingDatabaseConnection's list of supported providers."
            )

        self.provider = provider
        if provider == "redis":
            self.logging_provider = self.supported_providers[provider](
                collection_name
            )
        else:
            self.logging_provider = self.supported_providers[provider](
                collection_name
            )

    def __enter__(self):
        self.logging_provider.connect()
        return self.logging_provider

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logging_provider.close()

    def get_logs(
        self, max_logs: int, pipe_run_type: Optional[str]
    ) -> list:
        return self.logging_provider.get_logs(max_logs, pipe_run_type)


def log_output_to_db(func):
    """A decorator to log the execution of a method to the database."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        instance = args[0]
        logging_connection = instance.logging_connection
        if not logging_connection:
            return func(*args, **kwargs)

        arg_pipe_run_id = instance.pipe_run_info["run_id"]
        arg_pipe_run_type = instance.pipe_run_info["type"]

        try:
            result = func(*args, **kwargs)
            if isinstance(result, types.GeneratorType):

                def generator_wrapper():
                    log_level = "INFO"
                    results = []
                    try:
                        for res in result:
                            results.append(res)
                            yield res
                    except Exception as e:
                        results.append(str(e))
                        log_level = "ERROR"
                    finally:
                        logging_connection.logging_provider.log(
                            arg_pipe_run_id,
                            arg_pipe_run_type,
                            func.__name__,
                            "".join(results),
                            log_level,
                        )

                return generator_wrapper()
            else:
                logging_connection.logging_provider.log(
                    arg_pipe_run_id,
                    arg_pipe_run_type,
                    func.__name__,
                    str(result),
                    "INFO",
                )
                return result

        except Exception as e:
            result = str(e)
            log_level = "ERROR"
            logging_connection.logging_provider.log(
                arg_pipe_run_id,
                arg_pipe_run_type,
                func.__name__,
                result,
                log_level,
            )
            raise Exception(result)

    return wrapper
