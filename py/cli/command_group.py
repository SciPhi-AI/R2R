from functools import wraps

import asyncclick as click
from asyncclick import pass_context
from asyncclick.exceptions import Exit

from sdk import R2RAsyncClient


def deprecated_command(new_name):
    def decorator(f):
        @wraps(f)
        async def wrapped(*args, **kwargs):
            click.secho(
                f"Warning: This command is deprecated. Please use '{new_name}' instead.",
                fg="yellow",
                err=True,
            )
            return await f(*args, **kwargs)

        return wrapped

    return decorator


@click.group()
@click.option(
    "--base-url", default="http://localhost:7272", help="Base URL for the API"
)
@pass_context
async def cli(ctx, base_url):
    """R2R CLI for all core operations."""

    ctx.obj = R2RAsyncClient(base_url=base_url)

    # Override the default exit behavior
    def silent_exit(self, code=0):
        if code != 0:
            raise Exit(code)

    ctx.exit = silent_exit.__get__(ctx)
