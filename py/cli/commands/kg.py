import json

import asyncclick as click
from asyncclick import pass_context

from cli.command_group import cli
from cli.utils.timer import timer


@cli.command()
@click.option(
    "--collection-id",
    required=True,
    help="Collection ID to create graph for.",
)
@click.option(
    "--document-ids",
    required=False,
    default=None,
    help="Document IDs to create graph for (comma-separated)",
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
def create_graph(
    ctx, collection_id, document_ids, force_enrichment, skip_clustering
):
    """
    Create a new graph.
    """
    client = ctx.obj
    with timer():
        if document_ids is None:
            document_ids = []
        else:
            document_ids = document_ids.split(",")
        response = client.create_graph(
            collection_id, document_ids, force_enrichment, skip_clustering
        )

    click.echo(json.dumps(response, indent=2))
