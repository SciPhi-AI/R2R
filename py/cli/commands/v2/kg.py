import json

import asyncclick as click
from asyncclick import pass_context

from cli.command_group import cli
from cli.utils.timer import timer
from r2r import R2RAsyncClient


# TODO
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
async def create_graph(
    ctx, collection_id, run, graph_creation_settings, force_kg_creation
):
    client: R2RAsyncClient = ctx.obj

    if graph_creation_settings:
        try:
            graph_creation_settings = json.loads(graph_creation_settings)
        except json.JSONDecodeError:
            click.echo(
                "Error: kg-creation-settings must be a valid JSON string"
            )
            return
    else:
        graph_creation_settings = {}

    run_type = "run" if run else "estimate"

    if force_kg_creation:
        graph_creation_settings = {"force_kg_creation": True}

    with timer():
        response = await client.create_graph(
            collection_id=collection_id,
            run_type=run_type,
            graph_creation_settings=graph_creation_settings,
        )

    click.echo(json.dumps(response, indent=2))


# TODO
@cli.command()
@click.option(
    "--collection-id",
    required=False,
    help="Collection ID to deduplicate entities for.",
)
@click.option(
    "--run",
    is_flag=True,
    help="Run the deduplication process.",
)
@click.option(
    "--force-deduplication",
    is_flag=True,
    help="Force the deduplication process.",
)
@click.option(
    "--deduplication-settings",
    required=False,
    help="Settings for the deduplication process.",
)
@pass_context
async def deduplicate_entities(
    ctx, collection_id, run, force_deduplication, deduplication_settings
):
    """
    Deduplicate entities in the knowledge graph.
    """
    client: R2RAsyncClient = ctx.obj

    if deduplication_settings:
        try:
            deduplication_settings = json.loads(deduplication_settings)
        except json.JSONDecodeError:
            click.echo(
                "Error: deduplication-settings must be a valid JSON string"
            )
            return
    else:
        deduplication_settings = {}

    run_type = "run" if run else "estimate"

    if force_deduplication:
        deduplication_settings = {"force_deduplication": True}

    with timer():
        response = await client.deduplicate_entities(
            collection_id, run_type, deduplication_settings
        )

    click.echo(json.dumps(response, indent=2))


# TODO
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
async def enrich_graph(
    ctx, collection_id, run, force_kg_enrichment, graph_enrichment_settings
):
    """
    Enrich an existing graph.
    """
    client: R2RAsyncClient = ctx.obj

    if graph_enrichment_settings:
        try:
            graph_enrichment_settings = json.loads(graph_enrichment_settings)
        except json.JSONDecodeError:
            click.echo(
                "Error: kg-enrichment-settings must be a valid JSON string"
            )
            return
    else:
        graph_enrichment_settings = {}

    run_type = "run" if run else "estimate"

    if force_kg_enrichment:
        graph_enrichment_settings = {"force_kg_enrichment": True}

    with timer():
        response = await client.enrich_graph(
            collection_id, run_type, graph_enrichment_settings
        )

    click.echo(json.dumps(response, indent=2))


# TODO
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
    "--entity-level",
    default="document",
    help="Entity level to filter by.",
)
@pass_context
async def get_entities(
    ctx, collection_id, offset, limit, entity_ids, entity_level
):
    """
    Retrieve entities from the knowledge graph.
    """
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.get_entities(
            offset=offset,
            limit=limit,
            entity_level=entity_level,
            collection_id=collection_id,
            entity_ids=list(entity_ids),
        )

    click.echo(json.dumps(response, indent=2))


# TODO
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
    "--relationship-ids",
    multiple=True,
    help="Relationship IDs to filter by.",
)
@click.option(
    "--entity-names",
    multiple=True,
    help="Entity names to filter by.",
)
@pass_context
async def get_triples(
    ctx, collection_id, offset, limit, relationship_ids, entity_names
):
    """
    Retrieve relationships from the knowledge graph.
    """
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.get_relationships(
            collection_id,
            offset,
            limit,
            list(entity_names),
            list(relationship_ids),
        )

    click.echo(json.dumps(response, indent=2))


# TODO
@cli.command()
@click.option(
    "--collection-id",
    required=True,
    help="Collection ID to delete the graph for.",
)
@click.option(
    "--cascade",
    is_flag=True,
    help="Whether to cascade the deletion.",
)
@pass_context
async def delete_graph_for_collection(ctx, collection_id, cascade):
    """
    Delete the graph for a given collection.

    NOTE: Setting the cascade flag to true will delete entities and relationships for documents that are shared across multiple collections. Do not set this flag unless you are absolutely sure that you want to delete the entities and relationships for all documents in the collection.
    """
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.delete_graph_for_collection(
            collection_id, cascade
        )

    click.echo(json.dumps(response, indent=2))
