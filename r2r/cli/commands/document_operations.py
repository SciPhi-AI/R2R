import click

from r2r.cli.command_group import cli
from r2r.cli.utils.timer import timer


@cli.command()
@click.option(
    "--filter",
    "-f",
    multiple=True,
    help="Filters for deletion in the format key:operator:value",
)
@click.pass_obj
def delete(obj, filter):
    """Delete documents based on filters."""
    filters = {}
    for f in filter:
        key, operator, value = f.split(":", 2)
        if key not in filters:
            filters[key] = {}
        filters[key][f"${operator}"] = value

    with timer():
        response = obj.delete(filters=filters)

    click.echo(response)


@cli.command()
@click.option("--document-ids", multiple=True, help="Document IDs to overview")
@click.pass_obj
def documents_overview(obj, document_ids):
    """Get an overview of documents."""
    document_ids = list(document_ids) if document_ids else None

    with timer():
        response = obj.documents_overview(document_ids)

    for document in response:
        click.echo(document)


@cli.command()
@click.argument("document-id")
@click.pass_obj
def document_chunks(obj, document_id):
    """Get chunks of a specific document."""
    print(document_id)
    with timer():
        response = obj.document_chunks(document_id)

    for chunk in response:
        click.echo(chunk)


@cli.command()
@click.option(
    "--file-paths", multiple=True, help="Paths to files for ingestion"
)
@click.option(
    "--document-ids", multiple=True, help="Document IDs for ingestion"
)
@click.option("--metadatas", multiple=True, help="Metadatas for ingestion")
@click.option(
    "--versions",
    multiple=True,
    help="Starting version for ingested files (e.g. `v1`)",
)
@click.pass_obj
def ingest_files(obj, file_paths, document_ids, metadatas, versions):
    """Ingest files into R2R."""
    with timer():
        file_paths = list(file_paths)
        document_ids = list(document_ids) if document_ids else None
        metadatas = list(metadatas) if metadatas else None
        versions = list(versions) if versions else None

        response = obj.ingest_files(
            file_paths, document_ids, metadatas, versions
        )
    click.echo(response)


@cli.command()
@click.option(
    "--no-media",
    is_flag=True,
    default=False,
    help="Exclude media files from ingestion",
)
@click.option("--option", type=int, default=0, help="Which file to ingest?")
@click.pass_obj
def ingest_sample_file(obj, no_media, option):
    """Ingest sample files into R2R."""
    with timer():
        response = obj.ingest_sample_file(no_media=no_media, option=option)

    click.echo(response)


@cli.command()
@click.option(
    "--no-media",
    default=True,
    help="Exclude media files from ingestion",
)
@click.pass_obj
def ingest_sample_files(obj, no_media):
    """Ingest all sample files into R2R."""
    with timer():
        response = obj.ingest_sample_files(no_media=no_media)

    click.echo(response)


@cli.command()
@click.argument("file-paths", nargs=-1)
@click.option(
    "--document-ids", multiple=True, help="Document IDs for ingestion"
)
@click.option("--metadatas", multiple=True, help="Metadatas for ingestion")
@click.pass_obj
def update_files(obj, file_paths, document_ids, metadatas):
    """Update existing files in R2R."""
    with timer():
        # Default to None if empty tuples are provided
        metadatas = list(metadatas) if metadatas else None

        response = obj.update_files(
            list(file_paths), list(document_ids), metadatas
        )

    click.echo(response)
