import secrets

import click

from cli.command_group import cli


@cli.command()
def generate_private_key():
    """Generate a secure private key for R2R."""
    private_key = secrets.token_urlsafe(32)
    click.echo(f"Generated Private Key: {private_key}")
    click.echo("Keep this key secure and use it as your R2R_SECRET_KEY.")
