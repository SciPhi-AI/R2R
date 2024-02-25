import functools
import os



class LoggingDatabaseConnection:
    def __init__(self, log_table_name="logs"):

        try:
            import psycopg2
            self.psycopg2 = psycopg2
        except ImportError:
            raise ValueError(
                "Error, `psycopg2` is not installed. Please install it using `pip install psycopg2`."
            )
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
        self.conn = self.psycopg2.connect(
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
        # Assuming args[0] is the instance of the class the method belongs to
        instance = args[0]
        arg_conn = instance.conn
        if not arg_conn:
            return func(*args, **kwargs)

        # Adjusted to use 'run_id' and 'type'
        arg_pipeline_run_id = instance.pipeline_run_info["run_id"]
        arg_pipeline_run_type = instance.pipeline_run_info["type"]
        arg_log_table_name = instance.log_table_name

        try:
            # Execute the function and get the result
            result = func(*args, **kwargs)
            log_level = "INFO"
        except Exception as e:
            result = str(e)
            log_level = "ERROR"

        # Log the execution to the database
        with arg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO "
                + arg_log_table_name
                + " (timestamp, pipeline_run_id, pipeline_run_type, method, result, log_level) VALUES (NOW(), %s, %s, %s, %s, %s)",
                (
                    str(arg_pipeline_run_id),
                    arg_pipeline_run_type,
                    func.__name__,
                    str(result),
                    log_level,
                ),
            )

        # Commit the transaction
        arg_conn.commit()

        if log_level == "ERROR":
            raise Exception(result)

        return result

    return wrapper
