import json
import os
import platform
import subprocess
import sys
from importlib.metadata import version as get_version

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


@cli.command()
@pass_context
def health(ctx):
    """Check the health of the server."""
    client = ctx.obj
    with timer():
        response = client.health()

    click.echo(response)


@cli.command()
@pass_context
def server_stats(ctx):
    client = ctx.obj
    """Check the server stats."""
    with timer():
        response = client.server_stats()

    click.echo(response)


@cli.command()
@click.option(
    "--offset", default=None, help="Pagination offset. Default is None."
)
@click.option(
    "--limit", default=None, help="Pagination limit. Defaults to 100."
)
@click.option("--run-type-filter", help="Filter for log types")
@pass_context
def logs(ctx, run_type_filter, offset, limit):
    """Retrieve logs with optional type filter."""
    client = ctx.obj
    with timer():
        response = client.logs(
            offset=offset, limit=limit, run_type_filter=run_type_filter
        )

    for log in response["results"]:
        click.echo(f"Run ID: {log['run_id']}")
        click.echo(f"Run Type: {log['run_type']}")
        click.echo(f"Timestamp: {log['timestamp']}")
        click.echo(f"User ID: {log['user_id']}")
        click.echo("Entries:")
        for entry in log["entries"]:
            click.echo(f"  - {entry['key']}: {entry['value'][:100]}")
        click.echo("---")

    click.echo(f"Total runs: {len(response['results'])}")


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
            f"An error occurred while bringing down the {project_name} Docker Compose setup. Attempting to remove the network..."
        )
    else:
        click.echo(
            f"{project_name} Docker Compose setup has been successfully brought down."
        )

    result = bring_down_docker_compose("r2r-full", volumes, remove_orphans)

    # TODO - Clean up the way we do this r2r-down
    click.echo(f"Also attempting to bring down the full deployment")
    if result != 0:
        click.echo(
            f"An error occurred while bringing down the r2r-full Docker Compose setup. Attempting to remove the network..."
        )
    else:
        click.echo(
            f"r2r-full Docker Compose setup has been successfully brought down."
        )


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
@click.option("--port", default=7272, help="Port to run the server on")
@click.option("--docker", is_flag=True, help="Run using Docker")
@click.option(
    "--full",
    is_flag=True,
    help="Run the full R2R compose? This includes Hatchet and Unstructured.",
)
@click.option(
    "--project-name", default="r2r", help="Project name for Docker deployment"
)
@click.option(
    "--config-name", default=None, help="Name of the R2R configuration to use"
)
@click.option(
    "--config-path",
    default=None,
    help="Path to a custom R2R configuration file",
)
@click.option(
    "--build",
    is_flag=True,
    default=False,
    help="Run in debug mode. Only for development.",
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
    host,
    port,
    docker,
    full,
    project_name,
    config_name,
    config_path,
    build,
    image,
    image_env,
    exclude_postgres,
):
    """Start the R2R server."""
    load_dotenv()
    click.echo("Spinning up an R2R deployment...")

    click.echo(f"Running on {host}:{port}, with docker={docker}")

    if full:
        click.echo(
            "Running the full R2R setup which includes `Hatchet` and `Unstructured.io`."
        )
        if project_name == "r2r":  # overwrite project name if full compose
            project_name = "r2r-full"
    else:
        click.echo("Running the lightweight R2R setup.")

    if config_path and config_name:
        raise click.UsageError(
            "Both `config-path` and `config-name` were provided. Please provide only one."
        )
    if build:
        click.echo(
            "`build` flag detected. Building Docker image from local repository..."
        )
    if image and image_env:
        click.echo(
            "WARNING: Both `image` and `image_env` were provided. Using `image`."
        )
    if not image and docker:
        r2r_version = get_version("r2r")

        version_specific_image = f"ragtoriches/{image_env}:{r2r_version}"
        latest_image = f"ragtoriches/{image_env}:latest"

        def image_exists(img):
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
                f"Neither {version_specific_image} nor {latest_image} found in remote registry. Confirm the sanity of your output for `docker manifest inspect ragtoriches/{version_specific_image}` and  `docker manifest inspect ragtoriches/{latest_image}`."
            )
            click.echo(
                "Please pull the required image or build it using the --build flag."
            )
            raise click.Abort()

    if docker:
        os.environ["R2R_IMAGE"] = image

    if build:
        subprocess.run(
            [
                "docker",
                "build",
                "-t",
                image,
                "-f",
                f"Dockerfile",
                ".",
            ],
            check=True,
        )

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
            # Open browser after Docker setup is complete
            import webbrowser

            click.echo("Waiting for all services to become healthy...")

            if not wait_for_container_health(project_name, "r2r"):
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
