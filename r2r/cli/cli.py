import os

import click

from r2r import R2R, R2RClient, R2RConfig


@click.group()
@click.option(
    "--config-path", default=None, help="Path to the configuration file"
)
@click.option(
    "--client-server-mode", default=True, help="Run in client-server mode"
)
@click.option(
    "--base-url",
    default="http://localhost:8000",
    help="Base URL for client-server mode",
)
@click.pass_context
def cli(ctx, config_path, client_server_mode, base_url):
    """R2R CLI for quick start and basic operations."""
    if config_path:
        config = R2RConfig.from_json(config_path)
    else:
        config = R2RConfig.from_json()
    if client_server_mode and ctx.invoked_subcommand != "serve":
        ctx.obj = R2RClient(base_url)
    else:
        ctx.obj = R2R(config)


@cli.command()
@click.option("--port", default=8000, help="Port to run the server on")
@click.pass_obj
def serve(obj, port):
    """Start the R2R server."""
    obj.serve(port=port)


@cli.command()
@click.argument("files", nargs=-1)
@click.pass_obj
def ingest(obj, files):
    """Ingest files into R2R."""
    if not files:
        files = [
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "examples",
                "data",
                "aristotle.txt",
            )
        ]

    if isinstance(obj, R2RClient):
        result = obj.ingest_files(files)
    else:
        documents = [obj.create_document(file) for file in files]
        result = obj.ingest_documents(documents)

    click.echo(result)


@cli.command()
@click.option(
    "--query", prompt="Enter your search query", help="The search query"
)
@click.pass_obj
def search(obj, query):
    """Perform a search query."""
    result = obj.search(query)
    click.echo(result)


@cli.command()
@click.option("--query", prompt="Enter your RAG query", help="The RAG query")
@click.option("--model", default="gpt-4o", help="Model to use for RAG")
@click.option("--stream", is_flag=True, help="Stream the RAG response")
@click.pass_obj
def rag(obj, query, model, stream):
    """Perform a RAG query."""
    result = obj.rag(query, model=model, stream=stream)
    if stream:
        for chunk in result:
            click.echo(chunk, nl=False)
    else:
        click.echo(result)


def main():
    cli()


if __name__ == "__main__":
    main()
