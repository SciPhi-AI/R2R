import click

from sdk.client import R2RClient


@click.group()
@click.pass_context
def cli(ctx):
    """R2R CLI for all core operations."""

    ctx.obj = R2RClient()
