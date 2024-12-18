import json

import asyncclick as click
from asyncclick import pass_context

from cli.utils.timer import timer
from r2r import R2RAsyncClient, R2RException


@click.group()
def prompts():
    """Prompts commands."""
    pass


@prompts.command()
@pass_context
async def list(ctx: click.Context):
    """Get an overview of prompts."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.prompts.list()

        for prompt in response["results"]:  # type: ignore
            click.echo(json.dumps(prompt, indent=2))
    except R2RException as e:
        click.echo(str(e), err=True)
    except Exception as e:
        click.echo(str(f"An unexpected error occurred: {e}"), err=True)


@prompts.command()
@click.argument("name", type=str)
@click.option("--inputs", default=None, type=str)
@click.option("--prompt-override", default=None, type=str)
@pass_context
async def retrieve(ctx: click.Context, name, inputs, prompt_override):
    """Retrieve an prompts by name."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.prompts.retrieve(
                name=name,
                inputs=inputs,
                prompt_override=prompt_override,
            )
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(str(e), err=True)
    except Exception as e:
        click.echo(str(f"An unexpected error occurred: {e}"), err=True)


@prompts.command()
@click.argument("name", required=True, type=str)
@pass_context
async def delete(ctx: click.Context, name):
    """Delete an index by name."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.prompts.delete(
                name=name,
            )
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(str(e), err=True)
    except Exception as e:
        click.echo(str(f"An unexpected error occurred: {e}"), err=True)
