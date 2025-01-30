import json

import asyncclick as click
from asyncclick import pass_context

from cli.utils.timer import timer
from r2r import R2RAsyncClient, R2RException


@click.group()
def collections():
    """Collections commands."""
    pass


async def execute_collection_command(ctx: click.Context, command: callable, *args, **kwargs) -> None:
    """Utility function to execute a collection command with error handling."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await command(client, *args, **kwargs)
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"R2RException: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {str(e)}", err=True)


@collections.command()
@click.argument("name", required=True, type=str)
@click.option("--description", type=str)
@pass_context
async def create(ctx: click.Context, name: str, description: str = None) -> None:
    """Create a collection."""
    await execute_collection_command(ctx, lambda client: client.collections.create(name=name, description=description))


@collections.command()
@click.option("--ids", multiple=True, help="Collection IDs to fetch")
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of nodes to return. Defaults to 100.")
@pass_context
async def list(ctx: click.Context, ids: tuple[str], offset: int = 0, limit: int = 100) -> None:
    """Get an overview of collections."""
    await execute_collection_command(ctx, lambda client: client.collections.list(ids=list(ids) if ids else None, offset=offset, limit=limit))


@collections.command()
@click.argument("id", required=True, type=str)
@pass_context
async def retrieve(ctx: click.Context, id: str) -> None:
    """Retrieve a collection by ID."""
    await execute_collection_command(ctx, lambda client: client.collections.retrieve(id=id))


@collections.command()
@click.argument("id", required=True, type=str)
@pass_context
async def delete(ctx: click.Context, id: str) -> None:
    """Delete a collection by ID."""
    await execute_collection_command(ctx, lambda client: client.collections.delete(id=id))


@collections.command()
@click.argument("id", required=True, type=str)
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of nodes to return. Defaults to 100.")
@pass_context
async def list_documents(ctx: click.Context, id: str, offset: int = 0, limit: int = 100) -> None:
    """Get an overview of documents in a collection."""
    await execute_collection_command(ctx, lambda client: client.collections.list_documents(id=id, offset=offset, limit=limit))


@collections.command()
@click.argument("id", required=True, type=str)
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of nodes to return. Defaults to 100.")
@pass_context
async def list_users(ctx: click.Context, id: str, offset: int = 0, limit: int = 100) -> None:
    """Get an overview of users in a collection."""
    await execute_collection_command(ctx, lambda client: client.collections.list_users(id=id, offset=offset, limit=limit))
