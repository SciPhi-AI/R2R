import json
import os

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
@pass_context
def create_graph(ctx, collection_id):
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
    "--kg-enrichment-settings",
    required=False,
    help="Settings for the graph enrichment process.",
)
@pass_context
def enrich_graph(ctx, collection_id, kg_enrichment_settings):
    """
    Enrich an existing graph.
    """
    client = ctx.obj
    with timer():
        response = client.enrich_graph(collection_id, kg_enrichment_settings)

    click.echo(json.dumps(response, indent=2))
