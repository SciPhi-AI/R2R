import json
import os
import uuid

import pytest
from fastapi.datastructures import UploadFile

from r2r import (
    DefaultR2RPipelineFactory,
    Document,
    PipeLoggingConnectionSingleton,
    R2RApp,
    R2RConfig,
    R2RProviderFactory,
    generate_id_from_label,
)


@pytest.fixture(scope="function")
def r2r_app(request):
    config = R2RConfig.from_json()
    config.logging.provider = "local"
    config.logging.logging_path = uuid.uuid4().hex + ".log"

    vector_db_provider = request.param
    if vector_db_provider == "pgvector":
        config.vector_database.provider = "pgvector"
        config.vector_database.collection_name = config.logging.logging_path
    elif vector_db_provider == "local":
        config.vector_database.provider = "local"
        config.vector_database.extra_fields[
            "db_path"
        ] = config.logging.logging_path

    print("config.logging = ", config.logging)
    print("config.vector_database = ", config.vector_database)

    try:
        PipeLoggingConnectionSingleton.configure(config.logging)
    except:
        PipeLoggingConnectionSingleton._config.logging_path = (
            config.logging.logging_path
        )

    try:
        providers = R2RProviderFactory(config).create_providers()
        pipelines = DefaultR2RPipelineFactory(
            config, providers
        ).create_pipelines()

        r2r = R2RApp(
            config=config,
            providers=providers,
            ingestion_pipeline=pipelines.ingestion_pipeline,
            search_pipeline=pipelines.search_pipeline,
            rag_pipeline=pipelines.rag_pipeline,
            streaming_rag_pipeline=pipelines.streaming_rag_pipeline,
        )

        yield r2r
    finally:
        if os.path.exists(config.logging.logging_path):
            os.remove(config.logging.logging_path)


