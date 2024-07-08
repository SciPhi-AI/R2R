import json
import time
import uuid

import click

from r2r import GenerationConfig
from r2r.main.execution import R2RExecutionWrapper


class JsonParamType(click.ParamType):
    name = "json"

    def convert(self, value, param, ctx):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            self.fail(f"'{value}' is not a valid JSON string", param, ctx)


JSON = JsonParamType()


@click.group()
@click.option(
    "--config-path", default=None, help="Path to the configuration file"
)
@click.option(
    "--config-name", default=None, help="Name of the configuration to use"
)
@click.option(
    "--client-server-mode", default=True, help="Run in client-server mode"
)
@click.option(
    "--base-url",
    default="http://localhost:8000",
    help="Base URL for client-server mode",
)
@click.pass_context
def cli(ctx, config_path, config_name, client_mode, base_url):
    """R2R CLI for all core operations."""
    if config_path and config_name:
        raise click.UsageError(
            "Cannot specify both config_path and config_name"
        )

    ctx.obj = R2RExecutionWrapper(
        config_path,
        config_name,
        client_mode if ctx.invoked_subcommand != "serve" else False,
        base_url,
    )


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to run the server on")
@click.option("--port", default=8000, help="Port to run the server on")
@click.pass_obj
def serve(obj, host, port):
    """Start the R2R server."""
    obj.serve(host, port)


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

    t0 = time.time()

    # Default to None if empty tuples are provided
    document_ids = None if not document_ids else list(document_ids)
    metadatas = None if not metadatas else list(metadatas)
    versions = None if not versions else list(versions)

    response = obj.ingest_files(
        list(file_paths), document_ids, metadatas, versions
    )
    t1 = time.time()
    click.echo(f"Time taken to ingest files: {t1 - t0:.2f} seconds")
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
    t0 = time.time()

    # Default to None if empty tuples are provided
    metadatas = None if not metadatas else list(metadatas)

    response = obj.update_files(
        list(file_paths), list(document_ids), metadatas
    )
    t1 = time.time()
    click.echo(f"Time taken to ingest files: {t1 - t0:.2f} seconds")
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
@click.option("--kg-agent-model", default="gpt-4o", help="Model for KG agent")
@click.pass_obj
def search(
    obj,
    query,
    use_vector_search,
    search_filters,
    search_limit,
    do_hybrid_search,
    use_kg_search,
    kg_agent_model,
):
    """Perform a search query."""
    kg_agent_generation_config = GenerationConfig(model=kg_agent_model)

    t0 = time.time()

    results = obj.search(
        query,
        use_vector_search,
        search_filters,
        search_limit,
        do_hybrid_search,
        use_kg_search,
        kg_agent_generation_config.dict(),
    )

    if isinstance(results, dict) and "results" in results:
        results = results["results"]

    if "vector_search_results" in results:
        click.echo("Vector search results:")
        for result in results["vector_search_results"]:
            click.echo(result)
    if "kg_search_results" in results and results["kg_search_results"]:
        click.echo("KG search results:", results["kg_search_results"])

    t1 = time.time()
    click.echo(f"Time taken to search: {t1 - t0:.2f} seconds")


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
@click.option("--kg-agent-model", default="gpt-4o", help="Model for KG agent")
@click.option("--stream", is_flag=True, help="Stream the RAG response")
@click.option("--rag-model", default="gpt-4o", help="Model for RAG")
@click.pass_obj
def rag(
    obj,
    query,
    use_vector_search,
    search_filters,
    search_limit,
    do_hybrid_search,
    use_kg_search,
    kg_agent_model,
    stream,
    rag_model,
):
    """Perform a RAG query."""
    kg_agent_generation_config = GenerationConfig(model=kg_agent_model)
    rag_generation_config = GenerationConfig(model=rag_model, stream=stream)

    t0 = time.time()

    response = obj.rag(
        query,
        use_vector_search,
        search_filters,
        search_limit,
        do_hybrid_search,
        use_kg_search,
        kg_agent_generation_config.dict(),
        stream,
        rag_generation_config.dict(),
    )
    if stream:
        for chunk in response:
            click.echo(chunk, nl=False)
        click.echo()
    else:
        click.echo(f"Search Results:\n{response['search_results']}")
        click.echo(f"Completion:\n{response['completion']}")

    t1 = time.time()
    click.echo(f"Time taken for RAG: {t1 - t0:.2f} seconds")


