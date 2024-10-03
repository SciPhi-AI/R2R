from typing import Any, Dict

import asyncclick as click
from asyncclick import pass_context

from cli.command_group import cli
from cli.utils.param_types import JSON
from cli.utils.timer import timer


@cli.command()
@click.option("--filters", type=JSON, help="Filters for analytics as JSON")
@click.option("--analysis-types", type=JSON, help="Analysis types as JSON")
@pass_context
def analytics(ctx, filters: Dict[str, Any], analysis_types: Dict[str, Any]):
    client = ctx.obj
    """Retrieve analytics data."""
    with timer():
        response = client.analytics(filters, analysis_types)

    click.echo(response)


@cli.command()
@pass_context
def app_settings(client):
    """Retrieve application settings."""
    with timer():
        response = client.app_settings()

    click.echo(response)


# TODO: Implement score_completion


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
def users_overview(ctx, user_ids, offset, limit):
    """Get an overview of users."""
    client = ctx.obj
    user_ids = list(user_ids) if user_ids else None

    with timer():
        response = client.users_overview(user_ids, offset, limit)

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
def delete(ctx, filter):
    """Delete documents based on filters."""
    client = ctx.obj
    filters = {}
    for f in filter:
        key, operator, value = f.split(":", 2)
        if key not in filters:
            filters[key] = {}
        filters[key][f"${operator}"] = value

    with timer():
        response = client.delete(filters=filters)

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
def documents_overview(ctx, document_ids, offset, limit):
    """Get an overview of documents."""
    client = ctx.obj
    document_ids = list(document_ids) if document_ids else None

    with timer():
        response = client.documents_overview(document_ids, offset, limit)

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
@pass_context
def document_chunks(ctx, document_id, offset, limit):
    """Get chunks of a specific document."""
    client = ctx.obj
    if not document_id:
        click.echo("Error: Document ID is required.")
        return

    with timer():
        chunks_data = client.document_chunks(document_id, offset, limit)

    chunks = chunks_data["results"]
    if not chunks:
        click.echo("No chunks found for the given document ID.")
        return

    click.echo(f"\nNumber of chunks: {len(chunks)}")

    for index, chunk in enumerate(chunks, 1):
        click.echo(f"\nChunk {index}:")
        if isinstance(chunk, dict):
            click.echo(f"Extraction ID: {chunk.get('id', 'N/A')}")
            click.echo(f"Text: {chunk.get('text', '')[:100]}...")
            click.echo(f"Metadata: {chunk.get('metadata', {})}")
        else:
            click.echo(f"Unexpected chunk format: {chunk}")
