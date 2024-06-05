import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from r2r import (
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
    assert response.json() == {"results": "Entries upserted successfully."}


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

    response = client.post(
        "/ingest_files/",
        data={"metadatas": json.dumps([metadata])},
        files=files,
    )
    assert response.status_code == 200
    assert response.json() == {
        "results": ["File 'test.txt' processed successfully."]
    }


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_search(client):
    query = "who was aristotle?"
    response = client.post(
        "/search/",
        json={
            "query": query,
            "search_filters": "{}",
            "search_limit": "10",
        },
    )
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_rag(client):
    query = "who was aristotle?"
    response = client.post(
        "/rag/",
        json={
            "message": query,
            "search_filters": "{}",
            "search_limit": "10",
            "streaming": "false",
        },
    )
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_delete(client):
    response = client.request(
        "DELETE",
        "/delete/",
        json={"keys": ["author"], "values": ["John Doe"]},
    )
    assert response.status_code == 200
    assert response.json() == {"results": "Entries deleted successfully."}


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_get_user_ids(client):
    response = client.get("/get_user_ids/")
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.parametrize("r2r_app", ["pgvector", "local"], indirect=True)
@pytest.mark.asyncio
async def test_get_user_documents_metadata(client):
    user_id = str(generate_id_from_label("user_0"))
    response = client.post(
        "/get_user_documents_metadata/",
        json={"user_id": user_id},
    )
    assert response.status_code == 200
    assert "results" in response.json()
