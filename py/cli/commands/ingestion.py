import json
import os
import tempfile
import uuid
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
@click.pass_obj
def ingest_files(client, file_paths, document_ids, metadatas):
    """Ingest files into R2R."""
    with timer():
        file_paths = list(file_paths)
        document_ids = list(document_ids) if document_ids else None

        response = client.ingest_files(file_paths, metadatas, document_ids)
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
    files_to_ingest = []
    metadatas = []
    document_ids = []
    temp_files = []

    try:
        for url in urls:
            filename = os.path.basename(urlparse(url).path)
            is_pdf = filename.lower().endswith(".pdf")

            temp_file = tempfile.NamedTemporaryFile(
                mode="wb" if is_pdf else "w+",
                delete=False,
                suffix=f"_{filename}",
            )
            temp_files.append(temp_file)

            response = requests.get(url)
            response.raise_for_status()
            if is_pdf:
                temp_file.write(response.content)
            else:
                temp_file.write(response.text)
            temp_file.close()

            files_to_ingest.append(temp_file.name)
            metadatas.append({"title": filename})
            document_ids.append(uuid.uuid5(uuid.NAMESPACE_DNS, url))

        response = client.ingest_files(
            files_to_ingest, metadatas=metadatas, document_ids=document_ids
        )

        return response["results"]
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            os.unlink(temp_file.name)


@cli.command()
@click.pass_obj
def ingest_sample_file(client):
    """Ingest the first sample file into R2R."""
    sample_file_url = "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/aristotle.txt"

    with timer():
        response = ingest_files_from_urls(client, [sample_file_url])
    click.echo(
        f"Sample file ingestion completed. Ingest files response:\n\n{response}"
    )


@cli.command()
@click.pass_obj
def ingest_sample_files(client):
    """Ingest multiple sample files into R2R."""
    urls = [
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/aristotle.txt",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/got.txt",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_1.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_2.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_3.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_4.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_5.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/lyft_2021.pdf",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/uber_2021.pdf",
    ]
    with timer():
        response = ingest_files_from_urls(client, urls)

    click.echo(
        f"Sample files ingestion completed. Ingest files response:\n\n{response}"
    )
