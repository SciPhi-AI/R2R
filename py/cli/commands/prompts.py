import json

import asyncclick as click
from asyncclick import pass_context

from cli.utils.timer import timer
from r2r import R2RAsyncClient


@click.group()
def prompts():
    """Prompts commands."""
    pass


@prompts.command()
@pass_context
async def list(ctx):
    """Get an overview of prompts."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.prompts.list()

    for prompt in response["results"]:
        click.echo(json.dumps(prompt, indent=2))


@prompts.command()
@click.argument("name", type=str)
@click.option("--inputs", default=None, type=str)
@click.option("--prompt-override", default=None, type=str)
@pass_context
async def retrieve(ctx, name, inputs, prompt_override):
    """Retrieve an prompts by name."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.prompts.retrieve(
            name=name,
            inputs=inputs,
            prompt_override=prompt_override,
        )

    click.echo(json.dumps(response, indent=2))


@prompts.command()
@click.argument("name", required=True, type=str)
@pass_context
async def delete(ctx, name):
    """Delete an index by name."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.prompts.delete(
            name=name,
        )

    click.echo(json.dumps(response, indent=2))
