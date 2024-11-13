import json

import asyncclick as click
from asyncclick import pass_context

from r2r import R2RAsyncClient

from cli.utils.param_types import JSON
from cli.utils.timer import timer


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
@click.option("--id", help="Existing document ID to update")
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
