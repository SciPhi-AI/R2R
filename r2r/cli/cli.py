import json
import os
import time
import uuid

import click
from fastapi.datastructures import UploadFile

from r2r import (
    R2R,
    GenerationConfig,
    R2RBuilder,
    R2RClient,
    R2RConfig,
    generate_id_from_label,
)
from r2r.base import (
    AnalysisTypes,
    FilterCriteria,
    KGSearchSettings,
    VectorSearchSettings,
)


class JsonParamType(click.ParamType):
    name = "json"

    def convert(self, value, param, ctx):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            self.fail(f"'{value}' is not a valid JSON string", param, ctx)


JSON = JsonParamType()


@click.group()
@click.option(
    "--config-path", default=None, help="Path to the configuration file"
)
@click.option(
    "--config-name", default="default", help="Name of the configuration to use"
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
def cli(ctx, config_path, config_name, client_server_mode, base_url):
    """R2R CLI for all core operations."""
    if config_path and config_name != "default":
        raise click.UsageError(
            "Cannot specify both config_path and config_name"
        )

    if config_path:
        config = R2RConfig.from_json(config_path)
    else:
        config = R2RConfig.from_json(R2RBuilder.CONFIG_OPTIONS[config_name])

    if client_server_mode and ctx.invoked_subcommand != "serve":
        ctx.obj = R2RClient(base_url)
    else:
        ctx.obj = R2R(config)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to run the server on")
@click.option("--port", default=8000, help="Port to run the server on")
@click.pass_obj
def serve(obj, host, port):
    """Start the R2R server."""
    obj.serve(host, port)


@cli.command()
@click.argument("file_paths", nargs=-1)
@click.option("--user-ids", multiple=True, help="User IDs for ingestion")
@click.option("--no-media", is_flag=True, help="Exclude media files")
@click.option("--all-sample-files", is_flag=True, help="Use all sample files?")
@click.pass_obj
def ingest(obj, file_paths, user_ids, no_media, all_sample_files):
    """Ingest files into R2R."""
    file_paths = list(file_paths)
    if not file_paths:
        # TODO - Relocate this logic for the quickstart / tutorial
        root_path = os.path.dirname(os.path.abspath(__file__))
        if not all_sample_files:
            file_paths = [
                os.path.join(
                    root_path, "..", "examples", "data", "aristotle.txt"
                )
            ]
        else:
            file_paths = [
                os.path.join(
                    root_path, "..", "examples", "data", "aristotle.txt"
                ),
                os.path.join(root_path, "..", "examples", "data", "got.txt"),
                os.path.join(
                    root_path, "..", "examples", "data", "screen_shot.png"
                ),
                os.path.join(
                    root_path, "..", "examples", "data", "pg_essay_1.html"
                ),
                os.path.join(
                    root_path, "..", "examples", "data", "pg_essay_2.html"
                ),
                os.path.join(
                    root_path, "..", "examples", "data", "pg_essay_3.html"
                ),
                os.path.join(
                    root_path, "..", "examples", "data", "pg_essay_4.html"
                ),
                os.path.join(
                    root_path, "..", "examples", "data", "pg_essay_5.html"
                ),
                os.path.join(
                    root_path, "..", "examples", "data", "lyft_2021.pdf"
                ),
                os.path.join(
                    root_path, "..", "examples", "data", "uber_2021.pdf"
                ),
                os.path.join(
                    root_path, "..", "examples", "data", "sample.mp3"
                ),
                os.path.join(
                    root_path, "..", "examples", "data", "sample2.mp3"
                ),
            ]
            if not user_ids and all_sample_files:  # tutorial mode
                # TODO - Relocate this logic for the quickstart / tutorial
                user_ids = [
                    "063edaf8-3e63-4cb9-a4d6-a855f36376c3",
                    "45c3f5a8-bcbe-43b1-9b20-51c07fd79f14",
                    "c6c23d85-6217-4caa-b391-91ec0021a000",
                    None,
                ] * 3

    if no_media:
        excluded_types = ["jpeg", "jpg", "png", "svg", "mp3", "mp4"]
        file_paths = [
            file_path
            for file_path in file_paths
            if file_path.split(".")[-1] not in excluded_types
        ]

    ids = [
        generate_id_from_label(file_path.split(os.path.sep)[-1])
        for file_path in file_paths
    ]

    files = [
        UploadFile(
            filename=file_path,
            file=open(file_path, "rb"),
        )
        for file_path in file_paths
    ]

    for file in files:
        file.file.seek(0, 2)
        file.size = file.file.tell()
        file.file.seek(0)

    t0 = time.time()

    if isinstance(obj, R2RClient):
        response = obj.ingest_files(
            metadatas=None,
            file_paths=file_paths,
            document_ids=ids,
            user_ids=user_ids if user_ids else None,
            monitor=True,
        )
    else:
        metadatas = [{} for _ in file_paths]
        response = obj.ingest_files(
            files=files,
            metadatas=metadatas,
            document_ids=ids,
            user_ids=user_ids if user_ids else None,
        )
    t1 = time.time()
    click.echo(f"Time taken to ingest files: {t1-t0:.2f} seconds")
    click.echo(response)


@cli.command()
@click.argument("file_tuples", nargs=-1)
@click.pass_obj
def update_documents(obj, file_tuples):
    """Update existing documents in R2R."""
    new_files = [
        UploadFile(
            filename=new_file,
            file=open(new_file, "rb"),
        )
        for old_file, new_file in file_tuples
    ]

    for file in new_files:
        file.file.seek(0, 2)
        file.size = file.file.tell()
        file.file.seek(0)

    metadatas = [
        {
            "title": old_file,
        }
        for old_file, new_file in file_tuples
    ]
    t0 = time.time()

    if isinstance(obj, R2RClient):
        response = obj.update_files(
            metadatas=metadatas,
            files=[new for old, new in file_tuples],
            document_ids=[
                generate_id_from_label(old_file.split(os.path.sep)[-1])
                for old_file, new_file in file_tuples
            ],
            monitor=True,
        )
    else:
        response = obj.update_files(
            files=new_files,
            document_ids=[
                generate_id_from_label(old_file.split(os.path.sep)[-1])
                for old_file, new_file in file_tuples
            ],
        )
    t1 = time.time()
    click.echo(f"Time taken to update files: {t1-t0:.2f} seconds")
    click.echo(response)


@cli.command()
@click.option(
    "--query", prompt="Enter your search query", help="The search query"
)
@click.option(
    "--use-vector-search", is_flag=True, default=True, help="Use vector search"
)
@click.option(
    "--search-filters", type=JsonParamType(), help="Search filters as JSON"
)
@click.option(
    "--search-limit", default=10, help="Number of search results to return"
)
@click.option("--do-hybrid-search", is_flag=True, help="Perform hybrid search")
@click.option(
    "--use-kg-search", is_flag=True, help="Use knowledge graph search"
)
@click.option("--kg-agent-model", default="gpt-4o", help="Model for KG agent")
@click.pass_obj
def search(
    obj,
    query,
    use_vector_search,
    search_filters,
    search_limit,
    do_hybrid_search,
    use_kg_search,
    kg_agent_model,
):
    """Perform a search query."""
    kg_agent_generation_config = GenerationConfig(model=kg_agent_model)

    t0 = time.time()
    if isinstance(obj, R2RClient):
        results = obj.search(
            query,
            use_vector_search,
            search_filters,
            search_limit,
            do_hybrid_search,
            use_kg_search,
            kg_agent_generation_config,
        )
    else:
        results = obj.search(
            query,
            VectorSearchSettings(
                use_vector_search=use_vector_search,
                search_filters=search_filters or {},
                search_limit=search_limit,
                do_hybrid_search=do_hybrid_search,
            ),
            KGSearchSettings(
                use_kg_search=use_kg_search,
                agent_generation_config=kg_agent_generation_config,
            ),
        )

    if isinstance(results, dict) and "results" in results:
        results = results["results"]

    if "vector_search_results" in results:
        click.echo("Vector search results:")
        for result in results["vector_search_results"]:
            click.echo(result)
    if "kg_search_results" in results and results["kg_search_results"]:
        click.echo("KG search results:", results["kg_search_results"])

    t1 = time.time()
    click.echo(f"Time taken to search: {t1-t0:.2f} seconds")


@cli.command()
@click.option("--query", prompt="Enter your RAG query", help="The RAG query")
@click.option(
    "--use-vector-search", is_flag=True, default=True, help="Use vector search"
)
@click.option(
    "--search-filters", type=JsonParamType(), help="Search filters as JSON"
)
@click.option(
    "--search-limit", default=10, help="Number of search results to return"
)
@click.option("--do-hybrid-search", is_flag=True, help="Perform hybrid search")
@click.option(
    "--use-kg-search", is_flag=True, help="Use knowledge graph search"
)
@click.option("--kg-agent-model", default="gpt-4o", help="Model for KG agent")
@click.option("--rag-model", default="gpt-4o", help="Model to use for RAG")
@click.option("--stream", is_flag=True, help="Stream the RAG response")
@click.pass_obj
def rag(
    obj,
    query,
    use_vector_search,
    search_filters,
    search_limit,
    do_hybrid_search,
    use_kg_search,
    kg_agent_model,
    rag_model,
    stream,
):
    """Perform a RAG query."""
    t0 = time.time()

    kg_agent_generation_config = GenerationConfig(model=kg_agent_model)
    rag_generation_config = GenerationConfig(model=rag_model, stream=stream)

    if isinstance(obj, R2RClient):
        response = obj.rag(
            query=query,
            use_vector_search=use_vector_search,
            search_filters=search_filters or {},
            search_limit=search_limit,
            do_hybrid_search=do_hybrid_search,
            use_kg_search=use_kg_search,
            kg_agent_generation_config=kg_agent_generation_config,
            rag_generation_config=rag_generation_config,
        )
        if not stream:
            response = response["results"]
            t1 = time.time()
            click.echo(f"Time taken to get RAG response: {t1-t0:.2f} seconds")
            click.echo(f"Search Results:\n{response['search_results']}")
            click.echo(f"Completion:\n{response['completion']}")
        else:
            for chunk in response:
                click.echo(chunk, nl=False)
            t1 = time.time()
            click.echo(
                f"\nTime taken to stream RAG response: {t1-t0:.2f} seconds"
            )
    else:
        response = obj.rag(
            query,
            vector_search_settings=VectorSearchSettings(
                use_vector_search=use_vector_search,
                search_filters=search_filters or {},
                search_limit=search_limit,
                do_hybrid_search=do_hybrid_search,
            ),
            kg_search_settings=KGSearchSettings(
                use_kg_search=use_kg_search,
                agent_generation_config=kg_agent_generation_config,
            ),
            rag_generation_config=rag_generation_config,
        )

        if not stream:
            t1 = time.time()
            click.echo(f"Time taken to get RAG response: {t1-t0:.2f} seconds")
            click.echo(f"Search Results:\n{response.search_results}")
            click.echo(f"Completion:\n{response.completion}")
        else:
            for chunk in response:
                click.echo(chunk, nl=False)
            t1 = time.time()
            click.echo(
                f"\nTime taken to stream RAG response: {t1-t0:.2f} seconds"
            )


@cli.command()
@click.option("--query", help="The query to evaluate")
@click.option("--context", help="The context for evaluation")
@click.option("--completion", help="The completion to evaluate")
@click.option(
    "--eval-model", default="gpt-3.5-turbo", help="Model for evaluation"
)
@click.pass_obj
def evaluate(obj, query, context, completion, eval_model):
    """Evaluate a RAG response."""
    if not query:
        query = "What is the meaning of life?"
    if not context:
        context = """Search Results:
        1. The meaning of life is 42.
        2. The car is red.
        3. The meaning of life is to help others.
        4. The car is blue.
        5. The meaning of life is to learn and grow.
        6. The car is green.
        7. The meaning of life is to make a difference.
        8. The car is yellow.
        9. The meaning of life is to enjoy the journey.
        10. The car is black.
        """
    if not completion:
        completion = "The meaning of life is to help others, learn and grow, and to make a difference."

    t0 = time.time()
    if isinstance(obj, R2RClient):
        response = obj.evaluate(
            query=query,
            context=context,
            completion=completion,
        )
    else:
        response = obj.evaluate(
            query=query,
            context=context,
            completion=completion,
            eval_generation_config=GenerationConfig(model=eval_model),
        )

    t1 = time.time()
    click.echo(f"Time taken to evaluate: {t1-t0:.2f} seconds")
    click.echo(response)


@cli.command()
@click.option("--keys", multiple=True, help="Keys for deletion")
@click.option("--values", multiple=True, help="Values for deletion")
@click.option("--version", help="Version for deletion")
@click.pass_obj
def delete(obj, keys, values, version):
    """Delete documents from R2R."""
    if version:
        keys = list(keys) + ["version"]
        values = list(values) + [version]
    t0 = time.time()
    response = obj.delete(keys, values)
    t1 = time.time()
    click.echo(f"Time taken to delete: {t1-t0:.2f} seconds")
    click.echo(response)


@cli.command()
@click.option("--log-type-filter", help="Filter for specific log types")
@click.pass_obj
def logs(obj, log_type_filter):
    """Retrieve logs from R2R."""
    t0 = time.time()
    response = obj.logs(log_type_filter)
    t1 = time.time()
    click.echo(f"Time taken to get logs: {t1-t0:.2f} seconds")
    click.echo(response)


@cli.command()
@click.pass_obj
def app_settings(obj):
    """Retrieve application settings."""
    t0 = time.time()
    response = obj.app_settings()
    t1 = time.time()
    click.echo(f"Time taken to get app data: {t1-t0:.2f} seconds")
    click.echo(response)


@cli.command()
@click.option(
    "--filters", type=JSON, help="Filter criteria for analytics as JSON"
)
@click.option(
    "--analysis-types", type=JSON, help="Types of analysis to perform as JSON"
)
@click.pass_obj
def analytics(obj, filters, analysis_types):
    """Perform analytics on R2R data."""
    t0 = time.time()
    filter_criteria = FilterCriteria(filters=filters)
    analysis_types = AnalysisTypes(analysis_types=analysis_types)
    if isinstance(obj, R2RClient):
        response = obj.analytics(
            filter_criteria=filter_criteria.model_dump(),
            analysis_types=analysis_types.model_dump(),
        )
    else:
        response = obj.analytics(
            filter_criteria=filter_criteria, analysis_types=analysis_types
        )
    t1 = time.time()
    click.echo(f"Time taken to get analytics: {t1-t0:.2f} seconds")
    click.echo(response)


@cli.command()
@click.option("--user-ids", multiple=True, help="User IDs to overview")
@click.pass_obj
def users_overview(obj, user_ids=None):
    """Get an overview of users."""
    t0 = time.time()
    user_ids = list(user_ids) if user_ids and user_ids != () else None
    if isinstance(obj, R2RClient):
        response = obj.users_overview(
            list(user_ids) if user_ids and user_ids != () else None
        )
    else:
        response = obj.users_overview(
            list(user_ids) if user_ids and user_ids != () else None
        )
    t1 = time.time()
    click.echo(f"Time taken to get user stats: {t1-t0:.2f} seconds")
    if isinstance(response, dict) and "results" in response:
        response = response["results"]
    for user in response:
        click.echo(user)


@cli.command()
@click.option("--document-ids", multiple=True, help="Document IDs to overview")
@click.option("--user-ids", multiple=True, help="User IDs to filter documents")
@click.pass_obj
def documents_overview(obj, document_ids=None, user_ids=None):
    """Get an overview of documents."""
    t0 = time.time()
    if isinstance(obj, R2RClient):
        results = obj.documents_overview(
            list(document_ids) if document_ids else None,
            list(user_ids) if user_ids else None,
        )
    else:
        results = obj.documents_overview(
            list(document_ids) if document_ids else None,
            list(user_ids) if user_ids else None,
        )
    t1 = time.time()
    click.echo(f"Time taken to get document info: {t1-t0:.2f} seconds")
    if isinstance(results, dict) and "results" in results:
        results = results["results"]
    for document in results:
        click.echo(document)


@cli.command()
@click.argument("document-id")
@click.pass_obj
def document_chunks(obj, document_id):
    """Retrieve chunks of a specific document."""
    t0 = time.time()
    doc_uuid = uuid.UUID(document_id)
    if isinstance(obj, R2RClient):
        results = obj.document_chunks(doc_uuid)
    else:
        results = obj.document_chunks(doc_uuid)
    t1 = time.time()
    click.echo(f"Time taken to get document chunks: {t1-t0:.2f} seconds")
    if isinstance(results, dict) and "results" in results:
        results = results["results"]
    for chunk in results:
        click.echo(chunk)


def main():
    cli()


if __name__ == "__main__":
    main()
