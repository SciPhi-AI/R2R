import json

import asyncclick as click
from asyncclick import pass_context

from cli.utils.timer import timer
from r2r import R2RAsyncClient, R2RException


@click.group()
def conversations():
    """Conversations commands."""
    pass


@conversations.command()
@pass_context
async def create(ctx: click.Context):
    """Create a new conversation."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.conversations.create()
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"Failed to create conversation: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred while creating a conversation: {e}", err=True)


@conversations.command()
@click.option("--ids", multiple=True, help="Conversation IDs to fetch")
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of conversations to return. Defaults to 100.")
@pass_context
async def list(ctx: click.Context, ids, offset, limit):
    """List conversations with optional filtering by IDs."""
    client: R2RAsyncClient = ctx.obj
    ids = list(ids) if ids else None

    try:
        with timer():
            response = await client.conversations.list(ids=ids, offset=offset, limit=limit)
        for conversation in response.get("results", []):
            click.echo(json.dumps(conversation, indent=2))
    except R2RException as e:
        click.echo(f"Failed to list conversations: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred while listing conversations: {e}", err=True)


@conversations.command()
@click.argument("id", required=True, type=str)
@pass_context
async def retrieve(ctx: click.Context, id):
    """Retrieve a conversation by its ID."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.conversations.retrieve(id=id)
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"Failed to retrieve conversation with ID '{id}': {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred while retrieving conversation with ID '{id}': {e}", err=True)


@conversations.command()
@click.argument("id", required=True, type=str)
@pass_context
async def delete(ctx: click.Context, id):
    """Delete a conversation by its ID."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.conversations.delete(id=id)
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"Failed to delete conversation with ID '{id}': {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred while deleting conversation with ID '{id}': {e}", err=True)


@conversations.command()
@click.argument("id", required=True, type=str)
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of users to return. Defaults to 100.")
@pass_context
async def list_users(ctx: click.Context, id, offset, limit):
    """List users in a specific conversation."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.conversations.list_users(id=id, offset=offset, limit=limit)
        for user in response.get("results", []):
            click.echo(json.dumps(user, indent=2))
    except R2RException as e:
        click.echo(f"Failed to list users for conversation ID '{id}': {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred while listing users for conversation ID '{id}': {e}", err=True)


if __name__ == "__main__":
    conversations()
