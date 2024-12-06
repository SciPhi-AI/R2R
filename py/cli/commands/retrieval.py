import json

import asyncclick as click
from asyncclick import pass_context

from cli.utils.param_types import JSON
from cli.utils.timer import timer
from r2r import R2RAsyncClient


@click.group()
def retrieval():
    """Retrieval commands."""
    pass


@retrieval.command()
@click.option(
    "--query", prompt="Enter your search query", help="The search query"
)
@click.option(
    "--limit", default=None, help="Number of search results to return"
)
@click.option(
    "--use-hybrid-search",
    default=None,
    help="Perform hybrid search? Equivalent to `use-semantic-search` and `use-fulltext-search`",
)
@click.option(
    "--use-semantic-search", default=None, help="Perform semantic search?"
)
@click.option(
    "--use-fulltext-search", default=None, help="Perform fulltext search?"
)
@click.option(
    "--filters",
    type=JSON,
    help="""Filters to apply to the vector search as a JSON, e.g. --filters='{"document_id":{"$in":["9fbe403b-c11c-5aae-8ade-ef22980c3ad1", "3e157b3a-8469-51db-90d9-52e7d896b49b"]}}'""",
)
@click.option(
    "--search-strategy",
    type=str,
    default="vanilla",
    help="Vanilla RAG or complex method like query fusion or HyDE.",
)
@click.option(
    "--graph-search-enabled", default=None, help="Use knowledge graph search?"
)
@click.option(
    "--chunk-search-enabled",
    default=None,
    help="Use search over document chunks?",
)
@pass_context
async def search(ctx, query, **kwargs):
    """Perform a search query."""
    client: R2RAsyncClient = ctx.obj
    search_settings = {
        k: v
        for k, v in kwargs.items()
        if k
        in [
            "filters",
            "limit",
            "search_strategy",
            "use_hybrid_search",
            "use_semantic_search",
            "use_fulltext_search",
            "search_strategy",
        ]
        and v is not None
    }
    graph_search_enabled = kwargs.get("graph_search_enabled")
    if graph_search_enabled != None:
        search_settings["graph_settings"] = {"enabled": graph_search_enabled}

    chunk_search_enabled = kwargs.get("chunk_search_enabled")
    if chunk_search_enabled != None:
        search_settings["chunk_settings"] = {"enabled": chunk_search_enabled}

    with timer():
        results = await client.retrieval.search(
            query,
            "custom",
            search_settings,
        )

        if isinstance(results, dict) and "results" in results:
            results = results["results"]

        if "chunk_search_results" in results:
            click.echo("Vector search results:")
            for result in results["chunk_search_results"]:
                click.echo(json.dumps(result, indent=2))

        if (
            "graph_search_results" in results
            and results["graph_search_results"]
        ):
            click.echo("KG search results:")
            for result in results["graph_search_results"]:
                click.echo(json.dumps(result, indent=2))


@retrieval.command()
@click.option(
    "--query", prompt="Enter your search query", help="The search query"
)
@click.option(
    "--limit", default=None, help="Number of search results to return"
)
@click.option(
    "--use-hybrid-search",
    default=None,
    help="Perform hybrid search? Equivalent to `use-semantic-search` and `use-fulltext-search`",
)
@click.option(
    "--use-semantic-search", default=None, help="Perform semantic search?"
)
@click.option(
    "--use-fulltext-search", default=None, help="Perform fulltext search?"
)
@click.option(
    "--filters",
    type=JSON,
    help="""Filters to apply to the vector search as a JSON, e.g. --filters='{"document_id":{"$in":["9fbe403b-c11c-5aae-8ade-ef22980c3ad1", "3e157b3a-8469-51db-90d9-52e7d896b49b"]}}'""",
)
@click.option(
    "--search-strategy",
    type=str,
    default="vanilla",
    help="Vanilla RAG or complex method like query fusion or HyDE.",
)
@click.option(
    "--graph-search-enabled", default=None, help="Use knowledge graph search?"
)
@click.option(
    "--chunk-search-enabled",
    default=None,
    help="Use search over document chunks?",
)
@click.option("--stream", is_flag=True, help="Stream the RAG response")
@click.option("--rag-model", default=None, help="Model for RAG")
@pass_context
async def rag(ctx, query, **kwargs):
    """Perform a RAG query."""
    client: R2RAsyncClient = ctx.obj
    rag_generation_config = {
        "stream": kwargs.get("stream", False),
    }
    if kwargs.get("rag_model"):
        rag_generation_config["model"] = kwargs["rag_model"]

    search_settings = {
        k: v
        for k, v in kwargs.items()
        if k
        in [
            "filters",
            "limit",
            "search_strategy",
            "use_hybrid_search",
            "use_semantic_search",
            "use_fulltext_search",
            "search_strategy",
        ]
        and v is not None
    }
    graph_search_enabled = kwargs.get("graph_search_enabled")
    if graph_search_enabled != None:
        search_settings["graph_settings"] = {"enabled": graph_search_enabled}

    chunk_search_enabled = kwargs.get("chunk_search_enabled")
    if chunk_search_enabled != None:
        search_settings["chunk_settings"] = {"enabled": chunk_search_enabled}

    with timer():
        response = await client.retrieval.rag(
            query=query,
            rag_generation_config=rag_generation_config,
            search_settings={**search_settings},
        )

        if rag_generation_config.get("stream"):
            async for chunk in response:
                click.echo(chunk, nl=False)
            click.echo()
        else:
            click.echo(json.dumps(response["results"]["completion"], indent=2))
