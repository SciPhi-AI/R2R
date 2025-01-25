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

async def check_connection_and_run(schema: str, command: str, revision: str = None) -> int:
    """Check database connection and run the alembic command."""
    db_url = get_database_url_from_env(False)
    if not await check_database_connection(db_url):
        click.secho(
            "Database connection failed. Please check your environment variables.",
            fg="red",
        )
        return 1

    click.echo(f"Running '{command}' for schema {schema or 'default'}...")
    result = await run_alembic_command(command, schema_name=schema, revision=revision)

    if result == 0:
        click.secho(f"Command '{command}' completed successfully.", fg="green")
    else:
        click.secho(f"Command '{command}' failed.", fg="red")

    return result

@db.command()
@click.option("--schema", help="Schema name to operate on (defaults to R2R_PROJECT_NAME)")
async def history(schema: str):
    """Show database migration history for a specific schema."""
    if await check_connection_and_run(schema, "history") != 0:
        sys.exit(1)

@db.command()
@click.option("--schema", help="Schema name to operate on (defaults to R2R_PROJECT_NAME)")
async def current(schema: str):
    """Show current database revision for a specific schema."""
    if await check_connection_and_run(schema, "current") != 0:
        sys.exit(1)

@db.command()
@click.option("--schema", help="Schema name to operate on (defaults to R2R_PROJECT_NAME)")
@click.option("--revision", help="Upgrade to a specific revision")
async def upgrade(schema: str, revision: str):
    """Upgrade database schema to the latest revision or a specific revision."""
    if await check_connection_and_run(schema, f"upgrade {revision}" if revision else "upgrade") != 0:
        sys.exit(1)

@db.command()
@click.option("--schema", help="Schema name to operate on (defaults to R2R_PROJECT_NAME)")
@click.option("--revision", help="Downgrade to a specific revision")
async def downgrade(schema: str, revision: str):
    """Downgrade database schema to the previous revision or a specific revision."""
    if not revision and not click.confirm(
        "No revision specified. This will downgrade the database by one revision. Continue?"
    ):
        return

    if await check_connection_and_run(schema, f"downgrade {revision}" if revision else "downgrade") != 0:
        sys.exit(1)

