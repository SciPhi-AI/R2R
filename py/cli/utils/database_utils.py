import logging.config
import os
import sys
from pathlib import Path
from typing import Optional

import alembic.config
import asyncclick as click
from alembic import command as alembic_command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


def get_default_db_vars() -> dict[str, str]:
    """Get default database environment variables."""
    return {
        "R2R_POSTGRES_HOST": "localhost",
        "R2R_POSTGRES_PORT": "5432",
        "R2R_POSTGRES_DBNAME": "postgres",
        "R2R_POSTGRES_USER": "postgres",
        "R2R_POSTGRES_PASSWORD": "postgres",
        "R2R_PROJECT_NAME": "r2r_default",
    }


def get_schema_version_table(schema_name: str) -> str:
    """Get the schema-specific version of alembic_version table name."""
    return f"{schema_name}_alembic_version"


def get_database_url_from_env(log: bool = True) -> str:
    """Construct database URL from environment variables."""
    env_vars = {
        k: os.environ.get(k, v) for k, v in get_default_db_vars().items()
    }

    if log:
        for k, v in env_vars.items():
            click.secho(
                f"Using value for {k}: {v}",
                fg="yellow" if v == get_default_db_vars()[k] else "green",
            )

    return (
        f"postgresql://{env_vars['R2R_POSTGRES_USER']}:{env_vars['R2R_POSTGRES_PASSWORD']}"
        f"@{env_vars['R2R_POSTGRES_HOST']}:{env_vars['R2R_POSTGRES_PORT']}"
        f"/{env_vars['R2R_POSTGRES_DBNAME']}"
    )


def ensure_schema_exists(engine, schema_name: str):
    """Create schema if it doesn't exist and set up schema-specific version table."""
    with engine.begin() as conn:
        # Create schema if it doesn't exist
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))

        # Move or create alembic_version table in the specific schema
        version_table = get_schema_version_table(schema_name)
        conn.execute(
            text(
                f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.{version_table} (
                version_num VARCHAR(32) NOT NULL
            )
        """
            )
        )


def check_current_revision(engine, schema_name: str) -> Optional[str]:
    """Check the current revision in the version table."""
    version_table = get_schema_version_table(schema_name)
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT version_num FROM {schema_name}.{version_table}")
        ).fetchone()
        return result[0] if result else None


async def check_database_connection(db_url: str) -> bool:
    """Check if we can connect to the database."""
    try:
        engine = create_engine(db_url)
        with engine.connect():
            return True
    except OperationalError as e:
        click.secho(f"Could not connect to database: {str(e)}", fg="red")
        if "Connection refused" in str(e):
            click.secho(
                "Make sure PostgreSQL is running and accessible with the provided credentials.",
                fg="yellow",
            )
        return False
    except Exception as e:
        click.secho(
            f"Unexpected error checking database connection: {str(e)}",
            fg="red",
        )
        return False


def create_schema_config(
    project_root: Path, schema_name: str, db_url: str
) -> alembic.config.Config:
    """Create an Alembic config for a specific schema."""
    config = alembic.config.Config()

    # Calculate the path to the migrations folder
    current_file = Path(__file__)
    migrations_path = current_file.parent.parent.parent / "migrations"

    if not migrations_path.exists():
        raise FileNotFoundError(
            f"Migrations folder not found at {migrations_path}"
        )

    # Set basic options
    config.set_main_option("script_location", str(migrations_path))
    config.set_main_option("sqlalchemy.url", db_url)

    # Set schema-specific version table
    version_table = get_schema_version_table(schema_name)
    config.set_main_option("version_table", version_table)
    config.set_main_option("version_table_schema", schema_name)

    return config


def setup_alembic_logging():
    """Set up logging configuration for Alembic."""
    # Reset existing loggers to prevent duplication
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging_config = {
        "version": 1,
        "formatters": {
            "generic": {
                "format": "%(levelname)s [%(name)s] %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "generic",
                "stream": sys.stderr,
            },
        },
        "loggers": {
            "alembic": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,  # Prevent propagation to root logger
            },
            "sqlalchemy": {
                "level": "WARN",
                "handlers": ["console"],
                "propagate": False,  # Prevent propagation to root logger
            },
        },
        "root": {
            "level": "WARN",
            "handlers": ["console"],
        },
    }
    logging.config.dictConfig(logging_config)


async def run_alembic_command(
    command_name: str,
    project_root: Optional[Path] = None,
    schema_name: Optional[str] = None,
) -> int:
    """Run an Alembic command with schema awareness."""
    try:
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent

        if schema_name is None:
            schema_name = os.environ.get("R2R_PROJECT_NAME", "r2r_default")

        # Set up logging
        setup_alembic_logging()

        # Get database URL and create engine
        db_url = get_database_url_from_env()
        engine = create_engine(db_url)

        # Ensure schema exists and has version table
        ensure_schema_exists(engine, schema_name)

        # Create schema-specific config
        config = create_schema_config(project_root, schema_name, db_url)

        click.secho(f"\nRunning command for schema: {schema_name}", fg="blue")

        # Execute the command
        if command_name == "current":
            current_rev = check_current_revision(engine, schema_name)
            if current_rev:
                click.secho(f"Current revision: {current_rev}", fg="green")
            else:
                click.secho("No migrations applied yet.", fg="yellow")
            alembic_command.current(config)
        elif command_name == "history":
            alembic_command.history(config)
        elif command_name.startswith("upgrade"):
            revision = "head"
            if " " in command_name:
                _, revision = command_name.split(" ", 1)
            alembic_command.upgrade(config, revision)
        elif command_name.startswith("downgrade"):
            revision = "-1"
            if " " in command_name:
                _, revision = command_name.split(" ", 1)
            alembic_command.downgrade(config, revision)
        else:
            raise ValueError(f"Unsupported command: {command_name}")

        return 0

    except Exception as e:
        click.secho(f"Error running migration command: {str(e)}", fg="red")
        return 1
