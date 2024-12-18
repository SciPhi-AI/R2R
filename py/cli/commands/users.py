import json

import asyncclick as click
from asyncclick import pass_context
from builtins import list as _list
from uuid import UUID

from cli.utils.timer import timer
from r2r import R2RAsyncClient


@click.group()
def users():
    """Users commands."""
    pass


@users.command()
@click.argument("email", required=True, type=str)
@click.argument("password", required=True, type=str)
@pass_context
async def create(ctx: click.Context, email: str, password: str):
    """Create a new user."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.users.create(
            email=email,
            password=password,
        )

    click.echo(json.dumps(response, indent=2))


@users.command()
@click.option("--ids", multiple=True, help="Document IDs to fetch", type=str)
@click.option(
    "--offset",
    default=0,
    help="The offset to start from. Defaults to 0.",
    type=int,
)
@click.option(
    "--limit",
    default=100,
    help="The maximum number of nodes to return. Defaults to 100.",
    type=int,
)
@pass_context
async def list(
    ctx: click.Context,
    ids: tuple[str, ...],
    offset: int,
    limit: int,
):
    """Get an overview of users."""
    client: R2RAsyncClient = ctx.obj
    uuids: _list[str | UUID] | None = (
        [UUID(id_) for id_ in ids] if ids else None
    )

    with timer():
        response = await client.users.list(
            ids=uuids,
            offset=offset,
            limit=limit,
        )

    for user in response["results"]:  # type: ignore
        click.echo(json.dumps(user, indent=2))


@users.command()
@click.argument("id", required=True, type=str)
@pass_context
async def retrieve(ctx: click.Context, id):
    """Retrieve a user by ID."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.users.retrieve(id=id)

    click.echo(json.dumps(response, indent=2))


@users.command()
@pass_context
async def me(ctx: click.Context):
    """Retrieve the current user."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.users.me()

    click.echo(json.dumps(response, indent=2))


@users.command()
@click.argument("id", required=True, type=str)
@click.option(
    "--offset",
    default=0,
    help="The offset to start from. Defaults to 0.",
)
@click.option(
    "--limit",
    default=100,
    help="The maximum number of nodes to return. Defaults to 100.",
)
@pass_context
async def list_collections(ctx: click.Context, id, offset, limit):
    """List collections for a specific user."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.users.list_collections(
            id=id,
            offset=offset,
            limit=limit,
        )

    for collection in response["results"]:  # type: ignore
        click.echo(json.dumps(collection, indent=2))


@users.command()
@click.argument("id", required=True, type=str)
@click.argument("collection_id", required=True, type=str)
@pass_context
async def add_to_collection(ctx: click.Context, id, collection_id):
    """Retrieve a user by ID."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.users.add_to_collection(
            id=id,
            collection_id=collection_id,
        )

    click.echo(json.dumps(response, indent=2))


@users.command()
@click.argument("id", required=True, type=str)
@click.argument("collection_id", required=True, type=str)
@pass_context
async def remove_from_collection(ctx: click.Context, id, collection_id):
    """Retrieve a user by ID."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.users.remove_from_collection(
            id=id,
            collection_id=collection_id,
        )

    click.echo(json.dumps(response, indent=2))