@pytest.fixture
def logging_connection():
    return PipeLoggingConnectionSingleton()


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_txt_document(r2r_app, logging_connection):
    await r2r_app.ingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_1"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )
    run_ids = await logging_connection.get_run_ids(pipeline_type="ingestion")
    logs = await logging_connection.get_logs(run_ids)
    assert len(logs) == 2, f"Expected 2 logs, but got {len(logs)}"

    for log in logs:
        assert log["key"] in ["fragment", "extraction"]
        value = json.loads(log["value"])
        assert value["data"] == "The quick brown fox jumps over the lazy dog."
        assert value["document_id"] == str(generate_id_from_label("doc_1"))


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_txt_file(r2r_app, logging_connection):
    # Prepare the test data
    metadata = {"author": "John Doe"}
    files = [
        UploadFile(
            filename="test1.txt",
            file=open("r2r/examples/data/test1.txt", "rb"),
        ),
    ]
    # Set file size manually
    for file in files:
        file.file.seek(0, 2)  # Move to the end of the file
        file.size = file.file.tell()  # Get the file size
        file.file.seek(0)  # Move back to the start of the file

    # Convert metadata to JSON string
    metadata_str = json.dumps(metadata)

    await r2r_app.ingest_files(metadata=metadata_str, files=files)

    run_ids = await logging_connection.get_run_ids(pipeline_type="ingestion")
    logs = await logging_connection.get_logs(run_ids)
    assert len(logs) == 2, f"Expected 2 logs, but got {len(logs)}"

    for log in logs:
        assert log["key"] in ["fragment", "extraction"]
        value = json.loads(log["value"])
        assert value["data"] == "this is a test text"
        assert value["document_id"] == str(generate_id_from_label("test1.txt"))


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_and_search_larger_txt_file(r2r_app, logging_connection):
    # Prepare the test data
    metadata = {}
    files = [
        UploadFile(
            filename="test2.txt",
            file=open("r2r/examples/data/test2.txt", "rb"),
        ),
    ]
    # Set file size manually
    for file in files:
        file.file.seek(0, 2)  # Move to the end of the file
        file.size = file.file.tell()  # Get the file size
        file.file.seek(0)  # Move back to the start of the file

    # Convert metadata to JSON string
    metadata_str = json.dumps(metadata)

    await r2r_app.ingest_files(metadata=metadata_str, files=files)

    run_ids = await logging_connection.get_run_ids(pipeline_type="ingestion")
    logs = await logging_connection.get_logs(run_ids, 100)
    assert len(logs) == 100, f"Expected 100 logs, but got {len(logs)}"

    for log in logs:
        assert log["key"] in ["fragment", "extraction"]
        value = json.loads(log["value"])
        assert value["document_id"] == str(generate_id_from_label("test2.txt"))

    search_results = await r2r_app.search("who was aristotle?")
    assert len(search_results["results"]) == 10
    assert (
        "was an Ancient Greek philosopher and polymath"
        in search_results["results"][0].metadata["text"]
    )

    search_results = await r2r_app.search(
        "who was aristotle?", search_limit=20
    )
    assert len(search_results["results"]) == 20
    assert (
        "was an Ancient Greek philosopher and polymath"
        in search_results["results"][0].metadata["text"]
    )

    ## test streaming
    response = await r2r_app.rag(query="Who was aristotle?", streaming=True)
    collector = ""
    async for chunk in response.body_iterator:
        collector += chunk
    assert "Aristotle" in collector
    assert "Greek" in collector
    assert "philosopher" in collector
    assert "polymath" in collector
    assert "Ancient" in collector


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_search_then_delete(r2r_app, logging_connection):
    # Ingest a document
    await r2r_app.ingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_1"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )

    # Search for the document
    search_results = await r2r_app.search("who was aristotle?")

    # Verify that the search results are not empty
    assert len(search_results["results"]) > 0, "Expected search results, but got none"
    assert search_results["results"][0].metadata["text"] == "The quick brown fox jumps over the lazy dog."

    # Delete the document
    delete_result = await r2r_app.delete("author", "John Doe")

    # Verify the deletion was successful
    assert delete_result == {"results": "Entries deleted successfully."}, f"Expected successful deletion message, but got {delete_result}"

    # Search for the document again
    search_results_2 = await r2r_app.search("who was aristotle?")

    # Verify that the search results are empty
    assert len(search_results_2["results"]) == 0, f"Expected no search results, but got {search_results_2['results']}"


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_user_documents(r2r_app, logging_connection):
    user_id_0 = generate_id_from_label("user_0")
    user_id_1 = generate_id_from_label("user_1")
    await r2r_app.ingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_0"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe", "user_id": user_id_0},
            ),
            Document(
                id=generate_id_from_label("doc_1"),
                data="The lazy dog jumps over the quick brown fox.",
                type="txt",
                metadata={"author": "John Doe", "user_id": user_id_1},
            ),
        ]
    )
    user_id_results = await r2r_app.get_user_ids()
    user_ids = user_id_results["results"]
    assert set(user_ids) == set(
        [str(user_id_0), str(user_id_1)]
    ), f"Expected user ids {user_id_0} and {user_id_1}, but got {user_ids}"

    user_0_docs = await r2r_app.get_user_document_ids(user_id=str(user_id_0))
    user_1_docs = await r2r_app.get_user_document_ids(user_id=str(user_id_1))

    assert (
        len(user_0_docs) == 1
    ), f"Expected 1 document for user {user_id_0}, but got {len(user_0_docs)}"
    assert (
        len(user_1_docs) == 1
    ), f"Expected 1 document for user {user_id_1}, but got {len(user_1_docs)}"
    assert user_0_docs["results"][0] == str(
        generate_id_from_label("doc_0")
    ), f"Expected document id {str(generate_id_from_label('doc_0'))} for user {user_id_0}, but got {user_0_docs[0]}"
    assert user_1_docs["results"][0] == str(
        generate_id_from_label("doc_1")
    ), f"Expected document id {str(generate_id_from_label('doc_1'))} for user {user_id_1}, but got {user_1_docs[0]}"
