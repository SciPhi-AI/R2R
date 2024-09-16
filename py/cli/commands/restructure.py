import json

import asyncclick as click
from asyncclick import pass_context

from cli.command_group import cli
from cli.utils.timer import timer


@cli.command()
@click.option(
    "--document-ids",
    required=False,
    default="",
    help="Document IDs to create graph for (comma-separated)",
)
@pass_context
def create_graph(ctx, document_ids):
    """
    Create a new graph.
    """
    client = ctx.obj
    with timer():
        if document_ids == "":
            document_ids = []
        else:
            document_ids = document_ids.split(",")
        response = client.create_graph(document_ids)

    click.echo(json.dumps(response, indent=2))


@cli.command()
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
def enrich_graph(ctx, force_enrichment, skip_clustering):
    """
    Perform graph enrichment over the entire graph.
    """
    client = ctx.obj
    with timer():
        response = client.enrich_graph(force_enrichment, skip_clustering)

    click.echo(json.dumps(response, indent=2))
