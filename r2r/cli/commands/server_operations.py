import json
import os
import platform
import subprocess
import sys

import click
from dotenv import load_dotenv

from r2r.cli.command_group import cli
from r2r.cli.utils.docker_utils import (
    bring_down_docker_compose,
    remove_r2r_network,
    run_docker_serve,
)
from r2r.cli.utils.timer import timer
from r2r.main.execution import R2RExecutionWrapper


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
@click.option("--project-name", default="r2r", help="Project name for Docker")
@click.pass_context
def docker_down(ctx, volumes, remove_orphans, project_name):
    """Bring down the Docker Compose setup and attempt to remove the network if necessary."""
    result = bring_down_docker_compose(project_name, volumes, remove_orphans)

    if result != 0:
        click.echo(
            "An error occurred while bringing down the Docker Compose setup. Attempting to remove the network..."
        )
        remove_r2r_network()
    else:
        click.echo("Docker Compose setup has been successfully brought down.")


@cli.command()
def generate_report():
    """Generate a system report including R2R version, Docker info, and OS details."""

    # Get R2R version
    from importlib.metadata import version

    report = {"r2r_version": version("r2r")}

    # Get Docker info
    try:
        # Get running containers
        docker_ps_output = subprocess.check_output(
            ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}"],
            text=True,
        ).decode("utf-8")
        report["docker_ps"] = [
            dict(zip(["id", "name", "status"], line.split("\t")))
            for line in docker_ps_output.strip().split("\n")
            if line
        ]

        # Get running subnets in Docker
        docker_network_output = subprocess.check_output(
            ["docker", "network", "ls", "--format", "{{.ID}}\t{{.Name}}"],
            text=True,
        ).decode("utf-8")
        networks = [
            dict(zip(["id", "name"], line.split("\t")))
            for line in docker_network_output.strip().split("\n")
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
            ).decode("utf-8")
            if subnet := inspect_output.strip():
                network["subnet"] = subnet
                report["docker_subnets"].append(network)

    except subprocess.CalledProcessError as e:
        report["docker_error"] = f"Error running Docker command: {e}"
    except FileNotFoundError:
        report["docker_error"] = (
            "Docker command not found. Is Docker installed and in PATH?"
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
@click.pass_obj
def health(obj):
    """Check the health of the server."""
    with timer():
        response = obj.health()

    click.echo(response)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to run the server on")
@click.option("--port", default=8000, help="Port to run the server on")
@click.option("--docker", is_flag=True, help="Run using Docker")
@click.option(
    "--exclude-neo4j", is_flag=True, help="Exclude Neo4j from Docker setup"
)
@click.option(
    "--exclude-ollama", is_flag=True, help="Exclude Ollama from Docker setup"
)
@click.option(
    "--exclude-postgres",
    is_flag=True,
    help="Exclude Postgres from Docker setup",
)
@click.option("--project-name", default="r2r", help="Project name for Docker")
@click.option(
    "--config-path",
    type=click.Path(exists=True),
    help="Path to the configuration file",
)
@click.option("--image", help="Docker image to use")
@click.pass_obj
def serve(
    obj,
    host,
    port,
    docker,
    exclude_neo4j,
    exclude_ollama,
    exclude_postgres,
    project_name,
    config_path,
    image,
):
    """Start the R2R server."""
    load_dotenv()

    if config_path:
        config_path = os.path.abspath(config_path)

        # For Windows, convert backslashes to forward slashes and prepend /host_mnt/
        if platform.system() == "Windows":
            config_path = "/host_mnt/" + config_path.replace(
                "\\", "/"
            ).replace(":", "")

        obj["config_path"] = config_path

    if docker:
        run_docker_serve(
            obj,
            host,
            port,
            exclude_neo4j,
            exclude_ollama,
            exclude_postgres,
            project_name,
            config_path,
            image,
        )
    else:
        run_local_serve(obj, host, port)


def run_local_serve(obj, host, port):
    wrapper = R2RExecutionWrapper(**obj, client_mode=False)
    wrapper.serve(host, port)


@cli.command()
def update():
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
        click.echo(f"An unexpected error occurred: {e}")


@cli.command()
def version():
    """Print the version of R2R."""
    from importlib.metadata import version

    click.echo(version("r2r"))
