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
def r2r_app():
    config = R2RConfig.from_json()
    config.logging.provider = "local"
    config.logging.logging_path = uuid.uuid4().hex + ".log"

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
