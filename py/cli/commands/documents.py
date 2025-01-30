import json
import os
import tempfile
import uuid
from builtins import list as _list
from typing import Any, Optional, Sequence
from urllib.parse import urlparse
from uuid import UUID

import asyncclick as click
from asyncclick import pass_context
from rich.box import ROUNDED
from rich.console import Console
from rich.table import Table

from cli.utils.param_types import JSON
from cli.utils.timer import timer
from r2r import R2RAsyncClient, R2RException


@click.group()
def documents():
    """Documents commands."""
    pass


@documents.command()
@click.argument("file_paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--ids", multiple=True, help="Document IDs for ingestion")
@click.option("--metadatas", type=JSON, help="Metadatas for ingestion as a JSON string")
@click.option("--run-without-orchestration", is_flag=True, help="Run with orchestration")
@pass_context
async def create(
    ctx: click.Context,
    file_paths: tuple[str, ...],
    ids: Optional[tuple[str, ...]] = None,
    metadatas: Optional[Sequence[dict[str, Any]]] = None,
    run_without_orchestration: bool = False,
):
    """Ingest files into R2R."""
    client: R2RAsyncClient = ctx.obj
    run_with_orchestration = not run_without_orchestration
    responses: _list[dict[str, Any]] = []

    for idx, file_path in enumerate(file_paths):
        current_id = ids[idx] if ids and idx < len(ids) else None
        current_metadata = metadatas[idx] if metadatas and idx < len(metadatas) else None

        click.echo(f"Processing file {idx + 1}/{len(file_paths)}: {file_path}")
        try:
            with timer():
                response = await client.documents.create(
                    file_path=file_path,
                    metadata=current_metadata,
                    id=current_id,
                    run_with_orchestration=run_with_orchestration,
                )
                responses.append(response)
                click.echo(json.dumps(response, indent=2))
                click.echo("-" * 40)
        except R2RException as e:
            click.echo(f"[bold red]Error:[/bold red] {str(e)}", err=True)
        except Exception as e:
            click.echo(f"[bold red]Unexpected error:[/bold red] {str(e)}", err=True)

    click.echo(f"\nProcessed {len(responses)} files successfully.")


@documents.command()
@click.option("--ids", multiple=True, help="Document IDs to fetch")
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of nodes to return. Defaults to 100.")
@pass_context
async def list(
    ctx: click.Context,
    ids: Optional[tuple[str, ...]] = None,
    offset: int = 0,
    limit: int = 100,
) -> None:
    """Get an overview of documents."""
    ids = list(ids) if ids else None
    client: R2RAsyncClient = ctx.obj
    console = Console()

    try:
        with timer():
            response = await client.documents.list(ids=ids, offset=offset, limit=limit)

        table = create_document_table(response["results"])
        console.print("\n")
        console.print(table)
        console.print(f"\n[dim]Showing {len(response['results'])} documents (offset: {offset}, limit: {limit})[/dim]")
    except R2RException as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {str(e)}")


def create_document_table(documents):
    """Create a rich table for displaying documents."""
    table = Table(
        title="[bold blue]Documents[/bold blue]",
        show_header=True,
        header_style="bold white on blue",
        border_style="blue",
        box=ROUNDED,
        pad_edge=False,
        collapse_padding=True,
        show_lines=True,
    )

    # Add columns based on your document structure
    table.add_column("ID", style="bright_yellow", no_wrap=True)
    table.add_column("Type", style="bright_magenta")
    table.add_column("Title", style="bright_green")
    table.add_column("Ingestion Status", style="bright_cyan")
    table.add_column("Extraction Status", style="bright_cyan")
    table.add_column("Summary", style="bright_white")
    table.add_column("Created At", style="bright_white")

    for document in documents:  # type: ignore
        table.add_row(
            document.get("id", ""),
            document.get("document_type", ""),
            document.get("title", ""),
            document.get("ingestion_status", ""),
            document.get("extraction_status", ""),
            document.get("summary", ""),
            document.get("created_at", "")[:19],
        )
    return table


@documents.command()
@click.argument("id", required=True, type=str)
@pass_context
async def retrieve(ctx: click.Context, id: UUID):
    """Retrieve a document by ID."""
    client: R2RAsyncClient = ctx.obj
    console = Console()

    try:
        with timer():
            response = await client.documents.retrieve(id=id)
        document = response["results"]  # type: ignore

        metadata_table = create_metadata_table(document)
        console.print("\n")
        console.print(metadata_table)
        console.print("\n")

    except R2RException as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {str(e)}")


