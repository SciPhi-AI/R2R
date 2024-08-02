import ipaddress
import json
import os
import subprocess
import sys
import time

import click
import requests
from requests.exceptions import RequestException


def bring_down_docker_compose(project_name, volumes, remove_orphans):
    compose_files = get_compose_files()
    docker_command = f"docker compose -f {compose_files['base']} -f {compose_files['neo4j']} -f {compose_files['ollama']} -f {compose_files['postgres']}"
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


def run_docker_serve(
    obj,
    host,
    port,
    exclude_neo4j,
    exclude_ollama,
    exclude_postgres,
    project_name,
    config_path,
    image,
):
    unset_env_vars(exclude_postgres)
    set_config_env_vars(obj)
    set_ollama_api_base(exclude_ollama)

    if exclude_ollama:
        check_external_ollama()

    no_conflict, message = check_subnet_conflict()
    if not no_conflict:
        click.secho(f"Warning: {message}", fg="red", bold=True)
        click.echo("This may cause issues when starting the Docker setup.")
        if not click.confirm("Do you want to continue?", default=False):
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
        config_path,
        image,
    )

    click.echo("Starting Docker Compose setup...")
    os.system(docker_command)


def check_external_ollama():
    ollama_url = "http://localhost:11434/api/version"
    try:
        response = requests.get(ollama_url, timeout=5)
        if response.status_code == 200:
            click.echo("External Ollama instance detected and responsive.")
        else:
            warning_text = click.style("Warning:", fg="red", bold=True)
            click.echo(
                f"{warning_text} External Ollama instance returned unexpected status code: {response.status_code}"
            )
    except RequestException as e:
        warning_text = click.style("Warning:", fg="red", bold=True)
        click.echo(
            f"{warning_text} Unable to connect to external Ollama instance. Error: {e}"
        )
        click.echo(
            "Please ensure Ollama is running externally if you've excluded it from Docker and plan on running Local LLMs."
        )


def unset_env_vars(exclude_postgres=False):
    env_vars = [
        "NEO4J_USER",
        "NEO4J_PASSWORD",
        "NEO4J_URL",
        "NEO4J_DATABASE",
        "OLLAMA_API_BASE",
    ]

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

    for var in env_vars:
        if value := os.environ.get(var):
            warning_text = click.style("Warning:", fg="red", bold=True)
            prompt = (
                f"{warning_text} It's only necessary to set this environment variable when connecting to an instance not managed by R2R.\n"
                f"Add the flag --exclude-postgres to avoid deploying a Postgres instance with R2R.\n"
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


def set_ollama_api_base(exclude_ollama):
    os.environ["OLLAMA_API_BASE"] = (
        "http://host.docker.internal:11434"
        if exclude_ollama
        else "http://ollama:11434"
    )


def get_compose_files():
    package_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."
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


def build_docker_command(
    compose_files,
    host,
    port,
    exclude_neo4j,
    exclude_ollama,
    exclude_postgres,
    project_name,
    config_path,
    image,
):
    command = f"docker compose -f {compose_files['base']}"
    if not exclude_neo4j:
        command += f" -f {compose_files['neo4j']}"
    if not exclude_ollama:
        command += f" -f {compose_files['ollama']}"
    if not exclude_postgres:
        command += f" -f {compose_files['postgres']}"

    command += f" --project-name {project_name}"

    if host != "0.0.0.0" or port != 8000:
        command += f" --build-arg HOST={host} --build-arg PORT={port}"

    if config_path:
        config_dir = os.path.dirname(config_path)
        config_file = os.path.basename(config_path)
        command += f" --build-arg CONFIG_PATH=/app/config/{config_file}"
        command += f" -v {config_dir}:/app/config"

    if image:
        os.environ["R2R_IMAGE"] = image

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
