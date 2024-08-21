import click
from core.cli.command_group import cli
from core.cli.utils.timer import timer



@cli.command()
@click.option("--model", type=str, help="LLM Model to use for enrichment")
@click.pass_obj
def enrich_graph(obj, model):
    """Enrich the knowledge graph with specified documents."""
    
    with timer():
        response = obj.enrich_graph(model)

    click.echo(response)
