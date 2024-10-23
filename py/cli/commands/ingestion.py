import json
import os
import tempfile
import uuid
from urllib.parse import urlparse

import asyncclick as click
import requests
from asyncclick import pass_context

from cli.command_group import cli
from cli.utils.param_types import JSON
from cli.utils.timer import timer
from shared.abstractions.vector import (
    IndexMeasure,
    IndexMethod,
    VectorTableName,
)


async def ingest_files_from_urls(client, urls):
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
            # TODO: use the utils function generate_document_id
            document_ids.append(uuid.uuid5(uuid.NAMESPACE_DNS, url))

        response = await client.ingest_files(
            files_to_ingest, metadatas=metadatas, document_ids=document_ids
        )

        return response["results"]
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            os.unlink(temp_file.name)


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
    "--run-without-orchestration", is_flag=True, help="Run with orchestration"
)
@pass_context
async def ingest_files(
    ctx, file_paths, document_ids, metadatas, run_without_orchestration
):
    """Ingest files into R2R."""
    client = ctx.obj
    with timer():
        file_paths = list(file_paths)
        document_ids = list(document_ids) if document_ids else None
        run_with_orchestration = not run_without_orchestration
        response = await client.ingest_files(
            file_paths,
            metadatas,
            document_ids,
            run_with_orchestration=run_with_orchestration,
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
@click.option(
    "--run-without-orchestration", is_flag=True, help="Run with orchestration"
)
@pass_context
async def update_files(
    ctx, file_paths, document_ids, metadatas, run_without_orchestration
):
    """Update existing files in R2R."""
    client = ctx.obj
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
        run_with_orchestration = not run_without_orchestration
        response = await client.update_files(
            file_paths,
            document_ids,
            metadatas,
            run_with_orchestration=run_with_orchestration,
        )
    click.echo(json.dumps(response, indent=2))


@cli.command()
@click.option(
    "--v2", is_flag=True, help="use aristotle_v2.txt (a smaller file)"
)
@pass_context
async def ingest_sample_file(ctx, v2=False):
    """Ingest the first sample file into R2R."""
    sample_file_url = f"https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/aristotle{'_v2' if v2 else ''}.txt"
    client = ctx.obj

    with timer():
        response = await ingest_files_from_urls(client, [sample_file_url])
    click.echo(
        f"Sample file ingestion completed. Ingest files response:\n\n{response}"
    )


@cli.command()
@pass_context
async def ingest_sample_files(ctx):
    """Ingest multiple sample files into R2R."""
    client = ctx.obj
    urls = [
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_3.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_4.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_5.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/lyft_2021.pdf",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/uber_2021.pdf",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/aristotle.txt",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/got.txt",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_1.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_2.html",
    ]
    with timer():
        response = await ingest_files_from_urls(client, urls)

    click.echo(
        f"Sample files ingestion completed. Ingest files response:\n\n{response}"
    )


@cli.command()
@pass_context
async def ingest_sample_files_from_unstructured(ctx):
    """Ingest multiple sample files from URLs into R2R."""
    client = ctx.obj

    # Get the absolute path of the current script
    current_script_path = os.path.abspath(__file__)

    # Navigate to the root directory of the project
    root_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(current_script_path))
    )

    # Construct the absolute path to the data_unstructured folder
    folder = os.path.join(root_dir, "core", "examples", "data_unstructured")

    file_paths = [os.path.join(folder, file) for file in os.listdir(folder)]

    with timer():
        response = await client.ingest_files(file_paths)

    click.echo(
        f"Sample files ingestion completed. Ingest files response:\n\n{response}"
    )


@cli.command()
@click.option(
    "--table-name",
    type=click.Choice([t.value for t in VectorTableName]),
    default=VectorTableName.VECTORS.value,
    help="Table to create index on",
)
@click.option(
    "--index-method",
    type=click.Choice([m.value for m in IndexMethod]),
    default=IndexMethod.hnsw.value,
    help="Indexing method to use",
)
@click.option(
    "--index-measure",
    type=click.Choice([m.value for m in IndexMeasure]),
    default=IndexMeasure.cosine_distance.value,
    help="Distance measure to use",
)
@click.option(
    "--index-arguments",
    type=JSON,
    help="Additional index arguments as JSON",
)
@click.option(
    "--index-name",
    help="Custom name for the index",
)
@click.option(
    "--no-concurrent",
    is_flag=True,
    help="Disable concurrent index creation",
)
@pass_context
async def create_vector_index(
    ctx,
    table_name,
    index_method,
    index_measure,
    index_arguments,
    index_name,
    no_concurrent,
):
    """Create a vector index for similarity search."""
    client = ctx.obj
    with timer():
        response = await client.create_vector_index(
            table_name=table_name,
            index_method=index_method,
            index_measure=index_measure,
            index_arguments=index_arguments,
            index_name=index_name,
            concurrently=not no_concurrent,
        )
    click.echo(json.dumps(response, indent=2))


@cli.command()
@click.option(
    "--table-name",
    type=click.Choice([t.value for t in VectorTableName]),
    default=VectorTableName.VECTORS.value,
    help="Table to list indices from",
)
@pass_context
async def list_vector_indices(ctx, table_name):
    """List all vector indices for a table."""
    client = ctx.obj
    with timer():
        response = await client.list_vector_indices(table_name=table_name)
    click.echo(json.dumps(response, indent=2))


@cli.command()
@click.argument("index-name", required=True)
@click.option(
    "--table-name",
    type=click.Choice([t.value for t in VectorTableName]),
    default=VectorTableName.VECTORS.value,
    help="Table containing the index",
)
@click.option(
    "--no-concurrent",
    is_flag=True,
    help="Disable concurrent index deletion",
)
@pass_context
async def delete_vector_index(ctx, index_name, table_name, no_concurrent):
    """Delete a vector index."""
    client = ctx.obj
    with timer():
        response = await client.delete_vector_index(
            index_name=index_name,
            table_name=table_name,
            concurrently=not no_concurrent,
        )
    click.echo(json.dumps(response, indent=2))
