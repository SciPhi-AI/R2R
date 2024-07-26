import json
import os
import secrets
import subprocess
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict

import click
from dotenv import load_dotenv

from r2r.main.execution import R2RExecutionWrapper


class JsonParamType(click.ParamType):
    name = "json"

    def convert(self, value, param, ctx) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            self.fail(f"'{value}' is not a valid JSON string", param, ctx)


JSON = JsonParamType()


@contextmanager
def timer():
    start = time.time()
    yield
    end = time.time()
    click.echo(f"Time taken: {end - start:.2f} seconds")


@click.group()
@click.option(
    "--config-path", default=None, help="Path to the configuration file"
)
@click.option(
    "--config-name", default=None, help="Name of the configuration to use"
)
@click.option("--client-mode", default=True, help="Run in client mode")
@click.option(
    "--base-url",
    default="http://localhost:8000",
    help="Base URL for client mode",
)
@click.pass_context
def cli(ctx, config_path, config_name, client_mode, base_url):
    """R2R CLI for all core operations."""
    if config_path and config_name:
        raise click.UsageError(
            "Cannot specify both config_path and config_name"
        )

    # Convert relative config path to absolute path
    if config_path:
        config_path = os.path.abspath(config_path)

    if ctx.invoked_subcommand != "serve":
        ctx.obj = R2RExecutionWrapper(
            config_path,
            config_name,
            client_mode if ctx.invoked_subcommand != "serve" else False,
            base_url,
        )
    else:
        ctx.obj = {
            "config_path": config_path,
            "config_name": config_name,
            "base_url": base_url,
        }


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

        os.environ["OLLAMA_API_BASE"] = "http://host.docker.internal:11434"

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
@click.argument("file-paths", nargs=-1)
@click.option(
    "--document-ids", multiple=True, help="Document IDs for ingestion"
)
@click.option("--metadatas", multiple=True, help="Metadatas for ingestion")
@click.option(
    "--versions",
    multiple=True,
    help="Starting version for ingested files (e.g. `v1`)",
)
@click.pass_obj
def ingest_files(obj, file_paths, document_ids, metadatas, versions):
    """Ingest files into R2R."""
    with timer():
        # Default to None if empty tuples are provided
        document_ids = list(document_ids) if document_ids else None
        metadatas = list(metadatas) if metadatas else None
        versions = list(versions) if versions else None

        response = obj.ingest_files(
            list(file_paths), document_ids, metadatas, versions
        )
    click.echo(response)


@cli.command()
@click.argument("file-paths", nargs=-1)
@click.option(
    "--document-ids", multiple=True, help="Document IDs for ingestion"
)
@click.option("--metadatas", multiple=True, help="Metadatas for ingestion")
@click.pass_obj
def update_files(obj, file_paths, document_ids, metadatas):
    """Ingest files into R2R."""
    with timer():
        # Default to None if empty tuples are provided
        metadatas = list(metadatas) if metadatas else None

        response = obj.update_files(
            list(file_paths), list(document_ids), metadatas
        )

    click.echo(response)


@cli.command()
@click.option(
    "--query", prompt="Enter your search query", help="The search query"
)
@click.option(
    "--use-vector-search", is_flag=True, default=True, help="Use vector search"
)
@click.option(
    "--search-filters", type=JsonParamType(), help="Search filters as JSON"
)
@click.option(
    "--search-limit", default=10, help="Number of search results to return"
)
@click.option("--do-hybrid-search", is_flag=True, help="Perform hybrid search")
@click.option(
    "--use-kg-search", is_flag=True, help="Use knowledge graph search"
)
@click.option("--kg-search-model", default=None, help="Model for KG agent")
@click.pass_obj
def search(
    obj,
    query,
    use_vector_search,
    search_filters,
    search_limit,
    do_hybrid_search,
    use_kg_search,
    kg_search_model,
):
    """Perform a search query."""
    kg_search_generation_config = {}
    if kg_search_model:
        kg_search_generation_config["model"] = kg_search_model

    with timer():
        results = obj.search(
            query,
            use_vector_search,
            search_filters,
            search_limit,
            do_hybrid_search,
            use_kg_search,
            kg_search_generation_config,
        )

        if isinstance(results, dict) and "results" in results:
            results = results["results"]

        if "vector_search_results" in results:
            click.echo("Vector search results:")
            for result in results["vector_search_results"]:
                click.echo(result)
        if "kg_search_results" in results and results["kg_search_results"]:
            click.echo("KG search results:", results["kg_search_results"])