@cli.command()
@click.option("--keys", multiple=True, help="Keys for deletion")
@click.option("--values", multiple=True, help="Values for deletion")
@click.pass_obj
def delete(obj, keys, values):
    """Delete documents based on keys and values."""
    if len(keys) != len(values):
        raise click.UsageError("Number of keys must match number of values")

    t0 = time.time()
    response = obj.delete(list(keys), list(values))
    t1 = time.time()

    click.echo(response)
    click.echo(f"Time taken for deletion: {t1 - t0:.2f} seconds")


@cli.command()
@click.option("--log-type-filter", help="Filter for log types")
@click.pass_obj
def logs(obj, log_type_filter):
    """Retrieve logs with optional type filter."""
    t0 = time.time()
    response = obj.logs(log_type_filter)
    t1 = time.time()

    click.echo(response)
    click.echo(f"Time taken to retrieve logs: {t1 - t0:.2f} seconds")


@cli.command()
@click.option("--document-ids", multiple=True, help="Document IDs to overview")
@click.option("--user-ids", multiple=True, help="User IDs to overview")
@click.pass_obj
def documents_overview(obj, document_ids, user_ids):
    """Get an overview of documents."""
    document_ids = list(document_ids) if document_ids else None
    user_ids = list(user_ids) if user_ids else None

    t0 = time.time()
    response = obj.documents_overview(document_ids, user_ids)
    t1 = time.time()

    for document in response:
        click.echo(document)
    click.echo(f"Time taken to get document overview: {t1 - t0:.2f} seconds")


@cli.command()
@click.argument("document_id")
@click.pass_obj
def document_chunks(obj, document_id):
    """Get chunks of a specific document."""
    t0 = time.time()
    response = obj.document_chunks(document_id)
    t1 = time.time()

    for chunk in response:
        click.echo(chunk)
    click.echo(f"Time taken to get document chunks: {t1 - t0:.2f} seconds")


@cli.command()
@click.pass_obj
def app_settings(obj):
    """Retrieve application settings."""
    t0 = time.time()
    response = obj.app_settings()
    t1 = time.time()

    click.echo(response)
    click.echo(f"Time taken to get app settings: {t1 - t0:.2f} seconds")


@cli.command()
@click.option("--user-ids", multiple=True, help="User IDs to overview")
@click.pass_obj
def users_overview(obj, user_ids):
    """Get an overview of users."""
    user_ids = (
        [uuid.UUID(user_id) for user_id in user_ids] if user_ids else None
    )

    t0 = time.time()
    response = obj.users_overview(user_ids)
    t1 = time.time()

    for user in response:
        click.echo(user)
    click.echo(f"Time taken to get users overview: {t1 - t0:.2f} seconds")


@cli.command()
@click.option(
    "--filters", type=JsonParamType(), help="Filters for analytics as JSON"
)
@click.option(
    "--analysis-types", type=JsonParamType(), help="Analysis types as JSON"
)
@click.pass_obj
def analytics(obj, filters, analysis_types):
    """Retrieve analytics data."""
    t0 = time.time()
    response = obj.analytics(filters, analysis_types)
    t1 = time.time()

    click.echo(response)
    click.echo(f"Time taken to get analytics: {t1 - t0:.2f} seconds")


@cli.command()
@click.option(
    "--no-media",
    is_flag=True,
    default=True,
    help="Exclude media files from ingestion",
)
@click.pass_obj
def ingest_sample_file(obj, no_media):
    t0 = time.time()
    response = obj.ingest_sample_file(no_media=no_media)
    t1 = time.time()

    click.echo(response)
    click.echo(f"Time taken to ingest sample: {t1 - t0:.2f} seconds")


@cli.command()
@click.option(
    "--no-media",
    is_flag=True,
    default=True,
    help="Exclude media files from ingestion",
)
@click.pass_obj
def ingest_sample_files(obj, no_media):
    """Ingest all sample files into R2R."""
    t0 = time.time()
    response = obj.ingest_sample_files(no_media=no_media)
    t1 = time.time()

    click.echo(response)
    click.echo(f"Time taken to ingest sample files: {t1 - t0:.2f} seconds")


def main():
    cli()


if __name__ == "__main__":
    main()
