import json

import asyncclick as click
from asyncclick import pass_context

from cli.command_group import cli
from cli.utils.timer import timer


@cli.command()
@click.option(
    "--collection-id",
    required=False,
    default="",
    help="Collection ID to create graph for.",
)
@click.option(
    "--run",
    is_flag=True,
    help="Run the graph creation process.",
)
@click.option(
    "--kg-creation-settings",
    required=False,
    help="Settings for the graph creation process.",
)
@click.option(
    "--force-kg-creation",
    is_flag=True,
    help="Force the graph creation process.",
)
@pass_context
def create_graph(ctx, collection_id, run, kg_creation_settings, force_kg_creation):
    """
    Create a new graph.
    """
    client = ctx.obj

    if kg_creation_settings:
        try:
            kg_creation_settings = json.loads(kg_creation_settings)
        except json.JSONDecodeError:
            click.echo(
                "Error: kg-creation-settings must be a valid JSON string"
            )
            return

    if not run:
        run_type = "estimate"
    else:
        run_type = "run"

    

    with timer():
        response = client.create_graph(
            collection_id, run_type, kg_creation_settings
        )

    click.echo(json.dumps(response, indent=2))


@cli.command()
@click.option(
    "--collection-id",
    required=False,
    default="",
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

    if kg_enrichment_settings:
        try:
            kg_enrichment_settings = json.loads(kg_enrichment_settings)
        except json.JSONDecodeError:
            click.echo(
                "Error: kg-enrichment-settings must be a valid JSON string"
            )
            return

    with timer():
        response = client.enrich_graph(collection_id, kg_enrichment_settings)

    click.echo(json.dumps(response, indent=2))