@cli.command()
@click.option("--query", prompt="Enter your query", help="The query for RAG")
@click.option(
    "--use-vector-search", is_flag=True, default=True, help="Use vector search"
)
@click.option(
    "--search-filters", type=JsonParamType(), help="Search filters as JSON"
)
@click.option(
    "--search-limit", default=10, help="Number of search results to return"
)
@click.option("--do-hybrid-search", is_flag=True, help="Perform hybrid search")
@click.option(
    "--use-kg-search", is_flag=True, help="Use knowledge graph search"
)
@click.option("--kg-search-model", default=None, help="Model for KG agent")
@click.option("--stream", is_flag=True, help="Stream the RAG response")
@click.option("--rag-model", default=None, help="Model for RAG")
@click.pass_obj
def rag(
    obj,
    query,
    use_vector_search,
    search_filters,
    search_limit,
    do_hybrid_search,
    use_kg_search,
    kg_search_model,
    stream,
    rag_model,
):
    """Perform a RAG query."""
    kg_search_generation_config = {}
    if kg_search_model:
        kg_search_generation_config = {"model": kg_search_model}
    rag_generation_config = {"stream": stream}
    if rag_model:
        rag_generation_config["model"] = rag_model

    with timer():
        response = obj.rag(
            query,
            use_vector_search,
            search_filters,
            search_limit,
            do_hybrid_search,
            use_kg_search,
            kg_search_generation_config,
            stream,
            rag_generation_config,
        )
        if stream:
            for chunk in response:
                click.echo(chunk, nl=False)
            click.echo()
        elif obj.client_mode:
            click.echo(f"Search Results:\n{response['search_results']}")
            click.echo(f"Completion:\n{response['completion']}")
        else:
            click.echo(f"Search Results:\n{response.search_results}")
            click.echo(f"Completion:\n{response.completion}")


@cli.command()
@click.option("--keys", multiple=True, help="Keys for deletion")
@click.option("--values", multiple=True, help="Values for deletion")
@click.pass_obj
def delete(obj, keys, values):
    """Delete documents based on keys and values."""
    if len(keys) != len(values):
        raise click.UsageError("Number of keys must match number of values")

    with timer():
        response = obj.delete(list(keys), list(values))

    click.echo(response)


@cli.command()
@click.option("--log-type-filter", help="Filter for log types")
@click.pass_obj
def logs(obj, log_type_filter):
    """Retrieve logs with optional type filter."""
    with timer():
        response = obj.logs(log_type_filter)

    click.echo(response)


@cli.command()
@click.option("--document-ids", multiple=True, help="Document IDs to overview")
@click.option("--user-ids", multiple=True, help="User IDs to overview")
@click.pass_obj
def documents_overview(obj, document_ids, user_ids):
    """Get an overview of documents."""
    document_ids = list(document_ids) if document_ids else None
    user_ids = list(user_ids) if user_ids else None

    with timer():
        response = obj.documents_overview(document_ids, user_ids)

    for document in response:
        click.echo(document)


@cli.command()
@click.argument("document_id")
@click.pass_obj
def document_chunks(obj, document_id):
    """Get chunks of a specific document."""
    with timer():
        response = obj.document_chunks(document_id)

    for chunk in response:
        click.echo(chunk)


@cli.command()
@click.pass_obj
def app_settings(obj):
    """Retrieve application settings."""
    with timer():
        response = obj.app_settings()

    click.echo(response)


@cli.command()
@click.option("--user-ids", multiple=True, help="User IDs to overview")
@click.pass_obj
def users_overview(obj, user_ids):
    """Get an overview of users."""
    user_ids = (
        [uuid.UUID(user_id) for user_id in user_ids] if user_ids else None
    )

    with timer():
        response = obj.users_overview(user_ids)

    for user in response:
        click.echo(user)


@cli.command()
@click.option(
    "--filters", type=JsonParamType(), help="Filters for analytics as JSON"
)
@click.option(
    "--analysis-types", type=JsonParamType(), help="Analysis types as JSON"
)
@click.pass_obj
def analytics(obj, filters: Dict[str, Any], analysis_types: Dict[str, Any]):
    """Retrieve analytics data."""
    with timer():
        response = obj.analytics(filters, analysis_types)

    click.echo(response)


@cli.command()
@click.option(
    "--limit", default=100, help="Limit the number of relationships returned"
)
@click.pass_obj
def inspect_knowledge_graph(obj, limit):
    """Print relationships from the knowledge graph."""
    with timer():
        response = obj.inspect_knowledge_graph(limit)

    click.echo(response)


@cli.command()
@click.option(
    "--no-media",
    default=True,
    help="Exclude media files from ingestion",
)
@click.option("--option", default=0, help="Which file to ingest?")
@click.pass_obj
def ingest_sample_file(obj, no_media, option):
    with timer():
        response = obj.ingest_sample_file(no_media=no_media, option=option)

    click.echo(response)


@cli.command()
@click.option(
    "--no-media",
    default=True,
    help="Exclude media files from ingestion",
)
@click.pass_obj
def ingest_sample_files(obj, no_media):
    """Ingest all sample files into R2R."""
    with timer():
        response = obj.ingest_sample_files(no_media=no_media)

    click.echo(response)


@cli.command()
@click.pass_obj
def health(obj):
    """Check the health of the server."""
    with timer():
        response = obj.health()

    click.echo(response)


@cli.command()
def version():
    """Print the version of R2R."""
    from importlib.metadata import version

    click.echo(version("r2r"))


@cli.command()
def generate_private_key():
    """Generate a secure private key for R2R."""
    private_key = secrets.token_urlsafe(32)
    click.echo(f"Generated Private Key: {private_key}")
    click.echo("Keep this key secure and use it as your R2R_SECRET_KEY.")


def main():
    cli()


if __name__ == "__main__":
    main()
