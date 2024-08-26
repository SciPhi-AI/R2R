import click

from cli.command_group import cli
from cli.utils.param_types import JSON
from cli.utils.timer import timer


@cli.command()
@click.option(
    "--query", prompt="Enter your search query", help="The search query"
)
# VectorSearchSettings
@click.option(
    "--use-vector-search",
    is_flag=True,
    default=True,
    help="Whether to use vector search",
)
@click.option(
    "--filters",
    type=JSON,
    help="Filters to apply to the vector search as a JSON",
)
@click.option(
    "--search-limit", default=None, help="Number of search results to return"
)
@click.option(
    "--use-hybrid-search", is_flag=True, help="Perform hybrid search"
)
@click.option(
    "--selected-group-ids", type=JSON, help="Group IDs to search for as a JSON"
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
    "--max-llm-queries-for-global-search", type=JSON, help="Max community size"
)
@click.option("--local-search-limits", type=JSON, help="Local search limits")
@click.pass_obj
def search(client, query, **kwargs):
    """Perform a search query."""
    vector_search_settings = {
        k: v
        for k, v in kwargs.items()
        if k
        in [
            "use_vector_search",
            "filters",
            "search_limit",
            "use_hybrid_search",
            "selected_group_ids",
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
            "kg_search_generation_config",
            "entity_types",
            "relationships",
            "max_community_description_length",
            "max_llm_queries_for_global_search",
            "local_search_limits",
        ]
        and v is not None
    }

    with timer():
        results = client.search(
            query,
            vector_search_settings,
            kg_search_settings,
        )

        if isinstance(results, dict) and "results" in results:
            results = results["results"]

        if "vector_search_results" in results:
            click.echo("Vector search results:")
            for result in results["vector_search_results"]:
                click.echo(result)

        if "kg_search_results" in results and results["kg_search_results"]:
            click.echo("KG search results:")
            for result in results["kg_search_results"]:
                click.echo(result)


@cli.command()
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
    "--selected-group-ids", type=JSON, help="Group IDs to search for as a JSON"
)
# KG Search Settings
@click.option(
    "--use-kg-search", is_flag=True, help="Use knowledge graph search"
)
@click.option("--kg-search-type", default="global", help="Local or Global")
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
    "--max-llm-queries-for-global-search", type=int, help="Max community size"
)
@click.option("--local-search-limits", type=JSON, help="Local search limits")
@click.pass_obj
def rag(client, query, **kwargs):
    """Perform a RAG query."""
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
            "use_hybrid_search",
            "selected_group_ids",
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
            "max_llm_queries_for_global_search",
            "local_search_limits",
        ]
        and v is not None
    }

    if kg_search_settings.get("kg_search_model"):
        kg_search_settings["kg_search_generation_config"] = {
            "model": kg_search_settings.pop("kg_search_model")
        }

    with timer():
        response = client.rag(
            query,
            rag_generation_config,
            vector_search_settings,
            kg_search_settings,
        )

        if rag_generation_config.get("stream"):
            for chunk in response:
                click.echo(chunk, nl=False)
            click.echo()
        else:
            click.echo(response)


# TODO: Implement agent
