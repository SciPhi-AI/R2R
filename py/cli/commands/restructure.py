import click

from cli.command_group import cli
from cli.utils.timer import timer


@cli.command()
@click.pass_obj
def enrich_graph(client):
    """
    Perform graph enrichment over the entire graph.
    """
    with timer():
        response = client.enrich_graph()

    click.echo(response)
