import ipaddress
import json
import os
import socket
import subprocess
import sys
import time
from typing import Optional

import click
import requests
from requests.exceptions import RequestException

from sdk import R2RClient


def bring_down_docker_compose(project_name, volumes, remove_orphans):
    compose_files = get_compose_files()
    docker_command = f"docker compose pull && docker compose -f {compose_files['base']} -f {compose_files['neo4j']} -f {compose_files['ollama']} -f {compose_files['postgres']}"
    docker_command += f" --project-name {project_name}"

    if volumes:
        docker_command += " --volumes"

    if remove_orphans:
        docker_command += " --remove-orphans"

    docker_command += " down"

    click.echo("Bringing down Docker Compose setup...")
    return os.system(docker_command)


def remove_r2r_network():
    networks = (
        subprocess.check_output(
            ["docker", "network", "ls", "--format", "{{.Name}}"]
        )
        .decode()
        .split()
    )

    r2r_network = next(
        (
            network
            for network in networks
            if network.startswith("r2r_") and "network" in network
        ),
        None,
    )

    if not r2r_network:
        click.echo("Could not find the r2r network to remove.")
        return

    for _ in range(2):  # Try twice
        remove_command = f"docker network rm {r2r_network}"
        if os.system(remove_command) == 0:
            click.echo(f"Successfully removed network: {r2r_network}")
            return
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


def run_local_serve(
    host: str,
    port: int,
    config_name: Optional[str] = None,
    config_path: Optional[str] = None,
) -> None:
    try:
        from r2r import R2R
    except ImportError:
        click.echo(
            "You must install the `r2r core` package to run the R2R server locally."
        )
        sys.exit(1)

    r2r_instance = R2R(config_name=config_name, config_path=config_path)

    if config_name or config_path:
        completion_config = r2r_instance.config.completion
        llm_provider = completion_config.provider
        llm_model = completion_config.generation_config.model
        model_provider = llm_model.split("/")[0]
        check_llm_reqs(llm_provider, model_provider, include_ollama=True)

    available_port = find_available_port(port)

    r2r_instance.serve(host, available_port)


def run_docker_serve(
    host: str,
    port: int,
    exclude_neo4j: bool,
    exclude_ollama: bool,
    exclude_postgres: bool,
    project_name: str,
    image: str,
    config_name: Optional[str] = None,
    config_path: Optional[str] = None,
):
    check_set_docker_env_vars(exclude_neo4j, exclude_postgres)

    if config_path and config_name:
        raise ValueError("Cannot specify both config_path and config_name")

    no_conflict, message = check_subnet_conflict()
    if not no_conflict:
        click.secho(f"Warning: {message}", fg="red", bold=True)
        click.echo("This may cause issues when starting the Docker setup.")
        if not click.confirm("Do you want to continue?", default=True):
            click.echo("Aborting Docker setup.")
            return

    compose_files = get_compose_files()
    docker_command = build_docker_command(
        compose_files,
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

    click.echo("Starting Docker Compose setup...")
    os.system(docker_command)


def check_llm_reqs(llm_provider, model_provider, include_ollama=False):
    providers = {
        "openai": {"env_vars": ["OPENAI_API_KEY"]},
        "anthropic": {"env_vars": ["ANTHROPIC_API_KEY"]},
        "azure": {
            "env_vars": [
                "AZURE_API_KEY",
                "AZURE_API_BASE",
                "AZURE_API_VERSION",
            ]
        },
        "vertex": {
            "env_vars": [
                "GOOGLE_APPLICATION_CREDENTIALS",
                "VERTEX_PROJECT",
                "VERTEX_LOCATION",
            ]
        },
        "bedrock": {
            "env_vars": [
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "AWS_REGION_NAME",
            ]
        },
        "groq": {"env_vars": ["GROQ_API_KEY"]},
        "cohere": {"env_vars": ["COHERE_API_KEY"]},
        "anyscale": {"env_vars": ["ANYSCALE_API_KEY"]},
    }

    for provider, config in providers.items():
        if llm_provider == provider or model_provider == provider:
            if missing_vars := [
                var for var in config["env_vars"] if not os.environ.get(var)
            ]:
                message = f"You have specified `{provider}` as a default LLM provider, but the following environment variables are missing: {', '.join(missing_vars)}. Would you like to continue?"
                if not click.confirm(message, default=False):
                    click.echo("Aborting Docker setup.")
                    sys.exit(1)

    if (
        llm_provider == "ollama" or model_provider == "ollama"
    ) and include_ollama:
        check_external_ollama()


def check_external_ollama(ollama_url="http://localhost:11434/api/version"):

    try:
        response = requests.get(ollama_url, timeout=5)
        if response.status_code == 200:
            click.echo("External Ollama instance detected and responsive.")
        else:
            warning_text = click.style("Warning:", fg="red", bold=True)
            click.echo(
                f"{warning_text} External Ollama instance returned unexpected status code: {response.status_code}"
            )
            if not click.confirm(
                "Do you want to continue without Ollama connection?",
                default=False,
            ):
                click.echo("Aborting Docker setup.")
                sys.exit(1)
    except RequestException as e:
        warning_text = click.style("Warning:", fg="red", bold=True)
        click.echo(
            f"{warning_text} Unable to connect to external Ollama instance. Error: {e}"
        )
        click.echo(
            "Please ensure Ollama is running externally if you've excluded it from Docker and plan on running Local LLMs."
        )
        if not click.confirm(
            "Do you want to continue without Ollama connection?", default=False
        ):
            click.echo("Aborting Docker setup.")
            sys.exit(1)


def check_set_docker_env_vars(exclude_neo4j=False, exclude_postgres=False):
    env_vars = []
    if not exclude_neo4j:
        neo4j_vars = [
            "NEO4J_USER",
            "NEO4J_PASSWORD",
            "NEO4J_URL",
            "NEO4J_DATABASE",
            "OLLAMA_API_BASE",
        ]
        env_vars.extend(neo4j_vars)

    if not exclude_postgres:
        postgres_vars = [
            "POSTGRES_HOST",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_PORT",
            "POSTGRES_DBNAME",
            "POSTGRES_VECS_COLLECTION",
        ]
        env_vars.extend(postgres_vars)

    is_test = (
        "pytest" in sys.modules
        or "unittest" in sys.modules
        or os.environ.get("PYTEST_CURRENT_TEST")
    )

    if not is_test:
        for var in env_vars:
            if value := os.environ.get(var):
                warning_text = click.style("Warning:", fg="red", bold=True)
                prompt = (
                    f"{warning_text} It's only necessary to set this environment variable when connecting to an instance not managed by R2R.\n"
                    f"Set --exclude-postgres=true to avoid deploying a Postgres instance with R2R.\n"
                    f"Environment variable {var} is set to '{value}'. Unset it?"
                )
                if click.confirm(prompt, default=True):
                    os.environ[var] = ""
                    click.echo(f"Unset {var}")
                else:
                    click.echo(f"Kept {var}")


def set_config_env_vars(obj):
    if config_path := obj.get("config_path"):
        os.environ["CONFIG_PATH"] = config_path
    else:
        os.environ["CONFIG_NAME"] = obj.get("config_name") or "default"


def get_compose_files():
    package_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
    )
    compose_files = {
        "base": os.path.join(package_dir, "compose.yaml"),
        "neo4j": os.path.join(package_dir, "compose.neo4j.yaml"),
        "ollama": os.path.join(package_dir, "compose.ollama.yaml"),
        "postgres": os.path.join(package_dir, "compose.postgres.yaml"),
    }

    for name, path in compose_files.items():
        if not os.path.exists(path):
            click.echo(
                f"Error: Docker Compose file {name} not found at {path}"
            )
            sys.exit(1)

    return compose_files


