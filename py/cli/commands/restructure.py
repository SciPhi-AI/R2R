import json

import click

from cli.command_group import cli
from cli.utils.timer import timer


@cli.command()
@click.option(
    "--document-ids",
    required=False,
    default="",
    help="Document IDs to create graph for (comma-separated)",
)
@click.pass_obj
def create_graph(client, document_ids):
    """
    Create a new graph.
    """
    with timer():
        if document_ids == "":
            document_ids = []
        else:
            document_ids = document_ids.split(",")
        response = client.create_graph(document_ids)

    click.echo(json.dumps(response, indent=2))


@cli.command()
@click.pass_obj
def enrich_graph(client):
    """
    Perform graph enrichment over the entire graph.
    """
    with timer():
        response = client.enrich_graph()

    click.echo(response)
