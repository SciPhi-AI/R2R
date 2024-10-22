import configparser
import logging.config
import os
import sys
from pathlib import Path
from typing import Dict, Optional

import alembic.config
import asyncclick as click
from alembic import command as alembic_command
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError


def run_alembic_command(
    command_name: str, project_root: Optional[Path] = None
) -> int:
    """Run an Alembic command with the configured environment."""
    try:
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent

        # Set up logging first
        setup_alembic_logging()

        # Create a new config
        config = alembic.config.Config()
        config.set_main_option(
            "script_location", str(project_root / "migrations")
        )
        config.set_main_option("sqlalchemy.url", get_database_url_from_env())

        # Execute the appropriate command
        if command_name == "current":
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


def setup_alembic_logging():
    """Set up logging configuration for Alembic."""
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
            },
            "sqlalchemy": {
                "level": "WARN",
                "handlers": ["console"],
            },
        },
        "root": {
            "level": "WARN",
            "handlers": ["console"],
        },
    }
    logging.config.dictConfig(logging_config)


def get_default_db_vars() -> Dict[str, str]:
    """Get default database environment variables."""
    return {
        "R2R_POSTGRES_HOST": "localhost",
        "R2R_POSTGRES_PORT": "5432",
        "R2R_POSTGRES_DBNAME": "postgres",
        "R2R_POSTGRES_USER": "postgres",
        "R2R_POSTGRES_PASSWORD": "postgres",
        "R2R_PROJECT_NAME": "r2r_default",
    }


def get_database_url_from_env(log: bool = True) -> str:
    """Construct database URL from R2R environment variables, using defaults if not set."""
    defaults = get_default_db_vars()

    env_vars = {}
    for var_name, default_value in defaults.items():
        value = os.environ.get(var_name, default_value)
        if value == default_value:
            if log:
                click.secho(
                    f"Using default value for {var_name}: {value}", fg="yellow"
                )
        else:
            if log:
                click.secho(f"Using value for {var_name}: {value}", fg="red")
        env_vars[var_name] = value

    return (
        f"postgresql://{env_vars['R2R_POSTGRES_USER']}:{env_vars['R2R_POSTGRES_PASSWORD']}"
        f"@{env_vars['R2R_POSTGRES_HOST']}:{env_vars['R2R_POSTGRES_PORT']}"
        f"/{env_vars['R2R_POSTGRES_DBNAME']}"
    )


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


# # cli/utils/database_utils.py
# import os
# import configparser
# from pathlib import Path
# import asyncclick as click
# import alembic.config
# import sys
# from typing import Dict, Optional
# import logging.config
# from sqlalchemy import create_engine
# from sqlalchemy.exc import OperationalError


# def get_default_db_vars() -> Dict[str, str]:
#     """Get default database environment variables."""
#     return {
#         "R2R_POSTGRES_HOST": "localhost",
#         "R2R_POSTGRES_PORT": "5432",
#         "R2R_POSTGRES_DBNAME": "postgres",
#         "R2R_POSTGRES_USER": "postgres",
#         "R2R_POSTGRES_PASSWORD": "postgres",
#     }


# def get_database_url_from_env() -> str:
#     """Construct database URL from R2R environment variables, using defaults if not set."""
#     defaults = get_default_db_vars()

#     env_vars = {}
#     for var_name, default_value in defaults.items():
#         value = os.environ.get(var_name, default_value)
#         if value == default_value:
#             click.secho(
#                 f"Using default value for {var_name}: {value}",
#                 fg="yellow"
#             )
#         env_vars[var_name] = value

#     return (
#         f"postgresql://{env_vars['R2R_POSTGRES_USER']}:{env_vars['R2R_POSTGRES_PASSWORD']}"
#         f"@{env_vars['R2R_POSTGRES_HOST']}:{env_vars['R2R_POSTGRES_PORT']}"
#         f"/{env_vars['R2R_POSTGRES_DBNAME']}"
#     )


# def setup_alembic_logging():
#     """Set up logging configuration for Alembic."""
#     logging_config = {
#         'version': 1,
#         'formatters': {
#             'generic': {
#                 'format': '%(levelname)s [%(name)s] %(message)s',
#                 'datefmt': '%H:%M:%S',
#             },
#         },
#         'handlers': {
#             'console': {
#                 'class': 'logging.StreamHandler',
#                 'formatter': 'generic',
#                 'stream': sys.stderr,
#             },
#         },
#         'loggers': {
#             'alembic': {
#                 'level': 'INFO',
#                 'handlers': ['console'],
#             },
#             'sqlalchemy': {
#                 'level': 'WARN',
#                 'handlers': ['console'],
#             },
#         },
#         'root': {
#             'level': 'WARN',
#             'handlers': ['console'],
#         },
#     }
#     logging.config.dictConfig(logging_config)


# async def check_database_connection(db_url: str) -> bool:
#     """Check if we can connect to the database."""
#     try:
#         engine = create_engine(db_url)
#         with engine.connect():
#             return True
#     except OperationalError as e:
#         click.secho(f"Could not connect to database: {str(e)}", fg="red")
#         if "Connection refused" in str(e):
#             click.secho(
#                 "Make sure PostgreSQL is running and accessible with the provided credentials.",
#                 fg="yellow"
#             )
#         return False
#     except Exception as e:
#         click.secho(f"Unexpected error checking database connection: {str(e)}", fg="red")
#         return False

# def run_alembic_command(command: str, project_root: Optional[Path] = None) -> int:
#     """Run an Alembic command with the configured environment."""
#     try:
#         if project_root is None:
#             project_root = Path(__file__).parent.parent.parent

#         # Set up logging first
#         setup_alembic_logging()

#         # Create a new config
#         config = alembic.config.Config()
#         config.set_main_option("script_location", str(project_root / "migrations"))
#         config.set_main_option("sqlalchemy.url", get_database_url_from_env())

#         # Import alembic commands
#         from alembic import command

#         # Parse the command string and execute appropriate command
#         if command == "current":
#             command.current(config)
#         elif command == "history":
#             command.history(config)
#         elif isinstance(command, str) and command.startswith("upgrade"):
#             if " " in command:
#                 _, revision = command.split(" ", 1)
#             else:
#                 revision = "head"
#             command.upgrade(config, revision)
#         elif isinstance(command, str) and command.startswith("downgrade"):
#             if " " in command:
#                 _, revision = command.split(" ", 1)
#             else:
#                 revision = "-1"
#             command.downgrade(config, revision)
#         else:
#             raise ValueError(f"Unsupported command: {command}")

#         return 0
#     except Exception as e:
#         click.secho(f"Error running migration command: {str(e)}", fg="red")
#         return 1