def create_metadata_table(document):
    """Create a rich table for displaying document metadata."""
    metadata_table = Table(
        show_header=True,
        header_style="bold white on blue",
        border_style="blue",
        box=ROUNDED,
        title="[bold blue]Document Details[/bold blue]",
        show_lines=True,
    )

    metadata_table.add_column("Field", style="bright_yellow")
    metadata_table.add_column("Value", style="bright_white")

    core_fields = [
        ("ID", document.get("id", "")),
        ("Type", document.get("document_type", "")),
        ("Title", document.get("title", "")),
        ("Created At", document.get("created_at", "")[:19]),
        ("Updated At", document.get("updated_at", "")[:19]),
        ("Ingestion Status", document.get("ingestion_status", "")),
        ("Extraction Status", document.get("extraction_status", "")),
        ("Size", f"{document.get('size_in_bytes', 0):,} bytes"),
    ]

    for field, value in core_fields:
        metadata_table.add_row(field, str(value))

    if "metadata" in document:
        metadata_table.add_row("[bold]Metadata[/bold]", "", style="bright_blue")
        for key, value in document["metadata"].items():
            metadata_table.add_row(f"  {key}", str(value))

    if "summary" in document:
        metadata_table.add_row("[bold]Summary[/bold]", document["summary"])

    return metadata_table


@documents.command()
@click.argument("id", required=True, type=str)
@pass_context
async def delete(ctx: click.Context, id: str):
    """Delete a document by ID."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.documents.delete(id=id)
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"[bold red]Error:[/bold red] {str(e)}", err=True)
    except Exception as e:
        click.echo(f"[bold red]Unexpected error:[/bold red] {str(e)}", err=True)


@documents.command()
@click.argument("id", required=True, type=str)
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of nodes to return. Defaults to 100.")
@pass_context
async def list_chunks(ctx: click.Context, id: str, offset: int, limit: int):
    """List chunks for a specific document."""
    client: R2RAsyncClient = ctx.obj
    console = Console()

    try:
        with timer():
            response = await client.documents.list_chunks(id=id, offset=offset, limit=limit)

        table = create_chunk_table(response["results"])
        console.print("\n")
        console.print(table)
        console.print(f"\n[dim]Showing {len(response['results'])} chunks (offset: {offset}, limit: {limit})[/dim]")
    except R2RException as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {str(e)}")


def create_chunk_table(chunks):
    """Create a rich table for displaying document chunks."""
    table = Table(
        title="[bold blue]Document Chunks[/bold blue]",
        show_header=True,
        header_style="bold white on blue",
        border_style="blue",
        box=ROUNDED,
        pad_edge=False,
        collapse_padding=True,
        show_lines=True,
    )

    table.add_column("ID", style="bright_yellow", no_wrap=True)
    table.add_column("Text", style="bright_white")

    for chunk in chunks:  # type: ignore
        text_preview = (chunk.get("text", "")[:200] + "...") if len(chunk.get("text", "")) > 200 else chunk.get("text", "")
        table.add_row(chunk.get("id", ""), text_preview)

    return table


@documents.command()
@click.argument("id", required=True, type=str)
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of nodes to return. Defaults to 100.")
@pass_context
async def list_collections(ctx: click.Context, id: str, offset: int, limit: int):
    """List collections for a specific document."""
    client: R2RAsyncClient = ctx.obj
    console = Console()

    try:
        with timer():
            response = await client.documents.list_collections(id=id, offset=offset, limit=limit)

        table = create_collection_table(response["results"])
        console.print("\n")
        console.print(table)
        console.print(f"\n[dim]Showing {len(response['results'])} collections (offset: {offset}, limit: {limit})[/dim]")
    except R2RException as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {str(e)}")


def create_collection_table(collections):
    """Create a rich table for displaying document collections."""
    table = Table(
        title="[bold blue]Document Collections[/bold blue]",
        show_header=True,
        header_style="bold white on blue",
        border_style="blue",
        box=ROUNDED,
        pad_edge=False,
        collapse_padding=True,
        show_lines=True,
    )

    table.add_column("ID", style="bright_yellow", no_wrap=True)
    table.add_column("Name", style="bright_green")
    table.add_column("Description", style="bright_white")
    table.add_column("Created At", style="bright_white")

    for collection in collections:  # type: ignore
        table.add_row(
            collection.get("id", ""),
            collection.get("name", ""),
            collection.get("description", ""),
            collection.get("created_at", "")[:19],
        )

    return table


async def ingest_files_from_urls(client: R2RAsyncClient, urls: list[str]):
    """Download and ingest files from given URLs."""
    files_to_ingest = []
    metadatas = []
    document_ids = []
    temp_files = []

    try:
        for url in urls:
            filename = os.path.basename(urlparse(url).path)
            is_pdf = filename.lower().endswith(".pdf")

            with tempfile.NamedTemporaryFile(mode="wb" if is_pdf else "w+", delete=False, suffix=f"_{filename}") as temp_file:
                temp_files.append(temp_file)

                response = requests.get(url)
                response.raise_for_status()
                if is_pdf:
                    temp_file.write(response.content)
                else:
                    temp_file.write(response.text)

                files_to_ingest.append(temp_file.name)
                metadatas.append({"title": filename})
                document_ids.append(str(uuid.uuid5(uuid.NAMESPACE_DNS, url)))

        for it, file in enumerate(files_to_ingest):
            click.echo(f"Ingesting file: {file}")
            response = await client.documents.create(file, metadata=metadatas[it], id=document_ids[it])

        return response["results"]

    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            os.unlink(temp_file.name)


@documents.command()
@click.argument("id", required=True, type=str)
@click.option("--settings", type=JSON, help="Extraction settings as JSON")
@click.option("--run-without-orchestration", is_flag=True, help="Run without orchestration")
@pass_context
async def extract(ctx: click.Context, id: str, settings: Optional[dict], run_without_orchestration: bool = False):
    """Extract entities and relationships from a document."""
    client: R2RAsyncClient = ctx.obj
    run_with_orchestration = not run_without_orchestration

    try:
        with timer():
            response = await client.documents.extract(id=id, settings=settings, run_with_orchestration=run_with_orchestration)
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"[bold red]Error:[/bold red] {str(e)}", err=True)
    except Exception as e:
        click.echo(f"[bold red]Unexpected error:[/bold red] {str(e)}", err=True)


@documents.command()
@click.argument("id", required=True, type=str)
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of items to return. Defaults to 100.")
@click.option("--include-embeddings", is_flag=True, help="Include embeddings in response")
@pass_context
async def list_entities(ctx: click.Context, id: str, offset: int, limit: int, include_embeddings: bool):
    """List entities extracted from a document."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.documents.list_entities(id=id, offset=offset, limit=limit, include_embeddings=include_embeddings)
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"[bold red]Error:[/bold red] {str(e)}", err=True)
    except Exception as e:
        click.echo(f"[bold red]Unexpected error:[/bold red] {str(e)}", err=True)


