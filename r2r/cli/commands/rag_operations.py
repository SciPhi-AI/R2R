import click

from r2r.cli.command_group import cli
from r2r.cli.utils.param_types import JSON
from r2r.cli.utils.timer import timer


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
@click.option("--query", prompt="Enter your query", help="The query for RAG")
@click.option(
    "--use-vector-search", is_flag=True, default=True, help="Use vector search"
)
@click.option("--search-filters", type=JSON, help="Search filters as JSON")
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
@click.option(
    "--query", prompt="Enter your search query", help="The search query"
)
@click.option(
    "--use-vector-search", is_flag=True, default=True, help="Use vector search"
)
@click.option("--search-filters", type=JSON, help="Search filters as JSON")
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
