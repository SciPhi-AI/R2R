import json
import logging

import asyncclick as click
from asyncclick import pass_context

from cli.utils.timer import timer
from r2r import R2RAsyncClient, R2RException

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.group()
def prompts():
    """Commands for managing prompts."""
    pass

@prompts.command()
@pass_context
async def list(ctx: click.Context) -> None:
    """Get an overview of all prompts."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            logger.info("Listing all prompts.")
            response = await client.prompts.list()

        for prompt in response.get("results", []):
            click.echo(json.dumps(prompt, indent=2))
    except R2RException as e:
        logger.error(f"R2RException occurred: {e}")
        click.echo(str(e), err=True)
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        click.echo(f"An unexpected error occurred: {e}", err=True)

@prompts.command()
@click.argument("name", type=str)
@click.option("--inputs", default=None, type=str, help="Inputs for the prompt.")
@click.option("--prompt-override", default=None, type=str, help="Override for the prompt.")
@pass_context
async def retrieve(ctx: click.Context, name: str, inputs: str = None, prompt_override: str = None) -> None:
    """Retrieve a prompt by its name."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            logger.info(f"Retrieving prompt: {name}")
            response = await client.prompts.retrieve(
                name=name,
                inputs=inputs,
                prompt_override=prompt_override,
            )
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        logger.error(f"R2RException occurred: {e}")
        click.echo(str(e), err=True)
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        click.echo(f"An unexpected error occurred: {e}", err=True)

@prompts.command()
@click.argument("name", required=True, type=str)
@pass_context
async def delete(ctx: click.Context, name: str) -> None:
    """Delete a prompt by its name."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            logger.info(f"Deleting prompt: {name}")
            response = await client.prompts.delete(name=name)
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        logger.error(f"R2RException occurred: {e}")
        click.echo(str(e), err=True)
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
        click.echo(f"An unexpected error occurred: {e}", err=True)
