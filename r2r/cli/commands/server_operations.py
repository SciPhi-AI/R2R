import os
import subprocess
import sys
import time

import click
from dotenv import load_dotenv

from r2r.cli.command_group import cli
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
    package_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", ".."
    )
    compose_yaml = os.path.join(package_dir, "compose.yaml")
    compose_neo4j_yaml = os.path.join(package_dir, "compose.neo4j.yaml")
    compose_ollama_yaml = os.path.join(package_dir, "compose.ollama.yaml")
    if (
        not os.path.exists(compose_yaml)
        or not os.path.exists(compose_neo4j_yaml)
        or not os.path.exists(compose_ollama_yaml)
    ):
        click.echo(
            "Error: Docker Compose files not found in the package directory."
        )
        return

    docker_command = f"docker compose -f {compose_yaml} -f {compose_neo4j_yaml} -f {compose_ollama_yaml}"
    docker_command += f" --project-name {project_name}"

    if volumes:
        docker_command += " --volumes"

    if remove_orphans:
        docker_command += " --remove-orphans"

    docker_command += " down"

    click.echo("Bringing down Docker Compose setup...")
    result = os.system(docker_command)

    if result != 0:
        click.echo(
            "An error occurred while bringing down the Docker Compose setup. Attempting to remove the network..."
        )

        # Get the list of networks
        networks = (
            subprocess.check_output(
                ["docker", "network", "ls", "--format", "{{.Name}}"]
            )
            .decode()
            .split()
        )

        # Find the r2r network
        if r2r_network := next(
            (
                network
                for network in networks
                if network.startswith("r2r_") and "network" in network
            ),
            None,
        ):
            # Try to remove the network
            for _ in range(1):  # Try 1 extra times
                remove_command = f"docker network rm {r2r_network}"
                remove_result = os.system(remove_command)

                if remove_result == 0:
                    click.echo(f"Successfully removed network: {r2r_network}")
                    return
                else:
                    click.echo(
                        f"Failed to remove network: {r2r_network}. Retrying in 5 seconds..."
                    )
                    time.sleep(5)

            click.echo(
                "Failed to remove the network after multiple attempts. Please try the following steps:\n"
                "1. Run 'docker ps' to check for any running containers using this network.\n"
                "2. Stop any running containers with 'docker stop <container_id>'.\n"
                f"3. Try removing the network manually with 'docker network rm {r2r_network}'.\n"
                "4. If the above steps don't work, you may need to restart the Docker daemon."
            )

        else:
            click.echo("Could not find the r2r network to remove.")
    else:
        click.echo("Docker Compose setup has been successfully brought down.")


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
    "--docker-ext-neo4j",
    is_flag=True,
    help="Run using Docker with external Neo4j",
)
@click.option(
    "--docker-ext-ollama",
    is_flag=True,
    help="Run using Docker with external Ollama",
)
@click.option("--project-name", default="r2r", help="Project name for Docker")
@click.pass_obj
def serve(
    obj, host, port, docker, docker_ext_neo4j, docker_ext_ollama, project_name
):
    """Start the R2R server."""
    # Load environment variables from .env file if it exists
    load_dotenv()

    if docker:
        env_vars = [
            "POSTGRES_HOST",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_PORT",
            "POSTGRES_DBNAME",
            "POSTGRES_VECS_COLLECTION",
        ]

        for var in env_vars:
            if value := os.environ.get(var):
                prompt = (
                    f"Warning: Only set a Postgres variable when trying to connect to your own existing database.\n"
                    f"Environment variable {var} is set to '{value}'. Unset it?"
                )
                if click.confirm(prompt, default=True):
                    os.environ[var] = ""
                    click.echo(f"Unset {var}")
                else:
                    click.echo(f"Kept {var}")

        if x := obj.get("config_path", None):
            os.environ["CONFIG_PATH"] = x
        else:
            os.environ["CONFIG_NAME"] = (
                obj.get("config_name", None) or "default"
            )

        if not docker_ext_ollama:
            os.environ["OLLAMA_API_BASE"] = "http://host.docker.internal:11434"
        else:
            os.environ["OLLAMA_API_BASE"] = "http://ollama:11434"

        # Check if compose files exist in the package directory
        package_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", ".."
        )
        compose_yaml = os.path.join(package_dir, "compose.yaml")
        compose_neo4j_yaml = os.path.join(package_dir, "compose.neo4j.yaml")
        compose_ollama_yaml = os.path.join(package_dir, "compose.ollama.yaml")

        if (
            not os.path.exists(compose_yaml)
            or not os.path.exists(compose_neo4j_yaml)
            or not os.path.exists(compose_ollama_yaml)
        ):
            click.echo(
                "Error: Docker Compose files not found in the package directory."
            )
            return

        # Build the docker compose command with the specified host and port
        docker_command = f"docker compose -f {compose_yaml}"
        if docker_ext_neo4j:
            docker_command += f" -f {compose_neo4j_yaml}"
        if docker_ext_ollama:
            docker_command += f" -f {compose_ollama_yaml}"
        if host != "0.0.0.0" or port != 8000:
            docker_command += (
                f" --build-arg HOST={host} --build-arg PORT={port}"
            )

        docker_command += f" --project-name {project_name}"
        docker_command += " up -d"
        os.system(docker_command)
    else:
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
