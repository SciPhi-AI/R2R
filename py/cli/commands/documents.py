import json
import os
import tempfile
import uuid
from urllib.parse import urlparse

import asyncclick as click
import requests
from asyncclick import pass_context

from cli.utils.param_types import JSON
from cli.utils.timer import timer
from r2r import R2RAsyncClient


@click.group()
def documents():
    """Documents commands."""
    pass


@documents.command()
@click.argument(
    "file_paths", nargs=-1, required=True, type=click.Path(exists=True)
)
@click.option("--ids", multiple=True, help="Document IDs for ingestion")
@click.option(
    "--metadatas", type=JSON, help="Metadatas for ingestion as a JSON string"
)
@click.option(
    "--run-without-orchestration", is_flag=True, help="Run with orchestration"
)
@pass_context
async def create(ctx, file_paths, ids, metadatas, run_without_orchestration):
    """Ingest files into R2R."""
    client: R2RAsyncClient = ctx.obj
    run_with_orchestration = not run_without_orchestration
    responses = []

    for idx, file_path in enumerate(file_paths):
        with timer():
            current_id = [ids[idx]] if ids and idx < len(ids) else None
            current_metadata = (
                metadatas[idx] if metadatas and idx < len(metadatas) else None
            )

            click.echo(
                f"Processing file {idx + 1}/{len(file_paths)}: {file_path}"
            )
            response = await client.documents.create(
                file_path=file_path,
                metadata=current_metadata,
                id=current_id,
                run_with_orchestration=run_with_orchestration,
            )
            responses.append(response)
            click.echo(json.dumps(response, indent=2))
            click.echo("-" * 40)

    click.echo(f"\nProcessed {len(responses)} files successfully.")


@documents.command()
@click.argument("file_path", required=True, type=click.Path(exists=True))
@click.option("--id", required=True, help="Existing document ID to update")
@click.option(
    "--metadata", type=JSON, help="Metadatas for ingestion as a JSON string"
)
@click.option(
    "--run-without-orchestration", is_flag=True, help="Run with orchestration"
)
@pass_context
async def update(ctx, file_path, id, metadata, run_without_orchestration):
    """Update an existing file in R2R."""
    client: R2RAsyncClient = ctx.obj
    run_with_orchestration = not run_without_orchestration
    responses = []

    with timer():
        click.echo(f"Updating file {id}: {file_path}")
        response = await client.documents.update(
            file_path=file_path,
            metadata=metadata,
            id=id,
            run_with_orchestration=run_with_orchestration,
        )
        responses.append(response)
        click.echo(json.dumps(response, indent=2))
        click.echo("-" * 40)

    click.echo(f"Updated file {id} file successfully.")


@documents.command()
@click.argument("id", required=True, type=str)
@pass_context
async def retrieve(ctx, id):
    """Retrieve a document by ID."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.documents.retrieve(id=id)

    click.echo(json.dumps(response, indent=2))


@documents.command()
@click.argument("id", required=True, type=str)
@pass_context
async def delete(ctx, id):
    """Delete a document by ID."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.documents.delete(id=id)

    click.echo(json.dumps(response, indent=2))


@documents.command()
@click.argument("id", required=True, type=str)
@click.option(
    "--offset",
    default=0,
    help="The offset to start from. Defaults to 0.",
)
@click.option(
    "--limit",
    default=100,
    help="The maximum number of nodes to return. Defaults to 100.",
)
@pass_context
async def list_chunks(ctx, id, offset, limit):
    """List collections for a specific document."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.documents.list_chunks(
            id=id,
            offset=offset,
            limit=limit,
        )

    click.echo(json.dumps(response, indent=2))


@documents.command()
@click.argument("id", required=True, type=str)
@click.option(
    "--offset",
    default=0,
    help="The offset to start from. Defaults to 0.",
)
@click.option(
    "--limit",
    default=100,
    help="The maximum number of nodes to return. Defaults to 100.",
)
@pass_context
async def list_collections(ctx, id, offset, limit):
    """List collections for a specific document."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.documents.list_collections(
            id=id,
            offset=offset,
            limit=limit,
        )

    click.echo(json.dumps(response, indent=2))


# TODO
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
            document_ids.append(str(uuid.uuid5(uuid.NAMESPACE_DNS, url)))

        for it, file in enumerate(files_to_ingest):
            click.echo(f"Ingesting file: {file}")
            response = await client.documents.create(
                file, metadata=metadatas[it], id=document_ids[it]
            )

        return response["results"]
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            os.unlink(temp_file.name)


