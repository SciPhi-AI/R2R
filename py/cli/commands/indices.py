import json

import asyncclick as click
from asyncclick import pass_context

from cli.utils.timer import timer
from r2r import R2RAsyncClient, R2RException


@click.group()
def indices():
    """Commands for managing indices."""
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
async def list(ctx: click.Context, offset: int, limit: int):
    """Get an overview of indices."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.indices.list(offset=offset, limit=limit)

        # Check if results are present
        if response["results"]:
            for user in response["results"]:
                click.echo(json.dumps(user, indent=2))
        else:
            click.echo("No indices found.", err=True)
    except R2RException as e:
        click.echo(f"R2R error: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {str(e)}", err=True)


@indices.command()
@click.argument("index_name", required=True, type=str)
@click.argument("table_name", required=True, type=str)
@pass_context
async def retrieve(ctx: click.Context, index_name: str, table_name: str):
    """Retrieve an index by name."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.indices.retrieve(index_name=index_name, table_name=table_name)
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"R2R error: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {str(e)}", err=True)


@indices.command()
@click.argument("index_name", required=True, type=str)
@click.argument("table_name", required=True, type=str)
@pass_context
async def delete(ctx: click.Context, index_name: str, table_name: str):
    """Delete an index by name."""
    client: R2RAsyncClient = ctx.obj

    try:
        # Assuming that the delete operation should be performed here
        with timer():
            response = await client.indices.delete(index_name=index_name, table_name=table_name)

        click.echo(f"Successfully deleted index '{index_name}' from table '{table_name}'.")
    except R2RException as e:
        click.echo(f"R2R error: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {str(e)}", err=True)


if __name__ == "__main__":
    indices()
