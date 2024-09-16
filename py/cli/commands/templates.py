import os
import shutil
import subprocess

import asyncclick as click

from cli.command_group import cli

REPO_URL = "https://github.com/SciPhi-AI/R2R.git"
TEMPLATES_DIR = "templates"


def get_templates():
    """Fetch list of available templates."""
    temp_dir = "temp_repo"
    try:
        _prepare_temp_directory(temp_dir)
        _clone_and_checkout_templates(temp_dir)
        return _get_template_list()
    except subprocess.CalledProcessError as e:
        raise click.ClickException(
            f"Failed to fetch templates: {e.stderr}"
        ) from e
    except Exception as e:
        raise click.ClickException(
            f"An unexpected error occurred: {str(e)}"
        ) from e
    finally:
        _cleanup(temp_dir)


def _prepare_temp_directory(temp_dir):
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)


def _clone_and_checkout_templates(temp_dir):
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            REPO_URL,
            temp_dir,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    os.chdir(temp_dir)
    subprocess.run(
        ["git", "sparse-checkout", "set", TEMPLATES_DIR],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "checkout"],
        check=True,
        capture_output=True,
        text=True,
    )


def _get_template_list():
    if not os.path.exists(TEMPLATES_DIR):
        raise click.ClickException(
            f"Templates directory '{TEMPLATES_DIR}' not found in the repository."
        )

    if templates := [
        d
        for d in os.listdir(TEMPLATES_DIR)
        if os.path.isdir(os.path.join(TEMPLATES_DIR, d))
    ]:
        return templates
    else:
        raise click.ClickException("No templates found in the repository.")


def _cleanup(temp_dir):
    os.chdir("..")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


def clone_template(template_name, location):
    templates = get_templates()
    if template_name not in templates:
        raise ValueError(
            f"Template '{template_name}' not found. Available templates: {', '.join(templates)}"
        )

    if not location:
        location = template_name

    if os.path.exists(location) and os.listdir(location):
        raise ValueError(
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
    if not os.path.exists(template_dir):
        raise ValueError(
            f"Template directory '{template_name}' not found in the cloned repository."
        )

    for item in os.listdir(template_dir):
        shutil.move(os.path.join(template_dir, item), item)

    shutil.rmtree(TEMPLATES_DIR)
    shutil.rmtree(".git")


@cli.command()
@click.argument("template_name", required=True)
@click.argument("location", required=False)
def clone(template_name, location):
    """Clones a template repository."""
    try:
        clone_template(template_name, location)
        click.echo(
            f"Successfully cloned template '{template_name}' to {location or template_name}"
        )
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"Git operation failed: {e}") from e
    except Exception as e:
        raise click.ClickException(
            f"An unexpected error occurred: {str(e)}"
        ) from e


@cli.command()
def list_templates():
    """Lists all available templates."""
    try:
        templates = get_templates()
        click.echo("Available templates:")
        for template in templates:
            click.echo(f"- {template}")
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.ClickException(str(e)) from e
