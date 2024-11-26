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
# SearchSettings
@click.option(
    "--use-vector-search",
    is_flag=True,
    default=True,
    help="Whether to use vector search",
)
@click.option(
    "--filters",
    type=JSON,
    help="""Filters to apply to the vector search as a JSON, e.g. --filters='{"document_id":{"$in":["9fbe403b-c11c-5aae-8ade-ef22980c3ad1", "3e157b3a-8469-51db-90d9-52e7d896b49b"]}}'""",
)
@click.option(
    "--limit", default=None, help="Number of search results to return"
)
@click.option(
    "--use-hybrid-search", is_flag=True, help="Perform hybrid search"
)
@click.option(
    "--selected-collection-ids",
    type=JSON,
    help="Collection IDs to search for as a JSON",
)
# KGSearchSettings
@click.option(
    "--use-kg-search", is_flag=True, help="Use knowledge graph search"
)
@click.option("--kg-search-type", default=None, help="Local or Global")
@click.option("--kg-search-level", default=None, help="Level of KG search")
@click.option(
    "--kg-search-generation-config",
    type=JSON,
    help="KG search generation config",
)
@click.option(
    "--entity-types", type=JSON, help="Entity types to search for as a JSON"
)
@click.option(
    "--relationships", type=JSON, help="Relationships to search for as a JSON"
)
@click.option(
    "--max-community-description-length",
    type=JSON,
    help="Max community description length",
)
@click.option(
    "--search-strategy",
    type=str,
    help="Vanilla search or complex search method like query fusion or HyDE.",
)
@click.option("--local-search-limits", type=JSON, help="Local search limits")
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
        ]
        and v is not None
    }

    with timer():
        print("kg_search_settings = ", search_settings)
        results = await client.retrieval.search(
            query,
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
@click.option("--query", prompt="Enter your query", help="The query for RAG")
# RAG Generation Config
@click.option("--stream", is_flag=True, help="Stream the RAG response")
@click.option("--rag-model", default=None, help="Model for RAG")
# Vector Search Settings
@click.option(
    "--use-vector-search", is_flag=True, default=True, help="Use vector search"
)
@click.option("--filters", type=JSON, help="Search filters as JSON")
@click.option(
    "--search-limit", default=10, help="Number of search results to return"
)
@click.option(
    "--use-hybrid-search", is_flag=True, help="Perform hybrid search"
)
@click.option(
    "--selected-collection-ids",
    type=JSON,
    help="Collection IDs to search for as a JSON",
)
# KG Search Settings
@click.option(
    "--use-kg-search", is_flag=True, help="Use knowledge graph search"
)
@click.option("--kg-search-type", default="local", help="Local or Global")
@click.option(
    "--kg-search-level",
    default=None,
    help="Level of cluster to use for Global KG search",
)
@click.option("--kg-search-model", default=None, help="Model for KG agent")
@click.option(
    "--entity-types", type=JSON, help="Entity types to search for as a JSON"
)
@click.option(
    "--relationships", type=JSON, help="Relationships to search for as a JSON"
)
@click.option(
    "--max-community-description-length",
    type=int,
    help="Max community description length",
)
@click.option(
    "--search-strategy",
    type=str,
    default="vanilla",
    help="Vanilla RAG or complex method like query fusion or HyDE.",
)
@click.option("--local-search-limits", type=JSON, help="Local search limits")
@pass_context
async def rag(ctx, query, **kwargs):
    """Perform a RAG query."""
    client: R2RAsyncClient = ctx.obj
    rag_generation_config = {
        "stream": kwargs.get("stream", False),
    }
    if kwargs.get("rag_model"):
        rag_generation_config["model"] = kwargs["rag_model"]

    vector_search_settings = {
        k: v
        for k, v in kwargs.items()
        if k
        in [
            "use_vector_search",
            "filters",
            "search_limit",
            "limit",
            "use_hybrid_search",
            "selected_collection_ids",
            "search_strategy",
        ]
        and v is not None
    }

    kg_search_settings = {
        k: v
        for k, v in kwargs.items()
        if k
        in [
            "use_kg_search",
            "kg_search_type",
            "kg_search_level",
            "kg_search_model",
            "entity_types",
            "relationships",
            "max_community_description_length",
            "limits",
        ]
        and v is not None
    }

    if kg_search_settings.get("kg_search_model"):
        kg_search_settings["generation_config"] = {
            "model": kg_search_settings.pop("kg_search_model")
        }

    with timer():
        response = await client.retrieval.rag(
            query=query,
            rag_generation_config=rag_generation_config,
            vector_search_settings=vector_search_settings,
            kg_search_settings=kg_search_settings,
        )

        if rag_generation_config.get("stream"):
            async for chunk in response:
                click.echo(chunk, nl=False)
            click.echo()
        else:
            click.echo(json.dumps(response, indent=2))