def find_available_port(start_port):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                if port != start_port:
                    click.secho(
                        f"Warning: Port {start_port} is in use. Using {port}",
                        fg="red",
                        bold=True,
                    )
                return port
            port += 1


def build_docker_command(
    compose_files,
    host,
    port,
    exclude_neo4j,
    exclude_ollama,
    exclude_postgres,
    project_name,
    image,
    config_name,
    config_path,
):
    available_port = find_available_port(port)

    command = f"docker compose -f {compose_files['base']}"
    if not exclude_neo4j:
        command += f" -f {compose_files['neo4j']}"
    if not exclude_ollama:
        command += f" -f {compose_files['ollama']}"
    if not exclude_postgres:
        command += f" -f {compose_files['postgres']}"

    command += f" --project-name {project_name}"

    os.environ["PORT"] = str(available_port)
    os.environ["HOST"] = host
    os.environ["TRAEFIK_PORT"] = str(available_port + 1)
    os.environ["R2R_IMAGE"] = image or ""

    if config_name is not None:
        os.environ["CONFIG_NAME"] = config_name
    elif config_path:
        os.environ["CONFIG_PATH"] = (
            os.path.abspath(config_path) if config_path else ""
        )

    command += " up -d"
    return command


def check_subnet_conflict():
    r2r_subnet = ipaddress.ip_network("172.28.0.0/16")

    try:
        networks_output = subprocess.check_output(
            ["docker", "network", "ls", "--format", "{{json .}}"]
        ).decode("utf-8")
        networks = [
            json.loads(line)
            for line in networks_output.splitlines()
            if line.strip()
        ]

        for network in networks:
            network_id = network["ID"]
            network_name = network["Name"]

            try:
                network_info_output = subprocess.check_output(
                    ["docker", "network", "inspect", network_id]
                ).decode("utf-8")

                network_info = json.loads(network_info_output)

                if (
                    not network_info
                    or not isinstance(network_info, list)
                    or len(network_info) == 0
                ):
                    continue

                network_data = network_info[0]
                if "IPAM" in network_data and "Config" in network_data["IPAM"]:
                    ipam_config = network_data["IPAM"]["Config"]
                    if ipam_config is None:
                        continue
                    for config in ipam_config:
                        if "Subnet" in config:
                            existing_subnet = ipaddress.ip_network(
                                config["Subnet"]
                            )
                            if r2r_subnet.overlaps(existing_subnet):
                                return (
                                    False,
                                    f"Subnet conflict detected with network '{network_name}' using subnet {existing_subnet}",
                                )
            except subprocess.CalledProcessError as e:
                click.echo(f"Error inspecting network {network_name}: {e}")
            except json.JSONDecodeError as e:
                click.echo(
                    f"Error parsing network info for {network_name}: {e}"
                )
            except Exception as e:
                click.echo(
                    f"Unexpected error inspecting network {network_name}: {e}"
                )

        return True, "No subnet conflicts detected"
    except subprocess.CalledProcessError as e:
        return False, f"Error checking Docker networks: {e}"
    except json.JSONDecodeError as e:
        return False, f"Error parsing Docker network information: {e}"
    except Exception as e:
        return False, f"Unexpected error while checking Docker networks: {e}"
