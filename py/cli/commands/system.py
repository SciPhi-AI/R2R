import json
import os
import platform
import subprocess
import sys
from importlib.metadata import version as get_version
from typing import Any, Optional

import asyncclick as click
from asyncclick import pass_context
from dotenv import load_dotenv

from cli.command_group import cli
from cli.utils.docker_utils import (
    bring_down_docker_compose,
    remove_r2r_network,
    run_docker_serve,
    run_local_serve,
    wait_for_container_health,
)
from cli.utils.timer import timer
from r2r import R2RAsyncClient, R2RException


@click.group()
def system():
    """System commands."""
    pass


@cli.command()
@pass_context
async def health(ctx: click.Context) -> None:
    """Check the health of the server."""
    client: R2RAsyncClient = ctx.obj
    try:
        with timer():
            response = await client.system.health()
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"R2R Exception: {str(e)}", err=True)
        raise
    except Exception as e:
        click.echo(
            f"An unexpected error occurred while checking health: {e}",
            err=True,
        )
        raise


@system.command()
@pass_context
async def settings(ctx: click.Context) -> None:
    """Retrieve application settings."""
    client: R2RAsyncClient = ctx.obj
    try:
        with timer():
            response = await client.system.settings()
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"R2R Exception: {str(e)}", err=True)
        raise
    except Exception as e:
        click.echo(
            f"An unexpected error occurred while retrieving settings: {e}",
            err=True,
        )
        raise


@system.command()
@pass_context
async def status(ctx: click.Context) -> None:
    """Get statistics about the server, including the start time, uptime, CPU usage, and memory usage."""
    client: R2RAsyncClient = ctx.obj
    try:
        with timer():
            response = await client.system.status()
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"R2R Exception: {str(e)}", err=True)
        raise
    except Exception as e:
        click.echo(
            f"An unexpected error occurred while retrieving status: {e}",
            err=True,
        )
        raise


