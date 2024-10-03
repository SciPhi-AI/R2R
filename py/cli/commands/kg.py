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
def create_graph(
    ctx, collection_id, run, kg_creation_settings, force_kg_creation
):
    client = ctx.obj

    if kg_creation_settings:
        try:
            kg_creation_settings = json.loads(kg_creation_settings)
        except json.JSONDecodeError:
            click.echo(
                "Error: kg-creation-settings must be a valid JSON string"
            )
            return
    else:
        kg_creation_settings = {}

    run_type = "run" if run else "estimate"

    if force_kg_creation:
        kg_creation_settings = {"force_kg_creation": True}

    with timer():
        response = client.create_graph(
            collection_id=collection_id,
            run_type=run_type,
            kg_creation_settings=kg_creation_settings,
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
    "--run",
    is_flag=True,
    help="Run the graph enrichment process.",
)
@click.option(
    "--force-kg-enrichment",
    is_flag=True,
    help="Force the graph enrichment process.",
)
@click.option(
    "--kg-enrichment-settings",
    required=False,
    help="Settings for the graph enrichment process.",
)
@pass_context
def enrich_graph(
    ctx, collection_id, run, force_kg_enrichment, kg_enrichment_settings
):
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
    else:
        kg_enrichment_settings = {}

    run_type = "run" if run else "estimate"

    if force_kg_enrichment:
        kg_enrichment_settings = {"force_kg_enrichment": True}

    with timer():
        response = client.enrich_graph(
            collection_id, run_type, kg_enrichment_settings
        )

    click.echo(json.dumps(response, indent=2))


@cli.command()
@click.option(
    "--collection-id",
    required=True,
    help="Collection ID to retrieve entities from.",
)
@click.option(
    "--offset",
    type=int,
    default=0,
    help="Offset for pagination.",
)
@click.option(
    "--limit",
    type=int,
    default=100,
    help="Limit for pagination.",
)
@click.option(
    "--entity-ids",
    multiple=True,
    help="Entity IDs to filter by.",
)
@click.option(
    "--with-description",
    is_flag=True,
    help="Include entity descriptions in the response.",
)
@pass_context
def get_entities(
    ctx, collection_id, offset, limit, entity_ids, with_description
):
    """
    Retrieve entities from the knowledge graph.
    """
    client = ctx.obj

    with timer():
        response = client.get_entities(
            collection_id,
            offset,
            limit,
            list(entity_ids),
            with_description,
        )

    click.echo(json.dumps(response, indent=2))


@cli.command()
@click.option(
    "--collection-id",
    required=True,
    help="Collection ID to retrieve triples from.",
)
@click.option(
    "--offset",
    type=int,
    default=0,
    help="Offset for pagination.",
)
@click.option(
    "--limit",
    type=int,
    default=100,
    help="Limit for pagination.",
)
@click.option(
    "--triple-ids",
    multiple=True,
    help="Triple IDs to filter by.",
)
@pass_context
def get_triples(ctx, collection_id, offset, limit, triple_ids):
    """
    Retrieve triples from the knowledge graph.
    """
    client = ctx.obj

    with timer():
        response = client.get_triples(
            collection_id,
            offset,
            limit,
            list(triple_ids),
        )

    click.echo(json.dumps(response, indent=2))
