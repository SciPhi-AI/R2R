import click

from sdk.client import R2RClient


@click.group()
@click.option(
    "--base-url", default="http://localhost:8000", help="Base URL for the API"
)
@click.pass_context
def cli(ctx, base_url):
    """R2R CLI for all core operations."""

    ctx.obj = R2RClient(base_url=base_url)
