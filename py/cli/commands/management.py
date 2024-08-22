from typing import Any, Dict

import click
from cli.command_group import cli
from cli.utils.param_types import JSON
from cli.utils.timer import timer

# TODO: Implement update_prompt


# TODO: Update
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
@click.pass_obj
def users_overview(client, user_ids):
    """Get an overview of users."""
    user_ids = list(user_ids) if user_ids else None

    with timer():
        response = client.users_overview(user_ids)

    if 'results' in response:
        click.echo("\nUser Overview:")
        click.echo(f"{'User ID':<40} {'Num Files':<10} {'Total Size (bytes)':<20} Document IDs")
        for user in response['results']:
            click.echo(f"{user['user_id']:<40} {user['num_files']:<10} {user['total_size_in_bytes']:<20} {', '.join(user['document_ids'][:3]) + ('...' if len(user['document_ids']) > 3 else '')}")
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
@click.pass_obj
def documents_overview(client, document_ids):
    """Get an overview of documents."""
    document_ids = list(document_ids) if document_ids else None

    with timer():
        response = client.documents_overview(document_ids)

    for document in response["results"]:
        click.echo(document)


@cli.command()
@click.option("--document-id", help="Document ID to retrieve chunks for")
@click.pass_obj
def document_chunks(client, document_id):
    """Get chunks of a specific document."""
    with timer():
        response = client.document_chunks(document_id)

    chunks = response.get("results", [])
    click.echo(f"\nNumber of chunks: {len(chunks)}")
    for index, chunk in enumerate(chunks, 1):
        click.echo(f"\nChunk {index}:")
        click.echo(f"Fragment ID: {chunk['fragment_id']}")
        click.echo(f"Text: {chunk['text'][:100]}...")
        click.echo(f"Metadata: {chunk['metadata']}")


@cli.command()
@click.option(
    "--limit",
    default=None,
    help="The maximum number of nodes to return. Defaults to 100.",
)
@click.pass_obj
def inspect_knowledge_graph(client, limit):
    """Inspect the knowledge graph."""
    with timer():
        response = client.inspect_knowledge_graph(limit)

    click.echo(response)


## TODO: Implement groups_overview


## TODO: Implement create_group


## TODO: Implement get_group


## TODO: Implement update_group


## TODO: Implement delete_group


## TODO: Implement list_groups


## TODO: Implement add_user_to_group


## TODO: Implement remove_user_from_group


## TODO: Implement get_users_in_group


## TODO: Implement get_groups_for_user


## TODO: Implement assign_document_to_group


## TODO: Implement remove_document_from_group


## TODO: Implement get_document_groups


## TODO: Implement get_documents_in_group
