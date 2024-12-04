import json

import asyncclick as click
from asyncclick import pass_context

from cli.utils.timer import timer
from r2r import R2RAsyncClient


@click.group()
def collections():
    """Collections commands."""
    pass


@collections.command()
@click.argument("name", required=True, type=str)
@click.option("--description", type=str)
@pass_context
async def create(ctx, name, description):
    """Create a collection."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.collections.create(
            name=name,
            description=description,
        )

    click.echo(json.dumps(response, indent=2))


@collections.command()
@click.option("--ids", multiple=True, help="Collection IDs to fetch")
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
async def list(ctx, ids, offset, limit):
    """Get an overview of collections."""
    client: R2RAsyncClient = ctx.obj
    ids = list(ids) if ids else None

    with timer():
        response = await client.collections.list(
            ids=ids,
            offset=offset,
            limit=limit,
        )

    for user in response["results"]:
        click.echo(json.dumps(user, indent=2))


@collections.command()
@click.argument("id", required=True, type=str)
@pass_context
async def retrieve(ctx, id):
    """Retrieve a collection by ID."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.collections.retrieve(id=id)

    click.echo(json.dumps(response, indent=2))


@collections.command()
@click.argument("id", required=True, type=str)
@pass_context
async def delete(ctx, id):
    """Delete a collection by ID."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.collections.delete(id=id)

    click.echo(json.dumps(response, indent=2))


@collections.command()
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
async def list_documents(ctx, id, offset, limit):
    """Get an overview of collections."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.collections.list_documents(
            id=id,
            offset=offset,
            limit=limit,
        )

    for user in response["results"]:
        click.echo(json.dumps(user, indent=2))


@collections.command()
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
async def list_users(ctx, id, offset, limit):
    """Get an overview of collections."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.collections.list_users(
            id=id,
            offset=offset,
            limit=limit,
        )

    for user in response["results"]:
        click.echo(json.dumps(user, indent=2))
