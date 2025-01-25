import json
import asyncclick as click
from asyncclick import pass_context

from cli.utils.param_types import JSON
from cli.utils.timer import timer
from r2r import R2RAsyncClient, R2RException


@click.group()
def retrieval():
    """A group of commands for retrieval operations."""
    pass


@retrieval.command()
@click.option(
    "--query",
    prompt="Enter your search query",
    help="The search query to perform the retrieval."
)
@click.option(
    "--limit",
    default=None,
    help="Specify the maximum number of search results to return."
)
@click.option(
    "--use-hybrid-search",
    default=None,
    help="Enable hybrid search, combining both semantic and fulltext search."
)
@click.option(
    "--use-semantic-search",
    default=None,
    help="Enable semantic search for more contextual results."
)
@click.option(
    "--use-fulltext-search",
    default=None,
    help="Enable fulltext search for exact matches."
)
@click.option(
    "--filters",
    type=JSON,
    help="""Apply filters to the vector search in JSON format.
    Example: --filters='{"document_id":{"$in":["doc_id_1", "doc_id_2"]}}'"""
)
@click.option(
    "--search-strategy",
    type=str,
    default="vanilla",
    help="Specify the search strategy (e.g., vanilla RAG or advanced methods like query fusion or HyDE)."
)
@click.option(
    "--graph-search-enabled",
    default=None,
    help="Enable knowledge graph search."
)
@click.option(
    "--chunk-search-enabled",
    default=None,
    help="Enable search over document chunks."
)
@pass_context
async def search(ctx: click.Context, query, **kwargs):
    """Perform a search query with the specified parameters."""
    search_settings = {
        k: v for k, v in kwargs.items()
        if k in [
            "filters", "limit", "search_strategy",
            "use_hybrid_search", "use_semantic_search",
            "use_fulltext_search"] and v is not None
    }

    # Enable graph and chunk search if specified
    if kwargs.get("graph_search_enabled") is not None:
        search_settings["graph_settings"] = {"enabled": kwargs["graph_search_enabled"]}
    if kwargs.get("chunk_search_enabled") is not None:
        search_settings["chunk_settings"] = {"enabled": kwargs["chunk_search_enabled"]}

    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            results = await client.retrieval.search(query, "custom", search_settings)

            # Extract results and handle output
            if isinstance(results, dict) and "results" in results:
                results = results["results"]

            # Display chunk search results if available
            if "chunk_search_results" in results:
                click.echo("Vector search results:")
                for result in results["chunk_search_results"]:
                    click.echo(json.dumps(result, indent=2))

            # Display graph search results if available
            if "graph_search_results" in results and results["graph_search_results"]:
                click.echo("KG search results:")
                for result in results["graph_search_results"]:
                    click.echo(json.dumps(result, indent=2))
    except R2RException as e:
        click.echo(f"R2R Error: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@retrieval.command()
@click.option(
    "--query",
    prompt="Enter your search query",
    help="The search query for RAG."
)
@click.option(
    "--limit",
    default=None,
    help="Specify the number of search results to return."
)
@click.option(
    "--use-hybrid-search",
    default=None,
    help="Enable hybrid search, combining both semantic and fulltext search."
)
@click.option(
    "--use-semantic-search",
    default=None,
    help="Enable semantic search."
)
@click.option(
    "--use-fulltext-search",
    default=None,
    help="Enable fulltext search."
)
@click.option(
    "--filters",
    type=JSON,
    help="""Apply filters to the vector search in JSON format.
    Example: --filters='{"document_id":{"$in":["doc_id_1", "doc_id_2"]}}'"""
)
@click.option(
    "--search-strategy",
    type=str,
    default="vanilla",
    help="Specify the search strategy for RAG."
)
@click.option(
    "--graph-search-enabled",
    default=None,
    help="Enable knowledge graph search."
)
@click.option(
    "--chunk-search-enabled",
    default=None,
    help="Enable search over document chunks."
)
@click.option("--stream", is_flag=True, help="Stream the RAG response in real-time.")
@click.option("--rag-model", default=None, help="Specify the model to use for RAG.")
@pass_context
async def rag(ctx: click.Context, query, **kwargs):
    """Perform a RAG query with the specified parameters."""
    # Prepare RAG generation configuration
    rag_generation_config = {
        "stream": kwargs.get("stream", False),
    }
    if kwargs.get("rag_model"):
        rag_generation_config["model"] = kwargs["rag_model"]

    # Prepare search settings similar to the search command
    search_settings = {
        k: v for k, v in kwargs.items()
        if k in [
            "filters", "limit", "search_strategy",
            "use_hybrid_search", "use_semantic_search",
            "use_fulltext_search"] and v is not None
    }

    # Enable graph and chunk search if specified
    if kwargs.get("graph_search_enabled") is not None:
        search_settings["graph_settings"] = {"enabled": kwargs["graph_search_enabled"]}
    if kwargs.get("chunk_search_enabled") is not None:
        search_settings["chunk_settings"] = {"enabled": kwargs["chunk_search_enabled"]}

    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.retrieval.rag(
                query=query,
                rag_generation_config=rag_generation_config,
                search_settings=search_settings,
            )

            # Handle streaming response
            if rag_generation_config.get("stream"):
                async for chunk in response:
                    click.echo(chunk, nl=False)
                click.echo()
            else:
                click.echo(json.dumps(response["results"]["completion"], indent=2))
    except R2RException as e:
        click.echo(f"R2R Error: {str(e)}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
