import json
import os
import subprocess
import time

import pytest

from r2r.core import R2RClient
from r2r.core.utils import generate_id_from_label

"""
To run the test locally, run
export LOCAL_DB_PATH=local.sqlite
export OPENAI_API_KEY=[your open ai key]
"""


@pytest.fixture(scope="session", autouse=True)
def r2r_server():
    # Start the R2R server using poetry run uvicorn
    server_process = subprocess.Popen(
        [
            "poetry",
            "run",
            "uvicorn",
            "r2r.examples.servers.configurable_pipeline:app",
            "--port=8010",
            "--workers=1",
        ]
    )

    # Wait for the server to start up (adjust the delay if needed)
    time.sleep(5)

    yield

    # Stop the R2R server after the tests complete
    server_process.terminate()
    server_process.wait()

    # Delete the local.sqlite file
    sqlite_file = "local.sqlite"
    if os.path.exists(sqlite_file):
        os.remove(sqlite_file)
    else:
        raise FileNotFoundError(f"Expected {sqlite_file} not found")


@pytest.fixture(scope="module")
def client():
    base_url = "http://localhost:8010"
    return R2RClient(base_url)


def test_ingest_txt_document(client):
    user_id = str(generate_id_from_label("user_0"))
    documents = [
        {
            "id": str(generate_id_from_label("doc_1")),
            "data": "The quick brown fox jumps over the lazy dog.",
            "type": "txt",
            "metadata": {"author": "John Doe", "user_id": user_id},
        }
    ]
    response = client.ingest_documents(documents)
    assert response == {"results": "Entries upserted successfully."}


def test_ingest_txt_file(client):
    user_id = str(generate_id_from_label("user_1"))
    metadata = {"author": "John Doe", "user_id": user_id}
    files = ["r2r/examples/data/test1.txt"]
    response = client.ingest_files(metadata, files)
    assert response == {
        "results": [
            "File 'r2r/examples/data/test1.txt' processed successfully for each file"
        ]
    }


@pytest.mark.dependency(
    depends=["test_ingest_txt_document", "test_ingest_txt_file"]
)
def test_search(client):
    query = "who was aristotle?"
    response = client.search(query)
    assert "results" in response
    assert len(response["results"]) > 0


@pytest.mark.dependency(
    depends=["test_ingest_txt_document", "test_ingest_txt_file"]
)
def test_rag(client):
    query = "who was aristotle?"
    response = client.rag(query)
    assert "results" in response


@pytest.mark.dependency(
    depends=[
        "test_ingest_txt_document",
        "test_ingest_txt_file",
        "test_search",
        "test_rag",
    ]
)
def test_delete(client):
    response = client.delete("author", "John Doe")
    assert response == {"results": "Entries deleted successfully."}


@pytest.mark.dependency(
    depends=[
        "test_ingest_txt_document",
        "test_ingest_txt_file",
        "test_search",
        "test_rag",
    ]
)
def test_get_user_ids(client):
    response = client.get_user_ids()
    assert "results" in response
    assert len(response["results"]) == 2
    assert set(response["results"]) == {
        str(generate_id_from_label("user_0")),
        str(generate_id_from_label("user_1")),
    }


@pytest.mark.dependency(
    depends=[
        "test_ingest_txt_document",
        "test_ingest_txt_file",
        "test_search",
        "test_rag",
    ]
)
def test_get_user_document_ids(client):
    user_id = str(generate_id_from_label("user_0"))
    response = client.get_user_document_ids(user_id)
    assert "results" in response
    assert len(response["results"]) == 1
    assert response["results"][0] == str(generate_id_from_label("doc_1"))
