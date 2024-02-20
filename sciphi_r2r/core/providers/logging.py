import functools
import os

import psycopg2
from pydantic import BaseModel


class LoggingDatabaseConnection:
    def __init__(self, log_table_name="logs"):
        self.conn = None
        self.log_table_name = log_table_name
        if (
            not os.getenv("PGVECTOR_DBNAME")
            or not os.getenv("PGVECTOR_USER")
            or not os.getenv("PGVECTOR_PASSWORD")
            or not os.getenv("PGVECTOR_HOST")
            or not os.getenv("PGVECTOR_PORT")
        ):
            raise ValueError(
                "Please set the environment variables PGVECTOR_DBNAME, PGVECTOR_USER, PGVECTOR_PASSWORD, PGVECTOR_HOST, and PGVECTOR_PORT."
            )

    def __enter__(self):
        self.conn = psycopg2.connect(
            dbname=os.getenv("PGVECTOR_DBNAME"),
            user=os.getenv("PGVECTOR_USER"),
            password=os.getenv("PGVECTOR_PASSWORD"),
            host=os.getenv("PGVECTOR_HOST"),
            port=os.getenv("PGVECTOR_PORT"),
        )
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.log_table_name} (
                    timestamp TIMESTAMP,
                    pipeline_run_id UUID,
                    method TEXT,
                    result TEXT,
                    log_level TEXT,
                    message TEXT
                )
            """
            )
        self.conn.commit()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

    def get_logs(self) -> list:
        with self.conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {self.log_table_name}")
            colnames = [desc[0] for desc in cur.description]
            logs = [dict(zip(colnames, row)) for row in cur.fetchall()]
        return logs


def log_execution_to_db(func):
    """A decorator to log the execution of a method to the database."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Get the database connection and pipeline run ID from the arguments
        arg_conn = args[0].conn
        if not arg_conn:
            return func(*args, **kwargs)

        arg_pipeline_run_id = args[0].pipeline_run_id
        arg_log_table_name = args[0].log_table_name

        try:
            # Execute the function and get the result
            result = func(*args, **kwargs)
            log_level = "INFO"
            message = "Method executed"
        except Exception as e:
            result = str(e)
            log_level = "ERROR"
            message = "Method execution failed"

        # Log the execution to the database
        with arg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO "
                + arg_log_table_name
                + " (timestamp, pipeline_run_id, method, result, log_level, message) VALUES (NOW(), %s, %s, %s, %s, %s)",
                (
                    str(arg_pipeline_run_id),
                    func.__name__,
                    str(result),
                    log_level,
                    message,
                ),
            )

        # Commit the transaction
        arg_conn.commit()

        if log_level == "ERROR":
            raise Exception(result)

        return result

    return wrapper
