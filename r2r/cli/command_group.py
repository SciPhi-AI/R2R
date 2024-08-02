import os

import click

from r2r.main.execution import R2RExecutionWrapper


@click.group()
@click.option(
    "--config-path", default=None, help="Path to the configuration file"
)
@click.option(
    "--config-name", default=None, help="Name of the configuration to use"
)
@click.option("--client-mode", default=True, help="Run in client mode")
@click.option(
    "--base-url",
    default="http://localhost:8000",
    help="Base URL for client mode",
)
@click.pass_context
def cli(ctx, config_path, config_name, client_mode, base_url):
    """R2R CLI for all core operations."""
    if config_path and config_name:
        raise click.UsageError(
            "Cannot specify both config_path and config_name"
        )

    if config_path:
        config_path = os.path.abspath(config_path)

    if ctx.invoked_subcommand != "serve":
        ctx.obj = R2RExecutionWrapper(
            config_path,
            config_name,
            client_mode if ctx.invoked_subcommand != "serve" else False,
            base_url,
        )
    else:
        ctx.obj = {
            "config_path": config_path,
            "config_name": config_name,
            "base_url": base_url,
        }
