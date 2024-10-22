import sys

import asyncclick as click

from cli.command_group import cli

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
async def history():
    """Show database migration history."""
    try:
        db_url = get_database_url_from_env(False)
        if not await check_database_connection(db_url):
            click.secho(
                "Database connection failed. Please check your environment variables.",
                fg="red",
            )
            sys.exit(1)

        result = run_alembic_command("history")
        if result != 0:
            click.secho("Failed to get migration history.", fg="red")
            sys.exit(1)
    except Exception as e:
        click.secho(f"Error getting migration history: {str(e)}", fg="red")
        sys.exit(1)


@db.command()
async def current():
    """Show current database revision."""
    try:
        db_url = get_database_url_from_env(False)
        if not await check_database_connection(db_url):
            click.secho(
                "Database connection failed. Please check your environment variables.",
                fg="red",
            )
            sys.exit(1)

        result = run_alembic_command("current")
        if result != 0:
            click.secho("Failed to get current revision.", fg="red")
            sys.exit(1)
    except Exception as e:
        click.secho(f"Error getting current revision: {str(e)}", fg="red")
        sys.exit(1)


@db.command()
@click.option("--revision", help="Upgrade to a specific revision")
async def upgrade(revision):
    """Upgrade database to the latest revision or a specific revision."""
    try:
        db_url = get_database_url_from_env(False)
        if not await check_database_connection(db_url):
            click.secho(
                "Database connection failed. Please check your environment variables.",
                fg="red",
            )
            sys.exit(1)

        click.echo("Running database upgrade...")
        command = f"upgrade {revision}" if revision else "upgrade"
        result = run_alembic_command(command)

        if result == 0:
            click.secho("Database upgrade completed successfully.", fg="green")
        else:
            click.secho("Database upgrade failed.", fg="red")
            sys.exit(1)

    except Exception as e:
        click.secho(f"Unexpected error: {str(e)}", fg="red")
        sys.exit(1)


@db.command()
@click.option("--revision", help="Downgrade to a specific revision")
async def downgrade(revision):
    """Downgrade database to the previous revision or a specific revision."""
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

        click.echo("Running database downgrade...")
        command = f"downgrade {revision}" if revision else "downgrade"
        result = run_alembic_command(command)

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
