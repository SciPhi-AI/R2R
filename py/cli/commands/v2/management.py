from typing import Any

import asyncclick as click
from asyncclick import pass_context

from r2r import R2RAsyncClient
from cli.command_group import cli, deprecated_command
from cli.utils.param_types import JSON
from cli.utils.timer import timer


# TODO
@cli.command()
@click.option("--filters", type=JSON, help="Filters for analytics as JSON")
@click.option("--analysis-types", type=JSON, help="Analysis types as JSON")
@pass_context
async def analytics(
    ctx, filters: dict[str, Any], analysis_types: dict[str, Any]
):
    client: R2RAsyncClient = ctx.obj
    """Retrieve analytics data."""
    with timer():
        response = await client.analytics(filters, analysis_types)

    click.echo(response)


# TODO
@cli.command()
@pass_context
async def app_settings(ctx):
    """Retrieve application settings."""
    client: R2RAsyncClient = ctx.obj
    with timer():
        response = await client.app_settings()

    click.echo(response)


@cli.command()
@click.option("--user-ids", multiple=True, help="User IDs to overview")
@click.option(
    "--offset",
    default=None,
    help="The offset to start from. Defaults to 0.",
)
@click.option(
    "--limit",
    default=None,
    help="The maximum number of nodes to return. Defaults to 100.",
)
@pass_context
@deprecated_command("r2r users list")
async def users_overview(ctx, user_ids, offset, limit):
    """Get an overview of users."""
    client: R2RAsyncClient = ctx.obj
    user_ids = list(user_ids) if user_ids else None

    with timer():
        response = await client.users_overview(user_ids, offset, limit)

    if "results" in response:
        click.echo("\nUser Overview:")
        click.echo(
            f"{'User ID':<40} {'Num Files':<10} {'Total Size (bytes)':<20} Document IDs"
        )
        for user in response["results"]:
            click.echo(
                f"{user['user_id']:<40} {user['num_files']:<10} {user['total_size_in_bytes']:<20} {', '.join(user['document_ids'][:3]) + ('...' if len(user['document_ids']) > 3 else '')}"
            )
    else:
        click.echo("No users found.")


@cli.command()
@click.option(
    "--filter",
    "-f",
    multiple=True,
    help="Filters for deletion in the format key:operator:value",
)
@pass_context
@deprecated_command("r2r delete <document id>")
async def delete(ctx, filter):
    """Delete documents based on filters."""
    client: R2RAsyncClient = ctx.obj
    filters = {}
    for f in filter:
        key, operator, value = f.split(":", 2)
        if key not in filters:
            filters[key] = {}
        filters[key][f"${operator}"] = value

    with timer():
        response = await client.delete(filters=filters)

    click.echo(response)


@cli.command()
@click.option("--document-ids", multiple=True, help="Document IDs to overview")
@click.option(
    "--offset",
    default=None,
    help="The offset to start from. Defaults to 0.",
)
@click.option(
    "--limit",
    default=None,
    help="The maximum number of nodes to return. Defaults to 100.",
)
@pass_context
@deprecated_command("r2r documents list")
async def documents_overview(ctx, document_ids, offset, limit):
    """Get an overview of documents."""
    client: R2RAsyncClient = ctx.obj
    document_ids = list(document_ids) if document_ids else None

    with timer():
        response = await client.documents_overview(document_ids, offset, limit)

    for document in response["results"]:
        click.echo(document)


@cli.command()
@click.option("--document-id", help="Document ID to retrieve chunks for")
@click.option(
    "--offset",
    default=None,
    help="The offset to start from. Defaults to 0.",
)
@click.option(
    "--limit",
    default=None,
    help="The maximum number of nodes to return. Defaults to 100.",
)
@click.option(
    "--include-vectors",
    is_flag=True,
    default=False,
    help="Should the vector be included in the response chunks",
)
@pass_context
@deprecated_command("r2r documents list-chunks <document id>")
async def list_document_chunks(
    ctx, document_id, offset, limit, include_vectors
):
    """Get chunks of a specific document."""
    client: R2RAsyncClient = ctx.obj
    if not document_id:
        click.echo("Error: Document ID is required.")
        return

    with timer():
        chunks_data = await client.list_document_chunks(
            document_id, offset, limit, include_vectors
        )

    chunks = chunks_data["results"]
    if not chunks:
        click.echo("No chunks found for the given document ID.")
        return

    click.echo(f"\nNumber of chunks: {len(chunks)}")

    for index, chunk in enumerate(chunks, 1):
        click.echo(f"\nChunk {index}:")
        if isinstance(chunk, dict):
            click.echo(f"Extraction ID: {chunk.get('extraction_id', 'N/A')}")
            click.echo(f"Text: {chunk.get('text', '')[:100]}...")
            click.echo(f"Metadata: {chunk.get('metadata', {})}")
            if include_vectors:
                click.echo(f"Vector: {chunk.get('vector', 'N/A')}")
        else:
            click.echo(f"Unexpected chunk format: {chunk}")


@cli.command()
@click.option("--document-id", help="Document ID to retrieve chunks for")
@click.option(
    "--offset",
    default=None,
    help="The offset to start from. Defaults to 0.",
)
@click.option(
    "--limit",
    default=None,
    help="The maximum number of nodes to return. Defaults to 100.",
)
@click.option(
    "--include-vectors",
    is_flag=True,
    default=False,
    help="Should the vector be included in the response chunks",
)
@pass_context
@deprecated_command("document_chunks")
async def document_chunks(ctx, document_id, offset, limit, include_vectors):
    """Get chunks of a specific document."""
    client: R2RAsyncClient = ctx.obj
    if not document_id:
        click.echo("Error: Document ID is required.")
        return

    with timer():
        chunks_data = await client.list_document_chunks(
            document_id, offset, limit, include_vectors
        )

    chunks = chunks_data["results"]
    if not chunks:
        click.echo("No chunks found for the given document ID.")
        return

    click.echo(f"\nNumber of chunks: {len(chunks)}")

    for index, chunk in enumerate(chunks, 1):
        click.echo(f"\nChunk {index}:")
        if isinstance(chunk, dict):
            click.echo(f"Extraction ID: {chunk.get('extraction_id', 'N/A')}")
            click.echo(f"Text: {chunk.get('text', '')[:100]}...")
            click.echo(f"Metadata: {chunk.get('metadata', {})}")
            if include_vectors:
                click.echo(f"Vector: {chunk.get('vector', 'N/A')}")
        else:
            click.echo(f"Unexpected chunk format: {chunk}")