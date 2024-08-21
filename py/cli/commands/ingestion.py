import json
import os
import tempfile
from urllib.parse import urlparse

import click
import requests
from cli.command_group import cli
from cli.utils.param_types import JSON
from cli.utils.timer import timer


@cli.command()
@click.argument(
    "file_paths", nargs=-1, required=True, type=click.Path(exists=True)
)
@click.option(
    "--document-ids", multiple=True, help="Document IDs for ingestion"
)
@click.option(
    "--metadatas", type=JSON, help="Metadatas for ingestion as a JSON string"
)
@click.option(
    "--versions",
    multiple=True,
    help="Starting version for ingested files (e.g. `v1`)",
)
@click.pass_obj
def ingest_files(client, file_paths, document_ids, metadatas, versions):
    """Ingest files into R2R."""
    with timer():
        file_paths = list(file_paths)
        document_ids = list(document_ids) if document_ids else None
        versions = list(versions) if versions else None

        response = client.ingest_files(
            file_paths, metadatas, document_ids, versions
        )
    click.echo(json.dumps(response, indent=2))


@cli.command()
@click.argument(
    "file-paths", nargs=-1, required=True, type=click.Path(exists=True)
)
@click.option(
    "--document-ids",
    required=True,
    help="Document IDs to update (comma-separated)",
)
@click.option(
    "--metadatas", type=JSON, help="Metadatas for updating as a JSON string"
)
@click.pass_obj
def update_files(client, file_paths, document_ids, metadatas):
    """Update existing files in R2R."""
    with timer():
        file_paths = list(file_paths)

        document_ids = document_ids.split(",")

        if metadatas:
            if isinstance(metadatas, str):
                metadatas = json.loads(metadatas)
            if isinstance(metadatas, dict):
                metadatas = [metadatas]
            elif not isinstance(metadatas, list):
                raise click.BadParameter(
                    "Metadatas must be a JSON string representing a list of dictionaries or a single dictionary"
                )

        response = client.update_files(file_paths, document_ids, metadatas)
    click.echo(json.dumps(response, indent=2))


def ingest_files_from_urls(client, urls):
    """Download and ingest files from given URLs."""
    ingested_files = []
    for url in urls:
        filename = os.path.basename(urlparse(url).path)

        with tempfile.NamedTemporaryFile(
            mode="w+", delete=False, suffix=f"_{filename}"
        ) as temp_file:
            response = requests.get(url)
            response.raise_for_status()
            temp_file.write(response.text)
            temp_file_path = temp_file.name

        try:
            response = client.ingest_files([temp_file_path])
            click.echo(
                f"File '{filename}' ingested successfully. Response: {response}"
            )
            ingested_files.append(filename)
        finally:
            os.unlink(temp_file_path)

    return ingested_files


@cli.command()
@click.pass_obj
def ingest_sample_file(client):
    """Ingest the first sample file into R2R."""
    sample_file_url = "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/r2r/examples/data/aristotle.txt"

    with timer():
        ingested_files = ingest_files_from_urls(client, [sample_file_url])

    click.echo(
        f"Sample file ingestion completed. Ingested files: {', '.join(ingested_files)}"
    )


@cli.command()
@click.pass_obj
def ingest_sample_files(client):
    """Ingest multiple sample files into R2R."""
    urls = [
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/r2r/examples/data/aristotle.txt",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/r2r/examples/data/got.txt",
    ]
    with timer():
        ingested_files = ingest_files_from_urls(client, urls)

    click.echo(
        f"Sample files ingestion completed. Ingested files: {', '.join(ingested_files)}"
    )
