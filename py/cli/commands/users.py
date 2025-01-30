import json
from builtins import list as _list
from uuid import UUID

import asyncclick as click
from asyncclick import pass_context

from cli.utils.timer import timer
from r2r import R2RAsyncClient, R2RException


@click.group()
def users():
    """Commands for user management."""
    pass


@users.command()
@click.argument("email", type=str, required=True)
@click.argument("password", type=str, required=True)
@pass_context
async def create(ctx: click.Context, email: str, password: str):
    """Create a new user with the specified email and password."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.users.create(
                email=email, password=password
            )
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"Error creating user: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@users.command()
@click.option("--ids", multiple=True, type=str, help="Document IDs to fetch.")
@click.option(
    "--offset", default=0, type=int, help="Offset to start from (default: 0)."
)
@click.option(
    "--limit",
    default=100,
    type=int,
    help="Maximum number of users to return (default: 100).",
)
@pass_context
async def list(
    ctx: click.Context, ids: tuple[str, ...], offset: int, limit: int
):
    """Get an overview of users."""
    uuids: _list[UUID] = [UUID(id_) for id_ in ids] if ids else None
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.users.list(
                ids=uuids, offset=offset, limit=limit
            )

        for user in response.get("results", []):
            click.echo(json.dumps(user, indent=2))
    except R2RException as e:
        click.echo(f"Error fetching users: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@users.command()
@click.argument("id", type=str, required=True)
@pass_context
async def retrieve(ctx: click.Context, id: str):
    """Retrieve a user by their ID."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.users.retrieve(id=id)
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"Error retrieving user: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@users.command()
@pass_context
async def me(ctx: click.Context):
    """Retrieve the current authenticated user."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.users.me()
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"Error retrieving current user: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@users.command()
@click.argument("id", type=str, required=True)
@click.option(
    "--offset", default=0, type=int, help="Offset to start from (default: 0)."
)
@click.option(
    "--limit",
    default=100,
    type=int,
    help="Maximum number of collections to return (default: 100).",
)
@pass_context
async def list_collections(
    ctx: click.Context, id: str, offset: int, limit: int
):
    """List collections for a specific user."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.users.list_collections(
                id=id, offset=offset, limit=limit
            )

        for collection in response.get("results", []):
            click.echo(json.dumps(collection, indent=2))
    except R2RException as e:
        click.echo(
            f"Error listing collections for user ID {id}: {str(e)}", err=True
        )
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@users.command()
@click.argument("id", type=str, required=True)
@click.argument("collection_id", type=str, required=True)
@pass_context
async def add_to_collection(ctx: click.Context, id: str, collection_id: str):
    """Add a user to a specific collection."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.users.add_to_collection(
                id=id, collection_id=collection_id
            )
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(
            f"Error adding user ID {id} to collection ID {collection_id}: {str(e)}",
            err=True,
        )
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@users.command()
@click.argument("id", type=str, required=True)
@click.argument("collection_id", type=str, required=True)
@pass_context
async def remove_from_collection(
    ctx: click.Context, id: str, collection_id: str
):
    """Remove a user from a specific collection."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.users.remove_from_collection(
                id=id, collection_id=collection_id
            )
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(
            f"Error removing user ID {id} from collection ID {collection_id}: {str(e)}",
            err=True,
        )
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
