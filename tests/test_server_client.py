import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from r2r import (
    KGSearchSettings,
    KVLoggingSingleton,
    R2RApp,
    R2RConfig,
    R2RIngestFilesRequest,
    R2RPipeFactory,
    R2RPipelineFactory,
    R2RProviderFactory,
    R2RRAGRequest,
    R2RSearchRequest,
    VectorSearchSettings,
    generate_id_from_label,
)


@pytest.fixture(scope="function")
def r2r_app(request):
    config = R2RConfig.from_json()
    config.logging.provider = "local"
    config.logging.logging_path = uuid.uuid4().hex

    vector_db_provider = request.param
    if vector_db_provider == "pgvector":
        config.vector_database.provider = "pgvector"
        config.vector_database.collection_name = config.logging.logging_path
    elif vector_db_provider == "local":
        config.vector_database.provider = "local"
        config.vector_database.extra_fields["db_path"] = (
            config.logging.logging_path
        )

    try:
        providers = R2RProviderFactory(config).create_providers()
        pipes = R2RPipeFactory(config, providers).create_pipes()
        pipelines = R2RPipelineFactory(config, pipes).create_pipelines()

        r2r = R2RApp(
            config=config,
            providers=providers,
            pipes=pipes,
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


@pytest.fixture(scope="function")
def client(r2r_app):
    return TestClient(r2r_app.app)


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_txt_document(client):
    response = client.post(
        "/ingest_documents/",
        json={
            "documents": [
                {
                    "id": str(generate_id_from_label("doc_1")),
                    "data": "The quick brown fox jumps over the lazy dog.",
                    "type": "txt",
                    "metadata": {"author": "John Doe"},
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "results": {
            "processed_documents": [
                "Document '10e57509-1331-560e-b825-b49df3fe209b' processed successfully."
            ],
            "skipped_documents": [],
        }
    }


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_txt_file(client):
    # Prepare the test data
    metadata = {"author": "John Doe"}
    files = [
        (
            "files",
            (
                "test.txt",
                open("r2r/examples/data/test.txt", "rb"),
                "text/plain",
            ),
        ),
    ]

    request = R2RIngestFilesRequest(
        metadatas=[metadata],
    )

    response = client.post(
        "/ingest_files/",
        # must use data instead of json when sending files
        # data={"metadatas": json.dumps([metadata])},
        data={k: json.dumps(v) for k, v in json.loads(request.json()).items()},
        files=files,
    )

    assert response.status_code == 200
    assert response.json() == {
        "results": {
            "processed_documents": ["File 'test.txt' processed successfully."],
            "skipped_documents": [],
        }
    }


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_search(client):
    query = "who was aristotle?"
    search_request = R2RSearchRequest(
        query=query,
        vector_settings=VectorSearchSettings(),
        kg_settings=KGSearchSettings(),
    )

    response = client.post("/search/", json=search_request.dict())
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_rag(client):
    query = "who was aristotle?"
    request = R2RRAGRequest(
        query=query,
        vector_settings=VectorSearchSettings(),
        kg_settings=KGSearchSettings(),
        rag_generation_config=None,
    )

    response = client.post("/rag/", json=json.loads(request.json()))
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_delete(client):

    metadata = {"author": "John Doe"}
    files = [
        (
            "files",
            (
                "test.txt",
                open("r2r/examples/data/test.txt", "rb"),
                "text/plain",
            ),
        ),
    ]
    request = R2RIngestFilesRequest(
        metadatas=[metadata],
    )

    response = client.post(
        "/ingest_files/",
        data={k: json.dumps(v) for k, v in json.loads(request.json()).items()},
        files=files,
    )

    print("response = ", response)
    response = client.request(
        "DELETE",
        "/delete/",
        json={"keys": ["author"], "values": ["John Doe"]},
    )
    assert response.status_code == 200
    assert response.json() == {"results": "Entries deleted successfully."}
