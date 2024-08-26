import json
import os
import platform
import subprocess
import sys

import click
from dotenv import load_dotenv

from cli.command_group import cli
from cli.utils.docker_utils import (
    bring_down_docker_compose,
    remove_r2r_network,
    run_docker_serve,
    run_local_serve,
)
from cli.utils.timer import timer


@cli.command()
@click.pass_obj
def health(client):
    """Check the health of the server."""
    with timer():
        response = client.health()

    click.echo(response)


@cli.command()
@click.pass_obj
def server_stats(client):
    """Check the server stats."""
    with timer():
        response = client.server_stats()

    click.echo(response)


@cli.command()
@click.option("--run-type-filter", help="Filter for log types")
@click.option(
    "--max-runs", default=None, help="Maximum number of runs to fetch"
)
@click.pass_obj
def logs(client, run_type_filter, max_runs):
    """Retrieve logs with optional type filter."""
    with timer():
        response = client.logs(run_type_filter, max_runs)

    for log in response["results"]:
        click.echo(f"Run ID: {log['run_id']}")
        click.echo(f"Run Type: {log['run_type']}")
        click.echo(f"Timestamp: {log['timestamp']}")
        click.echo(f"User ID: {log['user_id']}")
        click.echo("Entries:")
        for entry in log["entries"]:
            click.echo(f"  - {entry['key']}: {entry['value'][:100]}")
        click.echo("---")

    click.echo(f"Total runs: {len(response)}")


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
def docker_down(volumes, remove_orphans, project_name):
    """Bring down the Docker Compose setup and attempt to remove the network if necessary."""
    result = bring_down_docker_compose(project_name, volumes, remove_orphans)
    remove_r2r_network()

    if result != 0:
        click.echo(
            "An error occurred while bringing down the Docker Compose setup. Attempting to remove the network..."
        )
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
@click.option("--host", default="0.0.0.0", help="Host to run the server on")
@click.option("--port", default=8000, help="Port to run the server on")
@click.option("--docker", is_flag=True, help="Run using Docker")
@click.option(
    "--exclude-neo4j", default=False, help="Exclude Neo4j from Docker setup"
)
@click.option(
    "--exclude-ollama", default=True, help="Exclude Ollama from Docker setup"
)
@click.option(
    "--exclude-postgres",
    default=False,
    help="Exclude Postgres from Docker setup",
)
@click.option("--project-name", default="r2r", help="Project name for Docker")
@click.option("--image", help="Docker image to use")
@click.option(
    "--config-name", default=None, help="Name of the R2R configuration to use"
)
@click.option(
    "--config-path",
    default=None,
    help="Path to a custom R2R configuration file",
)
@click.pass_obj
def serve(
    client,
    host,
    port,
    docker,
    exclude_neo4j,
    exclude_ollama,
    exclude_postgres,
    project_name,
    image,
    config_name,
    config_path,
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

    if docker:

        run_docker_serve(
            host,
            port,
            exclude_neo4j,
            exclude_ollama,
            exclude_postgres,
            project_name,
            image,
            config_name,
            config_path,
        )
        if (
            "pytest" in sys.modules
            or "unittest" in sys.modules
            or os.environ.get("PYTEST_CURRENT_TEST")
        ):
            click.echo("Test environment detected. Skipping browser open.")
        else:
            # Open browser after Docker setup is complete
            import time
            import webbrowser

            for i in range(3, 0, -1):
                print(f"Navigating to dashboard in {i} seconds...")
                time.sleep(1)

            traefik_port = os.environ.get("TRAEFIK_PORT", "80")
            url = f"http://localhost:{traefik_port}"
            click.echo(f"Opening browser to {url}")
            webbrowser.open(url)
    else:
        run_local_serve(host, port, config_name, config_path)


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
