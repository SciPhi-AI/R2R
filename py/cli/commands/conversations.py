import json

import asyncclick as click
from asyncclick import pass_context

from cli.utils.timer import timer
from r2r import R2RAsyncClient


@click.group()
def conversations():
    """Conversations commands."""
    pass


@conversations.command()
@pass_context
async def create(ctx: click.Context):
    """Create a conversation."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.conversations.create()

    click.echo(json.dumps(response, indent=2))


@conversations.command()
@click.option("--ids", multiple=True, help="Conversation IDs to fetch")
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
async def list(ctx: click.Context, ids, offset, limit):
    """Get an overview of conversations."""
    client: R2RAsyncClient = ctx.obj
    ids = list(ids) if ids else None

    with timer():
        response = await client.conversations.list(
            ids=ids,
            offset=offset,
            limit=limit,
        )

    for user in response["results"]:  # type: ignore
        click.echo(json.dumps(user, indent=2))


@conversations.command()
@click.argument("id", required=True, type=str)
@pass_context
async def retrieve(ctx: click.Context, id):
    """Retrieve a collection by ID."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.conversations.retrieve(id=id)

    click.echo(json.dumps(response, indent=2))


@conversations.command()
@click.argument("id", required=True, type=str)
@pass_context
async def delete(ctx: click.Context, id):
    """Delete a collection by ID."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.conversations.delete(id=id)

    click.echo(json.dumps(response, indent=2))


@conversations.command()
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
async def list_users(ctx: click.Context, id, offset, limit):
    """Get an overview of collections."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.collections.list_users(
            id=id,
            offset=offset,
            limit=limit,
        )

    for user in response["results"]:  # type: ignore
        click.echo(json.dumps(user, indent=2))
