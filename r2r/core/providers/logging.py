import functools
import os
from typing import Optional


class LoggingDatabaseConnection:
    """
    A class to connect to a database and log the execution of methods to it.
    """

    supported_providers = ["postgres", "local"]

    def __init__(
        self,
        provider="postgres",
        log_table_name="logs",
        local_db_path: Optional[str] = None,
    ):
        if provider not in self.supported_providers:
            raise ValueError(
                f"Error, `{provider}` is not in LoggingDatabaseConnection's list of supported providers."
            )

        self.provider = provider
        self.conn = None
        self.log_table_name = log_table_name

        if self.provider == "postgres":
            if local_db_path is not None:
                raise ValueError(
                    "Error, `local_db_path` should be None when using `postgres`."
                )
            try:
                import psycopg2

                self.db_module = psycopg2
            except ImportError:
                raise ValueError(
                    "Error, `psycopg2` is not installed. Please install it using `pip install psycopg2`."
                )
            if (
                not os.getenv("POSTGRES_DBNAME")
                or not os.getenv("POSTGRES_USER")
                or not os.getenv("POSTGRES_PASSWORD")
                or not os.getenv("POSTGRES_HOST")
                or not os.getenv("POSTGRES_PORT")
            ):
                raise ValueError(
                    "Please set the environment variables POSTGRES_DBNAME, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, and POSTGRES_PORT to run `LoggingDatabaseConnection` with `postgres`."
                )
        elif self.provider == "local":
            import sqlite3

            self.db_module = sqlite3
            self.local_db_path = local_db_path
        else:
            raise ValueError(
                "Invalid provider. Expected 'postgres' or 'local'."
            )

    def __enter__(self):
        if self.provider == "postgres":
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
                    CREATE TABLE IF NOT EXISTS {self.log_table_name} (
                        timestamp TIMESTAMP,
                        pipeline_run_id UUID,
                        pipeline_run_type TEXT,
                        method TEXT,
                        result TEXT,
                        log_level TEXT
                    )
                """
                )

        elif self.provider == "local":
            self.conn = self.db_module.connect(
                self.local_db_path or os.getenv("LOCAL_DB_PATH")
            )
            self.conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.log_table_name} (
                    timestamp DATETIME,
                    pipeline_run_id TEXT,
                    pipeline_run_type TEXT,
                    method TEXT,
                    result TEXT,
                    log_level TEXT
                )
                """
            )

        self.conn.commit()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def get_logs(self) -> list:
        with self as conn:
            cur = conn.execute(f"SELECT * FROM {self.log_table_name}")
            colnames = [desc[0] for desc in cur.description]
            logs = [dict(zip(colnames, row)) for row in cur.fetchall()]
        return logs


def log_execution_to_db(func):
    """A decorator to log the execution of a method to the database."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Assuming args[0] is the instance of the class the method belongs to
        instance = args[0]
        inst_provider = instance.logging_provider
        if not inst_provider:
            return func(*args, **kwargs)

        # Adjusted to use 'run_id' and 'type'
        arg_pipeline_run_id = instance.pipeline_run_info["run_id"]
        arg_pipeline_run_type = instance.pipeline_run_info["type"]
        arg_log_table_name = inst_provider.log_table_name

        try:
            # Execute the function and get the result
            result = func(*args, **kwargs)
            log_level = "INFO"
        except Exception as e:
            result = str(e)
            log_level = "ERROR"

        # Log the execution to the database
        timestamp_func = (
            "NOW()"
            if inst_provider.provider == "postgres"
            else "datetime('now')"
        )
        with inst_provider as conn:
            conn.execute(
                f"INSERT INTO {arg_log_table_name} (timestamp, pipeline_run_id, pipeline_run_type, method, result, log_level) VALUES ({timestamp_func}, ?, ?, ?, ?, ?)",
                (
                    str(arg_pipeline_run_id),
                    arg_pipeline_run_type,
                    func.__name__,
                    str(result),
                    log_level,
                ),
            )

            # Commit the transaction
            conn.commit()

        if log_level == "ERROR":
            raise Exception(result)

        return result

    return wrapper
