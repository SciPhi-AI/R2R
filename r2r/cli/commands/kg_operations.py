import click

from r2r.cli.command_group import cli
from r2r.cli.utils.timer import timer


@cli.command()
@click.pass_obj
def enrich_graph(obj):
    """Enrich the knowledge graph with specified documents."""
    # document_ids = list(document_ids) if document_ids else None

    with timer():
        response = obj.enrich_graph()

    click.echo(response)