# Missing CLI Commands
@documents.command()
@click.argument("id", required=True, type=str)
@click.option("--run-type", help="Extraction run type (estimate or run)")
@click.option("--settings", type=JSON, help="Extraction settings as JSON")
@click.option(
    "--run-without-orchestration",
    is_flag=True,
    help="Run without orchestration",
)
@pass_context
async def extract(ctx, id, run_type, settings, run_without_orchestration):
    """Extract entities and relationships from a document."""
    client: R2RAsyncClient = ctx.obj
    run_with_orchestration = not run_without_orchestration

    with timer():
        response = await client.documents.extract(
            id=id,
            run_type=run_type,
            settings=settings,
            run_with_orchestration=run_with_orchestration,
        )

    click.echo(json.dumps(response, indent=2))


@documents.command()
@click.argument("id", required=True, type=str)
@click.option(
    "--offset",
    default=0,
    help="The offset to start from. Defaults to 0.",
)
@click.option(
    "--limit",
    default=100,
    help="The maximum number of items to return. Defaults to 100.",
)
@click.option(
    "--include-embeddings",
    is_flag=True,
    help="Include embeddings in response",
)
@pass_context
async def list_entities(ctx, id, offset, limit, include_embeddings):
    """List entities extracted from a document."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.documents.list_entities(
            id=id,
            offset=offset,
            limit=limit,
            include_embeddings=include_embeddings,
        )

    click.echo(json.dumps(response, indent=2))


@documents.command()
@click.argument("id", required=True, type=str)
@click.option(
    "--offset",
    default=0,
    help="The offset to start from. Defaults to 0.",
)
@click.option(
    "--limit",
    default=100,
    help="The maximum number of items to return. Defaults to 100.",
)
@click.option(
    "--entity-names",
    multiple=True,
    help="Filter by entity names",
)
@click.option(
    "--relationship-types",
    multiple=True,
    help="Filter by relationship types",
)
@pass_context
async def list_relationships(
    ctx, id, offset, limit, entity_names, relationship_types
):
    """List relationships extracted from a document."""
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await client.documents.list_relationships(
            id=id,
            offset=offset,
            limit=limit,
            entity_names=list(entity_names) if entity_names else None,
            relationship_types=(
                list(relationship_types) if relationship_types else None
            ),
        )

    click.echo(json.dumps(response, indent=2))


@documents.command()
@click.option(
    "--v2", is_flag=True, help="use aristotle_v2.txt (a smaller file)"
)
@click.option(
    "--v3", is_flag=True, help="use aristotle_v3.txt (a larger file)"
)
@pass_context
async def create_sample(ctx, v2=True, v3=False):
    """Ingest the first sample file into R2R."""
    sample_file_url = f"https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/aristotle.txt"
    client: R2RAsyncClient = ctx.obj

    with timer():
        response = await ingest_files_from_urls(client, [sample_file_url])
    click.echo(
        f"Sample file ingestion completed. Ingest files response:\n\n{response}"
    )


@documents.command()
@pass_context
async def create_samples(ctx):
    """Ingest multiple sample files into R2R."""
    client: R2RAsyncClient = ctx.obj
    urls = [
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_3.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_4.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_5.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/lyft_2021.pdf",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/uber_2021.pdf",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/got.txt",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_1.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/pg_essay_2.html",
        "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/aristotle.txt",
    ]
    with timer():
        response = await ingest_files_from_urls(client, urls)

    click.echo(
        f"Sample files ingestion completed. Ingest files response:\n\n{response}"
    )


@documents.command()
@click.option("--ids", multiple=True, help="Document IDs to fetch")
@click.option(
    "--offset",
    default=0,
    help="The offset to start from. Defaults to 0.",
)
@click.option(
    "--limit",
    default=100,
    help="The maximum number of nodes to return. Defaults to 100.",
)
@pass_context
async def list(ctx, ids, offset, limit):
    """Get an overview of documents."""
    client: R2RAsyncClient = ctx.obj
    ids = list(ids) if ids else None

    with timer():
        response = await client.documents.list(
            ids=ids,
            offset=offset,
            limit=limit,
        )

    for document in response["results"]:
        click.echo(document)
