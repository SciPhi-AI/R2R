import sys

import asyncclick as click

from ..utils.database_utils import (
    check_database_connection,
    get_database_url_from_env,
    run_alembic_command,
)


@click.group()
def db():
    """Database management commands."""
    pass


@db.command()
@click.option(
    "--schema", help="Schema name to operate on (defaults to R2R_PROJECT_NAME)"
)
async def history(schema):
    """Show database migration history for a specific schema."""
    try:
        db_url = get_database_url_from_env(False)
        if not await check_database_connection(db_url):
            click.secho(
                "Database connection failed. Please check your environment variables.",
                fg="red",
            )
            sys.exit(1)

        result = await run_alembic_command("history", schema_name=schema)
        if result != 0:
            click.secho("Failed to get migration history.", fg="red")
            sys.exit(1)
    except Exception as e:
        click.secho(f"Error getting migration history: {str(e)}", fg="red")
        sys.exit(1)


@db.command()
@click.option(
    "--schema", help="Schema name to operate on (defaults to R2R_PROJECT_NAME)"
)
async def current(schema):
    """Show current database revision for a specific schema."""
    try:
        db_url = get_database_url_from_env(False)
        if not await check_database_connection(db_url):
            click.secho(
                "Database connection failed. Please check your environment variables.",
                fg="red",
            )
            sys.exit(1)

        result = await run_alembic_command("current", schema_name=schema)
        if result != 0:
            click.secho("Failed to get current revision.", fg="red")
            sys.exit(1)
    except Exception as e:
        click.secho(f"Error getting current revision: {str(e)}", fg="red")
        sys.exit(1)


@db.command()
@click.option(
    "--schema", help="Schema name to operate on (defaults to R2R_PROJECT_NAME)"
)
@click.option("--revision", help="Upgrade to a specific revision")
async def upgrade(schema, revision):
    """Upgrade database schema to the latest revision or a specific revision."""
    try:
        db_url = get_database_url_from_env(False)
        if not await check_database_connection(db_url):
            click.secho(
                "Database connection failed. Please check your environment variables.",
                fg="red",
            )
            sys.exit(1)

        click.echo(
            f"Running database upgrade for schema {schema or 'default'}..."
        )
        print(f"Upgrading revision = {revision}")
        command = f"upgrade {revision}" if revision else "upgrade"
        result = await run_alembic_command(command, schema_name=schema)

        if result == 0:
            click.secho("Database upgrade completed successfully.", fg="green")
        else:
            click.secho("Database upgrade failed.", fg="red")
            sys.exit(1)

    except Exception as e:
        click.secho(f"Unexpected error: {str(e)}", fg="red")
        sys.exit(1)


@db.command()
@click.option(
    "--schema", help="Schema name to operate on (defaults to R2R_PROJECT_NAME)"
)
@click.option("--revision", help="Downgrade to a specific revision")
async def downgrade(schema, revision):
    """Downgrade database schema to the previous revision or a specific revision."""
    if not revision:
        if not click.confirm(
            "No revision specified. This will downgrade the database by one revision. Continue?"
        ):
            return

    try:
        db_url = get_database_url_from_env(log=False)
        if not await check_database_connection(db_url):
            click.secho(
                "Database connection failed. Please check your environment variables.",
                fg="red",
            )
            sys.exit(1)

        click.echo(
            f"Running database downgrade for schema {schema or 'default'}..."
        )
        command = f"downgrade {revision}" if revision else "downgrade"
        result = await run_alembic_command(command, schema_name=schema)

        if result == 0:
            click.secho(
                "Database downgrade completed successfully.", fg="green"
            )
        else:
            click.secho("Database downgrade failed.", fg="red")
            sys.exit(1)

    except Exception as e:
        click.secho(f"Unexpected error: {str(e)}", fg="red")
        sys.exit(1)
