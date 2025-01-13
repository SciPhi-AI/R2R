import json

import asyncclick as click
from asyncclick import pass_context

from cli.utils.timer import timer
from fuse import FUSEAsyncClient, FUSEException


@click.group()
def indices():
    """Indices commands."""
    pass


@indices.command()
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
async def list(ctx: click.Context, offset, limit):
    """Get an overview of indices."""
    client: FUSEAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.indices.list(
                offset=offset,
                limit=limit,
            )

        for user in response["results"]:  # type: ignore
            click.echo(json.dumps(user, indent=2))
    except FUSEException as e:
        click.echo(str(e), err=True)
    except Exception as e:
        click.echo(str(f"An unexpected error occurred: {e}"), err=True)


@indices.command()
@click.argument("index_name", required=True, type=str)
@click.argument("table_name", required=True, type=str)
@pass_context
async def retrieve(ctx: click.Context, index_name, table_name):
    """Retrieve an index by name."""
    client: FUSEAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.indices.retrieve(
                index_name=index_name,
                table_name=table_name,
            )
        click.echo(json.dumps(response, indent=2))
    except FUSEException as e:
        click.echo(str(e), err=True)
    except Exception as e:
        click.echo(str(f"An unexpected error occurred: {e}"), err=True)


@indices.command()
@click.argument("index_name", required=True, type=str)
@click.argument("table_name", required=True, type=str)
@pass_context
async def delete(ctx: click.Context, index_name, table_name):
    """Delete an index by name."""
    client: FUSEAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.indices.retrieve(
                index_name=index_name,
                table_name=table_name,
            )

        click.echo(json.dumps(response, indent=2))
    except FUSEException as e:
        click.echo(str(e), err=True)
    except Exception as e:
        click.echo(str(f"An unexpected error occurred: {e}"), err=True)
