import asyncclick as click
from asyncclick import pass_context
from asyncclick.exceptions import Exit

from sdk.client import R2RClient


@click.group()
@click.option(
    "--base-url", default="http://localhost:7272", help="Base URL for the API"
)
@pass_context
async def cli(ctx, base_url):
    """R2R CLI for all core operations."""

    ctx.obj = R2RClient(base_url=base_url)

    # Override the default exit behavior
    def silent_exit(self, code=0):
        if code != 0:
            raise Exit(code)

    ctx.exit = silent_exit.__get__(ctx)