@documents.command()
@click.argument("id", required=True, type=str)
@click.option("--offset", default=0, help="The offset to start from. Defaults to 0.")
@click.option("--limit", default=100, help="The maximum number of items to return. Defaults to 100.")
@click.option("--entity-names", multiple=True, help="Filter by entity names")
@click.option("--relationship-types", multiple=True, help="Filter by relationship types")
@pass_context
async def list_relationships(ctx: click.Context, id: str, offset: int, limit: int, entity_names: Optional[tuple[str, ...]], relationship_types: Optional[tuple[str, ...]]):
    """List relationships extracted from a document."""
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await client.documents.list_relationships(
                id=id,
                offset=offset,
                limit=limit,
                entity_names=list(entity_names) if entity_names else None,
                relationship_types=list(relationship_types) if relationship_types else None,
            )
        click.echo(json.dumps(response, indent=2))
    except R2RException as e:
        click.echo(f"[bold red]Error:[/bold red] {str(e)}", err=True)
    except Exception as e:
        click.echo(f"[bold red]Unexpected error:[/bold red] {str(e)}", err=True)


@documents.command()
@pass_context
async def create_sample(ctx: click.Context) -> None:
    """Ingest the first sample file into R2R."""
    sample_file_url = "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/aristotle.txt"
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await ingest_files_from_urls(client, [sample_file_url])
        click.echo(f"Sample file ingestion completed. Ingest files response:\n
{response}")
    except R2RException as e:
        click.echo(f"[bold red]Error:[/bold red] {str(e)}", err=True)
    except Exception as e:
        click.echo(f"[bold red]Unexpected error:[/bold red] {str(e)}", err=True)


@documents.command()
@pass_context
async def create_samples(ctx: click.Context) -> None:
    """Ingest multiple sample files into R2R."""
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
    client: R2RAsyncClient = ctx.obj

    try:
        with timer():
            response = await ingest_files_from_urls(client, urls)
        click.echo(f"Sample files ingestion completed. Ingest files response:\n
{response}")
    except R2RException as e:
        click.echo(f"[bold red]Error:[/bold red] {str(e)}", err=True)
    except Exception as e:
        click.echo(f"[bold red]Unexpected error:[/bold red] {str(e)}", err=True)
