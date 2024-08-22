import os

import click
from sdk.client import R2RClient


# TODO: refactor this to remove config path and config name
@click.group()
@click.option(
    "--config-path", default=None, help="Path to the configuration file"
)
@click.option(
    "--config-name", default=None, help="Name of the configuration to use"
)
@click.option(
    "--base-url",
    default="http://localhost:8000",
    help="The base URL of the R2R server",
)
@click.pass_context
def cli(ctx, config_path, config_name, base_url):
    """R2R CLI for all core operations."""
    if config_path and config_name:
        raise click.UsageError(
            "Cannot specify both config_path and config_name"
        )

    if config_path:
        config_path = os.path.abspath(config_path)

    ctx.obj = R2RClient(base_url)
