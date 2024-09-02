import os
import shutil
import subprocess

import click
import requests

from cli.command_group import cli

REPO_URL = "https://github.com/SciPhi-AI/R2R.git"
TEMPLATES_DIR = "templates"


@cli.command()
@click.argument("template_name", required=True)
@click.argument("location", required=False)
def clone(template_name, location):
    """Clones a template repository."""
    try:
        templates = get_templates()
        if template_name not in templates:
            raise click.ClickException(
                f"Template '{template_name}' not found. Available templates: {', '.join(templates)}"
            )

        if not location:
            location = template_name

        if os.path.exists(location) and os.listdir(location):
            raise click.ClickException(
                f"Directory '{location}' already exists and is not empty."
            )

        # Clone the repository
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",  # Shallow clone
                "--filter=blob:none",  # Don't download file contents initially
                "--sparse",  # Enable sparse checkout
                REPO_URL,
                location,
            ],
            check=True,
        )

        os.chdir(location)
        subprocess.run(
            [
                "git",
                "sparse-checkout",
                "set",
                f"{TEMPLATES_DIR}/{template_name}",
            ],
            check=True,
        )
        subprocess.run(["git", "checkout"], check=True)

        template_dir = os.path.join(TEMPLATES_DIR, template_name)
        for item in os.listdir(template_dir):
            shutil.move(os.path.join(template_dir, item), item)

        shutil.rmtree(TEMPLATES_DIR)
        shutil.rmtree(".git")

        click.echo(
            f"Successfully cloned template '{template_name}' to {location}"
        )

    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"Git operation failed: {e}") from e
    except Exception as e:
        raise click.ClickException(f"An error occurred: {e}") from e


def get_templates():
    """Fetch list of available templates."""
    try:
        response = requests.get(
            f"https://api.github.com/repos/SciPhi-AI/R2R/contents/{TEMPLATES_DIR}"
        )
        response.raise_for_status()
        return [
            item["name"] for item in response.json() if item["type"] == "dir"
        ]
    except requests.RequestException as e:
        raise click.ClickException(f"Failed to fetch templates: {e}") from e


@cli.command()
def list_templates():
    """Lists all available templates."""
    try:
        templates = get_templates()
        click.echo("Available templates:")
        for template in templates:
            click.echo(f"- {template}")
    except click.ClickException as e:
        click.echo(str(e), err=True)