@cli.command()
@click.option("--host", default=None, help="Host to run the server on")
@click.option(
    "--port", default=None, type=int, help="Port to run the server on"
)
@click.option("--docker", is_flag=True, help="Run using Docker")
@click.option(
    "--full",
    is_flag=True,
    help="Run the full R2R compose? This includes Hatchet and Unstructured.",
)
@click.option(
    "--project-name", default=None, help="Project name for Docker deployment"
)
@click.option(
    "--config-name", default=None, help="Name of the R2R configuration to use"
)
@click.option(
    "--config-path",
    default=None,
    help="Path to a custom R2R configuration file",
)
@click.option("--image", help="Docker image to use")
@click.option(
    "--image-env",
    default="prod",
    help="Which dev environment to pull the image from?",
)
@click.option(
    "--exclude-postgres",
    is_flag=True,
    default=False,
    help="Excludes creating a Postgres container in the Docker setup.",
)
async def serve(
    host: Optional[str],
    port: Optional[int],
    docker: bool,
    full: bool,
    project_name: Optional[str],
    config_name: Optional[str],
    config_path: Optional[str],
    image: Optional[str],
    image_env: str,
    exclude_postgres: bool,
) -> None:
    """Start the R2R server."""
    load_dotenv()
    click.echo("Spinning up an R2R deployment...")

    host = host or os.getenv("R2R_HOST", "0.0.0.0")
    port = port or int(os.getenv("R2R_PORT", os.getenv("PORT", "7272")))

    click.echo(f"Running on {host}:{port}, with docker={docker}")

    if full:
        click.echo(
            "Running the full R2R setup which includes `Hatchet` and `Unstructured.io`."
        )

    if config_name in ["local_llm", "full_local_llm"]:
        click.secho(
            "WARNING: The `local_llm` and `full_local_llm` configurations are deprecated and will be removed in a future release. Please use `ollama`, `full_ollama`, `lm_studio`, or `full_lm_studio` as your configuration file instead.",
            fg="yellow",
        )

    if config_path and config_name:
        raise click.UsageError(
            "Both `config-path` and `config-name` were provided. Please provide only one."
        )

    if config_name and os.path.isfile(config_name):
        click.echo(
            "Warning: `config-name` corresponds to an existing file. If you intended a custom config, use `config-path`."
        )

    if image and image_env:
        click.echo(
            "WARNING: Both `image` and `image_env` were provided. Using `image`."
        )

    if not image and docker:
        r2r_version = get_version("r2r")
        version_specific_image = f"ragtoriches/{image_env}:{r2r_version}"
        latest_image = f"ragtoriches/{image_env}:latest"

        def image_exists(img: str) -> bool:
            try:
                subprocess.run(
                    ["docker", "manifest", "inspect", img],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return True
            except subprocess.CalledProcessError:
                return False

        if image_exists(version_specific_image):
            click.echo(f"Using image: {version_specific_image}")
            image = version_specific_image
        elif image_exists(latest_image):
            click.echo(
                f"Version-specific image not found. Using latest: {latest_image}"
            )
            image = latest_image
        else:
            click.echo(
                f"Neither {version_specific_image} nor {latest_image} found in remote registry. Please check the Docker images.",
                err=True,
            )
            raise click.Abort()

    if docker:
        os.environ["R2R_IMAGE"] = image

    if config_path:
        config_path = os.path.abspath(config_path)

        # For Windows, convert backslashes to forward slashes and prepend /host_mnt/
        if platform.system() == "Windows":
            drive, path = os.path.splitdrive(config_path)
            config_path = f"/host_mnt/{drive[0].lower()}" + path.replace(
                "\\", "/"
            )

    if docker:
        run_docker_serve(
            host,
            port,
            full,
            project_name,
            image,
            config_name,
            config_path,
            exclude_postgres,
        )
        if (
            "pytest" in sys.modules
            or "unittest" in sys.modules
            or os.environ.get("PYTEST_CURRENT_TEST")
        ):
            click.echo("Test environment detected. Skipping browser open.")
        else:
            import webbrowser

            click.echo("Waiting for all services to become healthy...")
            if not wait_for_container_health(
                project_name or ("r2r-full" if full else "r2r"), "r2r"
            ):
                click.secho(
                    "r2r container failed to become healthy.", fg="red"
                )
                return

            traefik_port = os.environ.get("R2R_DASHBOARD_PORT", "80")
            url = f"http://localhost:{traefik_port}"

            click.secho(f"Navigating to R2R application at {url}.", fg="blue")
            webbrowser.open(url)
    else:
        await run_local_serve(host, port, config_name, config_path, full)


@cli.command()
@click.option(
    "--volumes",
    is_flag=True,
    help="Remove named volumes declared in the `volumes` section of the Compose file",
)
@click.option(
    "--remove-orphans",
    is_flag=True,
    help="Remove containers for services not defined in the Compose file",
)
@click.option(
    "--project-name",
    default=None,
    help="Which Docker Compose project to bring down",
)
def docker_down(
    volumes: bool, remove_orphans: bool, project_name: Optional[str]
) -> None:
    """Bring down the Docker Compose setup and attempt to remove the network if necessary."""
    project_name = project_name or "r2r"
    click.echo(f"Bringing down the `{project_name}` R2R Docker setup...")

    try:
        result = bring_down_docker_compose(
            project_name, volumes, remove_orphans
        )
        if result == 0:
            click.echo(
                f"{project_name} Docker Compose setup has been successfully brought down."
            )
        else:
            click.echo(
                f"An error occurred while bringing down the {project_name} Docker Compose setup. Attempting to remove the network..."
            )
    except Exception as e:
        click.echo(f"Failed to bring down the Docker setup. Error: {e}")

    remove_r2r_network()


@cli.command()
def generate_report() -> None:
    """Generate a system report including R2R version, Docker info, and OS details."""
    report: dict[str, Any] = {"r2r_version": get_version("r2r")}

    # Get Docker info
    try:
        subprocess.run(
            ["docker", "version"], check=True, capture_output=True, timeout=5
        )

        docker_ps_output = subprocess.check_output(
            ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}"],
            text=True,
            timeout=5,
        ).strip()
        report["docker_ps"] = [
            dict(zip(["id", "name", "status"], line.split("\t")))
            for line in docker_ps_output.split("\n")
            if line
        ]

        docker_network_output = subprocess.check_output(
            ["docker", "network", "ls", "--format", "{{.ID}}\t{{.Name}}"],
            text=True,
            timeout=5,
        ).strip()
        networks = [
            dict(zip(["id", "name"], line.split("\t")))
            for line in docker_network_output.split("\n")
            if line
        ]

        report["docker_subnets"] = []
        for network in networks:
            inspect_output = subprocess.check_output(
                [
                    "docker",
                    "network",
                    "inspect",
                    network["id"],
                    "--format",
                    "{{range .IPAM.Config}}{{.Subnet}}{{end}}",
                ],
                text=True,
                timeout=5,
            ).strip()
            if subnet := inspect_output:
                network["subnet"] = subnet
                report["docker_subnets"].append(network)

    except subprocess.CalledProcessError as e:
        report["docker_error"] = f"Error running Docker command: {e}"
    except FileNotFoundError:
        report["docker_error"] = (
            "Docker command not found. Is Docker installed and in PATH?"
        )
    except subprocess.TimeoutExpired:
        report["docker_error"] = (
            "Docker command timed out. Docker might be unresponsive."
        )

    # Get OS information
    report["os_info"] = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }

    click.echo("System Report:")
    click.echo(json.dumps(report, indent=2))


@cli.command()
def update() -> None:
    """Update the R2R package to the latest version."""
    try:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "r2r"]

        click.echo("Updating R2R...")
        result = subprocess.run(
            cmd, check=True, capture_output=True, text=True
        )
        click.echo(result.stdout)
        click.echo("R2R has been successfully updated.")
    except subprocess.CalledProcessError as e:
        click.echo(f"An error occurred while updating R2R: {e}")
        click.echo(e.stderr)
    except Exception as e:
        click.echo(f"An unexpected error occurred during the update: {e}")


@cli.command()
def version() -> None:
    """Reports the SDK version."""
    try:
        r2r_version = get_version("r2r")
        click.echo(json.dumps(r2r_version, indent=2))
    except Exception as e:
        click.echo(
            f"An unexpected error occurred while retrieving the version: {e}",
            err=True,
        )
        raise
