import asyncio
import json
import os
import subprocess
import tempfile
import time

import pytest

from r2r.client import R2RClient
from r2r.core.utils import generate_id_from_label


@pytest.fixture(scope="session", autouse=True)
def r2r_server():
    # Start the R2R server using poetry run uvicorn
    server_process = subprocess.Popen(
        [
            "poetry",
            "run",
            "uvicorn",
            "r2r.examples.basic.app:app",
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


def test_upload_and_process_json(client):
    # Create a temporary JSON file
    json_data = {"key": "value"}
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as temp_json:
        json.dump(json_data, temp_json)
        temp_json_path = temp_json.name

    try:
        # Upload and process the JSON file
        metadata = {"tags": ["json", "test"]}
        document_id = generate_id_from_label("test_json")
        upload_json_response = client.upload_and_process_file(
            document_id, temp_json_path, metadata, None
        )

        assert "processed and saved" in upload_json_response["message"]

        # Perform a search on the uploaded JSON file
        search_response = client.search(
            "value",
            5,
            filters={"document_id": document_id},
        )

        assert len(search_response) > 0

    finally:
        # Delete the temporary JSON file
        os.unlink(temp_json_path)

        # Delete the uploaded document
        client.filtered_deletion("document_id", document_id)


def test_upload_and_process_html(client):
    # Create a temporary HTML file
    html_content = (
        "<html><body><h1>Test HTML</h1><p>This is a test.</p></body></html>"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False
    ) as temp_html:
        temp_html.write(html_content)
        temp_html_path = temp_html.name

    try:
        # Upload and process the HTML file
        metadata = {"tags": ["html", "test"]}
        document_id = generate_id_from_label("test_html")
        upload_html_response = client.upload_and_process_file(
            document_id, temp_html_path, metadata, None
        )

        assert "processed and saved" in upload_html_response["message"]

        # Perform a search on the uploaded HTML file
        search_response = client.search(
            "test",
            5,
            filters={"document_id": document_id},
        )

        assert len(search_response) > 0

    finally:
        # Delete the temporary HTML file
        os.unlink(temp_html_path)

        # Delete the uploaded document
        client.filtered_deletion("document_id", document_id)


# TODO - Modify these so that they work deterministically
# def test_search(client):
#     search_response = client.search("test", 5)
#     assert len(search_response) > 0

# def test_filtered_search(client):
#     filtered_search_response = client.search(
#         "test", 5, filters={"tags": "bulk"}
#     )
#     assert len(filtered_search_response) > 0
#     for result in filtered_search_response:
#         assert "bulk" in result["metadata"]["tags"]

# def test_filtered_deletion(client):
#     document_id = generate_id_from_label("doc 2")
#     response = client.filtered_deletion("document_id", document_id)
#     assert response["deleted"] == 1

#     post_deletion_filtered_search_response = client.search(
#         "test", 5, filters={"tags": "bulk"}
#     )
#     assert len(post_deletion_filtered_search_response) == 0


def test_upload_and_process_pdf(client):
    current_file_directory = os.path.dirname(os.path.realpath(__file__))
    file_path = os.path.join(current_file_directory, "test.pdf")

    metadata = {"tags": ["example", "test"]}
    document_id = generate_id_from_label("pdf 1")
    upload_pdf_response = client.upload_and_process_file(
        document_id, file_path, metadata, None
    )
    assert "processed and saved" in upload_pdf_response["message"]

    pdf_filtered_search_response = client.search(
        "what is a cool physics equation?",
        5,
        filters={"document_id": document_id},
    )
    assert len(pdf_filtered_search_response) > 0


def test_rag_completion(client):
    document_id = generate_id_from_label("pdf 1")
    rag_response = client.rag_completion(
        "Are there any test documents?",
        5,
        filters={"document_id": document_id},
    )
    assert rag_response  # Add your own assertions here based on the expected response


@pytest.mark.skip(
    reason="RAG streaming functionality is commented out in the original file"
)
def test_stream_rag_completion(client):
    document_id = generate_id_from_label("pdf 1")

    async def stream_rag_completion():
        async for chunk in client.stream_rag_completion(
            "Are there any test documents?",
            5,
            filters={"document_id": document_id},
            generation_config={"stream": True},
        ):
            assert chunk  # Add your own assertions here based on the expected chunks

    asyncio.run(stream_rag_completion())


def test_get_logs(client):
    logs_response = client.get_logs()
    assert logs_response  # Add your own assertions here based on the expected logs


def test_get_logs_summary(client):
    logs_summary_response = client.get_logs_summary()
    assert logs_summary_response  # Add your own assertions here based on the expected logs summary
