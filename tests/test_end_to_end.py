import json
import os
import uuid

import pytest
from fastapi.datastructures import UploadFile

from r2r import (
    Document,
    GenerationConfig,
    KVLoggingSingleton,
    R2RApp,
    R2RConfig,
    R2RPipeFactory,
    R2RPipelineFactory,
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

    try:
        providers = R2RProviderFactory(config).create_providers()
        pipes = R2RPipeFactory(config, providers).create_pipes()
        pipelines = R2RPipelineFactory(config, pipes).create_pipelines()

        r2r = R2RApp(
            config=config,
            providers=providers,
            pipelines=pipelines,
        )

        try:
            KVLoggingSingleton.configure(config.logging)
        except:
            KVLoggingSingleton._config.logging_path = (
                config.logging.logging_path
            )

        yield r2r
    finally:
        if os.path.exists(config.logging.logging_path):
            os.remove(config.logging.logging_path)


@pytest.fixture
def logging_connection():
    return KVLoggingSingleton()


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_txt_document(r2r_app, logging_connection):
    await r2r_app.aingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_1"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )
    run_info = await logging_connection.get_run_info(
        log_type_filter="ingestion"
    )
    logs = await logging_connection.get_logs([run.run_id for run in run_info])
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
            filename="test.txt",
            file=open(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "r2r",
                    "examples",
                    "data",
                    "test.txt",
                ),
                "rb",
            ),
        )
    ]
    # Set file size manually
    for file in files:
        file.file.seek(0, 2)  # Move to the end of the file
        file.size = file.file.tell()  # Get the file size
        file.file.seek(0)  # Move back to the start of the file

    await r2r_app.aingest_files(metadatas=[metadata], files=files)

    run_info = await logging_connection.get_run_info(
        log_type_filter="ingestion"
    )
    logs = await logging_connection.get_logs([run.run_id for run in run_info])
    assert len(logs) == 2, f"Expected 2 logs, but got {len(logs)}"

    for log in logs:
        assert log["key"] in ["fragment", "extraction"]
        value = json.loads(log["value"])
        assert value["data"] == "this is a test text"
        assert value["document_id"] == str(generate_id_from_label("test.txt"))


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_search_txt_file(r2r_app, logging_connection):
    # Prepare the test data
    metadata = {}
    files = [
        UploadFile(
            filename="aristotle.txt",
            file=open(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "r2r",
                    "examples",
                    "data",
                    "aristotle.txt",
                ),
                "rb",
            ),
        ),
    ]

    # Set file size manually
    for file in files:
        file.file.seek(0, 2)  # Move to the end of the file
        file.size = file.file.tell()  # Get the file size
        file.file.seek(0)  # Move back to the start of the file

    # Convert metadata to JSON string

    await r2r_app.aingest_files(metadatas=[metadata], files=files)

    run_info = await logging_connection.get_run_info(
        log_type_filter="ingestion"
    )
    logs = await logging_connection.get_logs(
        [run.run_id for run in run_info], 100
    )
    assert len(logs) == 100, f"Expected 100 logs, but got {len(logs)}"

    for log in logs:
        assert log["key"] in ["fragment", "extraction"]
        value = json.loads(log["value"])
        assert value["document_id"] == str(
            generate_id_from_label("aristotle.txt")
        )

    search_results = await r2r_app.asearch("who was aristotle?")
    assert len(search_results["results"]) == 10
    assert (
        "was an Ancient Greek philosopher and polymath"
        in search_results["results"][0]["metadata"]["text"]
    )

    search_results = await r2r_app.asearch(
        "who was aristotle?", search_limit=20
    )
    assert len(search_results["results"]) == 20
    assert (
        "was an Ancient Greek philosopher and polymath"
        in search_results["results"][0]["metadata"]["text"]
    )

    ## test streaming
    response = await r2r_app.arag(
        message="Who was aristotle?",
        rag_generation_config=GenerationConfig(
            **{"model": "gpt-3.5-turbo", "stream": True}
        ),
    )
    collector = ""
    async for chunk in response:
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
    await r2r_app.aingest_documents(
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
    search_results = await r2r_app.asearch("who was aristotle?")

    # Verify that the search results are not empty
    assert (
        len(search_results["results"]) > 0
    ), "Expected search results, but got none"
    assert (
        search_results["results"][0]["metadata"]["text"]
        == "The quick brown fox jumps over the lazy dog."
    )

    # Delete the document
    delete_result = await r2r_app.adelete(["author"], ["John Doe"])

    # Verify the deletion was successful
    assert delete_result == {
        "results": "Entries deleted successfully."
    }, f"Expected successful deletion message, but got {delete_result}"

    # Search for the document again
    search_results_2 = await r2r_app.asearch("who was aristotle?")

    # Verify that the search results are empty
    assert (
        len(search_results_2["results"]) == 0
    ), f"Expected no search results, but got {search_results_2['results']}"


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_user_documents(r2r_app, logging_connection):
    user_id_0 = generate_id_from_label("user_0")
    user_id_1 = generate_id_from_label("user_1")
    await r2r_app.aingest_documents(
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
    user_id_results = await r2r_app.aget_user_ids()
    user_ids = user_id_results["results"]
    assert set(user_ids) == set(
        [str(user_id_0), str(user_id_1)]
    ), f"Expected user ids {user_id_0} and {user_id_1}, but got {user_ids}"

    user_0_docs = await r2r_app.aget_user_documents_metadata(
        user_id=str(user_id_0)
    )
    user_1_docs = await r2r_app.aget_user_documents_metadata(
        user_id=str(user_id_1)
    )

    assert (
        len(user_0_docs["results"]) == 1
    ), f"Expected 1 document for user {user_id_0}, but got {len(user_0_docs['results'])}"
    assert (
        len(user_1_docs["results"]) == 1
    ), f"Expected 1 document for user {user_id_1}, but got {len(user_1_docs['results'])}"
    assert user_0_docs["results"][0]["document_id"] == str(
        generate_id_from_label("doc_0")
    ), f"Expected document id {str(generate_id_from_label('doc_0'))} for user {user_id_0}, but got {user_0_docs['results'][0]['document_id']}"
    assert user_1_docs["results"][0]["document_id"] == str(
        generate_id_from_label("doc_1")
    ), f"Expected document id {str(generate_id_from_label('doc_1'))} for user {user_id_1}, but got {user_1_docs['results'][0]['document_id']}"


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_delete_by_id(r2r_app, logging_connection):
    await r2r_app.aingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_1"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )
    search_results = await r2r_app.asearch("who was aristotle?")

    assert len(search_results["results"]) > 0
    await r2r_app.adelete(
        ["document_id"], [str(generate_id_from_label("doc_1"))]
    )
    search_results = await r2r_app.asearch("who was aristotle?")
    assert len(search_results["results"]) == 0


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_double_ingest(r2r_app, logging_connection):
    await r2r_app.aingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_1"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )
    search_results = await r2r_app.asearch("who was aristotle?")

    assert len(search_results["results"]) == 1
    await r2r_app.aingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_1"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )
    search_results = await r2r_app.asearch("who was aristotle?")
    assert len(search_results["results"]) == 1
