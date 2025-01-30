import json

import asyncclick as click
from asyncclick import pass_context

from cli.utils.param_types import JSON
from cli.utils.timer import timer
from r2r import R2RAsyncClient, R2RException


@click.group()
def graphs():
    """Graphs commands."""
    pass

async def handle_response(ctx: click.Context, response, message: str):
    """Helper function to handle responses and print them."""
    click.echo(json.dumps(response, indent=2))

async def handle_error(e: Exception):
    """Helper function to handle errors and print them."""
    if isinstance(e, R2RException):
        click.echo(str(e), err=True)
    else:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@graphs.command()
@click.option("--collection-ids", multiple=True, help="Collection IDs to fetch")
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of graphs to return. Defaults to 100.")
@pass_context
async def list(ctx: click.Context, collection_ids, offset, limit):
    """List available graphs."""
    collection_ids = list(collection_ids) if collection_ids else None
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.list(
                collection_ids=collection_ids,
                offset=offset,
                limit=limit,
            )
        await handle_response(ctx, response, "Graphs listed successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@pass_context
async def retrieve(ctx: click.Context, collection_id):
    """Retrieve a specific graph by collection ID."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.retrieve(collection_id=collection_id)
        await handle_response(ctx, response, "Graph retrieved successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@pass_context
async def reset(ctx: click.Context, collection_id):
    """Reset a graph, removing all its data."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.reset(collection_id=collection_id)
        await handle_response(ctx, response, "Graph reset successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.option("--name", help="New name for the graph")
@click.option("--description", help="New description for the graph")
@pass_context
async def update(ctx: click.Context, collection_id, name, description):
    """Update graph information."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.update(
                collection_id=collection_id,
                name=name,
                description=description,
            )
        await handle_response(ctx, response, "Graph updated successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of entities to return. Defaults to 100.")
@pass_context
async def list_entities(ctx: click.Context, collection_id, offset, limit):
    """List entities in a graph."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.list_entities(
                collection_id=collection_id,
                offset=offset,
                limit=limit,
            )
        await handle_response(ctx, response, "Entities listed successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.argument("entity_id", required=True, type=str)
@pass_context
async def get_entity(ctx: click.Context, collection_id, entity_id):
    """Get entity information from a graph."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.get_entity(
                collection_id=collection_id,
                entity_id=entity_id,
            )
        await handle_response(ctx, response, "Entity retrieved successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.argument("entity_id", required=True, type=str)
@pass_context
async def remove_entity(ctx: click.Context, collection_id, entity_id):
    """Remove an entity from a graph."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.remove_entity(
                collection_id=collection_id,
                entity_id=entity_id,
            )
        await handle_response(ctx, response, "Entity removed successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of relationships to return. Defaults to 100.")
@pass_context
async def list_relationships(ctx: click.Context, collection_id, offset, limit):
    """List relationships in a graph."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.list_relationships(
                collection_id=collection_id,
                offset=offset,
                limit=limit,
            )
        await handle_response(ctx, response, "Relationships listed successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.argument("relationship_id", required=True, type=str)
@pass_context
async def get_relationship(ctx: click.Context, collection_id, relationship_id):
    """Get relationship information from a graph."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.get_relationship(
                collection_id=collection_id,
                relationship_id=relationship_id,
            )
        await handle_response(ctx, response, "Relationship retrieved successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.argument("relationship_id", required=True, type=str)
@pass_context
async def remove_relationship(ctx: click.Context, collection_id, relationship_id):
    """Remove a relationship from a graph."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.remove_relationship(
                collection_id=collection_id,
                relationship_id=relationship_id,
            )
        await handle_response(ctx, response, "Relationship removed successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.option("--settings", required=True, type=JSON, help="Build settings as JSON")
@click.option("--run-without-orchestration", is_flag=True, help="Run without orchestration")
@pass_context
async def build(ctx: click.Context, collection_id, settings, run_without_orchestration):
    """Build a graph with specified settings."""
    run_with_orchestration = not run_without_orchestration
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.build(
                collection_id=collection_id,
                settings=settings,
                run_with_orchestration=run_with_orchestration,
            )
        await handle_response(ctx, response, "Graph built successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of communities to return. Defaults to 100.")
@pass_context
async def list_communities(ctx: click.Context, collection_id, offset, limit):
    """List communities in a graph."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.list_communities(
                collection_id=collection_id,
                offset=offset,
                limit=limit,
            )
        await handle_response(ctx, response, "Communities listed successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.argument("community_id", required=True, type=str)
@pass_context
async def get_community(ctx: click.Context, collection_id, community_id):
    """Get community information from a graph."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.get_community(
                collection_id=collection_id,
                community_id=community_id,
            )
        await handle_response(ctx, response, "Community retrieved successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.argument("community_id", required=True, type=str)
@click.option("--name", help="New name for the community")
@click.option("--summary", help="New summary for the community")
@click.option("--findings", type=JSON, help="New findings for the community as JSON array")
@click.option("--rating", type=int, help="New rating for the community")
@click.option("--rating-explanation", help="New rating explanation for the community")
@click.option("--level", type=int, help="New level for the community")
@click.option("--attributes", type=JSON, help="New attributes for the community as JSON")
@pass_context
async def update_community(ctx: click.Context, collection_id, community_id, name, summary, findings, rating, rating_explanation, level, attributes):
    """Update community information."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.update_community(
                collection_id=collection_id,
                community_id=community_id,
                name=name,
                summary=summary,
                findings=findings,
                rating=rating,
                rating_explanation=rating_explanation,
                level=level,
                attributes=attributes,
            )
        await handle_response(ctx, response, "Community updated successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.argument("community_id", required=True, type=str)
@pass_context
async def delete_community(ctx: click.Context, collection_id, community_id):
    """Delete a community from a graph."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.delete_community(
                collection_id=collection_id,
                community_id=community_id,
            )
        await handle_response(ctx, response, "Community deleted successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@pass_context
async def pull(ctx: click.Context, collection_id):
    """Pull documents into a graph."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.pull(collection_id=collection_id)
        await handle_response(ctx, response, "Documents pulled successfully.")
    except Exception as e:
        await handle_error(e)

@graphs.command()
@click.argument("collection_id", required=True, type=str)
@click.argument("document_id", required=True, type=str)
@pass_context
async def remove_document(ctx: click.Context, collection_id, document_id):
    """Remove a document from a graph."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.graphs.remove_document(
                collection_id=collection_id,
                document_id=document_id,
            )
        await handle_response(ctx, response, "Document removed successfully.")
    except Exception as e:
        await handle_error(e)
