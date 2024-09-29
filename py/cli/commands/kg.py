import json
import os
import asyncclick as click
from asyncclick import pass_context

from cli.command_group import cli
from cli.utils.timer import timer


@cli.command()
# TODO - add this once we fully implement project names
# @click.option(
#     "--project-name",
#     required=True,
#     default=os.environ["POSTGRES_PROJECT_NAME"],
#     help="Project name to create graph for.",
# )
@click.option(
    "--collection-id",
    required=True,
    help="Collection ID to create graph for.",
)
@pass_context
def create_graph(
    ctx, collection_id
):
    """
    Create a new graph.
    """
    client = ctx.obj
    with timer():
        response = client.create_graph(collection_id)

    click.echo(json.dumps(response, indent=2))


@cli.command()
@click.option(
    "--collection-id",
    required=True,
    help="Collection ID to enrich graph for.",
)
@click.option(
    "--force-enrichment",
    required=False,
    default=False,
    help="Force enrichment of the graph even if graph creation is still in progress for some documents.",
)
@click.option(
    "--skip-clustering",
    required=False,
    default=False,
    help="Perform leiden clustering on the graph to create communities.",
)
@pass_context
def enrich_graph(
    ctx, collection_id, force_enrichment, skip_clustering
):
    """
    Enrich an existing graph.
    """
    client = ctx.obj
    with timer():
        response = client.enrich_graph(
            collection_id, force_enrichment, skip_clustering
        )

    click.echo(json.dumps(response, indent=2))
