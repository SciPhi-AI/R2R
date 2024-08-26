from typing import Any, Dict

import click

from cli.command_group import cli
from cli.utils.param_types import JSON
from cli.utils.timer import timer

# TODO: Implement update_prompt


@cli.command()
@click.option("--filters", type=JSON, help="Filters for analytics as JSON")
@click.option("--analysis-types", type=JSON, help="Analysis types as JSON")
@click.pass_obj
def analytics(client, filters: Dict[str, Any], analysis_types: Dict[str, Any]):
    """Retrieve analytics data."""
    with timer():
        response = client.analytics(filters, analysis_types)

    click.echo(response)


@cli.command()
@click.pass_obj
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
@click.pass_obj
def users_overview(client, user_ids, offset, limit):
    """Get an overview of users."""
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
@click.pass_obj
def delete(client, filter):
    """Delete documents based on filters."""
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
@click.pass_obj
def documents_overview(client, document_ids, offset, limit):
    """Get an overview of documents."""
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
@click.pass_obj
def document_chunks(client, document_id, offset, limit):
    """Get chunks of a specific document."""
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
            click.echo(f"Fragment ID: {chunk.get('fragment_id', 'N/A')}")
            click.echo(f"Text: {chunk.get('text', '')[:100]}...")
            click.echo(f"Metadata: {chunk.get('metadata', {})}")
        else:
            click.echo(f"Unexpected chunk format: {chunk}")


@cli.command()
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
@click.pass_obj
def inspect_knowledge_graph(client, offset, limit):
    """Inspect the knowledge graph."""
    with timer():
        response = client.inspect_knowledge_graph(offset, limit)

    click.echo(response)
