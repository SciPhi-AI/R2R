"""
Tests document ingestion functionality in R2R across all supported file types and modes.

Supported file types include:
- Documents: .doc, .docx, .odt, .pdf, .rtf, .txt
- Presentations: .ppt, .pptx
- Spreadsheets: .csv, .tsv, .xls, .xlsx
- Markup: .html, .md, .org, .rst
- Images: .bmp, .heic, .jpeg, .jpg, .png, .tiff
- Email: .eml, .msg, .p7s
- Other: .epub, .json

Tests verify:
- Basic ingestion for each file type
- Hi-res ingestion for complex documents
- Custom ingestion configurations
- Raw text ingestion
- Pre-processed chunk ingestion
- Metadata handling
"""

import time
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

import pytest

from r2r import R2RClient, R2RException


def file_ingestion(
    client: R2RClient,
    file_path: str,
    ingestion_mode: Optional[str] = None,
    expected_status: str = "success",
    expected_chunk_count: Optional[int] = None,
    ingestion_config: Optional[dict] = None,
    metadata: Optional[dict] = None,
    cleanup: bool = True,
    wait_for_completion: bool = True,
    timeout: int = 600,
) -> UUID:
    """
    Test ingestion of a file with the given parameters.

    Args:
        client: R2RClient instance
        file_path: Path to the file to ingest
        ingestion_mode: Optional ingestion mode ("fast", "hi-res", or None for default)
        expected_status: Expected final status of the document
        expected_chunk_count: Optional number of chunks to expect
        cleanup: Whether to delete the document after testing
        wait_for_completion: Whether to wait for ingestion to complete
        timeout: Maximum time to wait for ingestion completion in seconds

    Returns:
        dict: Document details after ingestion

    Raises:
        AssertionError: If any checks fail
        TimeoutError: If ingestion doesn't complete within timeout period
    """
    doc_id = None
    try:
        # Verify file exists
        assert Path(file_path).exists(), f"Test file not found: {file_path}"

        # Start ingestion
        ingest_args: dict[str, Any] = {"file_path": file_path}
        if ingestion_mode:
            ingest_args["ingestion_mode"] = ingestion_mode
        if ingestion_config:
            ingest_args["ingestion_config"] = ingestion_config
        if metadata:
            ingest_args["metadata"] = metadata

        ingestion_response = client.documents.create(**ingest_args)

        assert ingestion_response is not None
        assert "results" in ingestion_response
        assert "document_id" in ingestion_response["results"]

        doc_id = ingestion_response["results"]["document_id"]

        if wait_for_completion:
            time.sleep(2)

            start_time = time.time()
            while True:
                try:
                    retrieval_response = client.documents.retrieve(id=doc_id)
                    ingestion_status = retrieval_response["results"][
                        "ingestion_status"
                    ]

                    if ingestion_status == expected_status:
                        break
                    elif ingestion_status == "failed":
                        raise AssertionError(
                            f"Document ingestion failed: {retrieval_response}"
                        )

                except R2RException as e:
                    if e.status_code == 404:
                        # Document not yet available, continue polling if within timeout
                        if time.time() - start_time > timeout:
                            raise TimeoutError(
                                f"Ingestion didn't complete within {timeout} seconds"
                            )
                    else:
                        # Re-raise other errors
                        raise

                time.sleep(2)

    finally:
        if cleanup and doc_id is not None:
            try:
                client.documents.delete(id=doc_id)
            except R2RException:
                # Ignore cleanup errors
                pass
        return doc_id


@pytest.fixture(scope="session")
def config():
    class TestConfig:
        base_url = "http://localhost:7272"
        superuser_email = "admin@example.com"
        superuser_password = "change_me_immediately"

    return TestConfig()


@pytest.fixture(scope="session")
def client(config):
    """Create a client instance and log in as a superuser."""
    client = R2RClient(config.base_url)
    client.users.login(config.superuser_email, config.superuser_password)
    return client


@pytest.mark.parametrize(
    "file_type,file_path",
    [
        ("bmp", "core/examples/supported_file_types/bmp.bmp"),
        ("csv", "core/examples/supported_file_types/csv.csv"),
        ("doc", "core/examples/supported_file_types/doc.doc"),
        ("docx", "core/examples/supported_file_types/docx.docx"),
        ("eml", "core/examples/supported_file_types/eml.eml"),
        ("epub", "core/examples/supported_file_types/epub.epub"),
        ("heic", "core/examples/supported_file_types/heic.heic"),
        ("html", "core/examples/supported_file_types/html.html"),
        ("json", "core/examples/supported_file_types/json.json"),
        ("jpeg", "core/examples/supported_file_types/jpeg.jpeg"),
        ("jpg", "core/examples/supported_file_types/jpg.jpg"),
        ("md", "core/examples/supported_file_types/md.md"),
        ("msg", "core/examples/supported_file_types/msg.msg"),
        ("odt", "core/examples/supported_file_types/odt.odt"),
        ("org", "core/examples/supported_file_types/org.org"),
        ("p7s", "core/examples/supported_file_types/p7s.p7s"),
        ("pdf", "core/examples/supported_file_types/pdf.pdf"),
        ("png", "core/examples/supported_file_types/png.png"),
        ("ppt", "core/examples/supported_file_types/ppt.ppt"),
        ("pptx", "core/examples/supported_file_types/pptx.pptx"),
        ("rst", "core/examples/supported_file_types/rst.rst"),
        ("rtf", "core/examples/supported_file_types/rtf.rtf"),
        ("tiff", "core/examples/supported_file_types/tiff.tiff"),
        ("txt", "core/examples/supported_file_types/txt.txt"),
        ("tsv", "core/examples/supported_file_types/tsv.tsv"),
        ("xls", "core/examples/supported_file_types/xls.xls"),
        ("xlsx", "core/examples/supported_file_types/xlsx.xlsx"),
    ],
)
def test_file_type_ingestion(
    client: R2RClient, file_type: str, file_path: str
):
    """Test ingestion of specific file type."""

    try:
        result = file_ingestion(
            client=client,
            file_path=file_path,
            cleanup=True,
            wait_for_completion=True,
        )

        assert result is not None

    except Exception as e:
        raise


@pytest.mark.parametrize(
    "file_type,file_path",
    [
        ("pdf", "core/examples/supported_file_types/pdf.pdf"),
        ("docx", "core/examples/supported_file_types/docx.docx"),
        ("pptx", "core/examples/supported_file_types/pptx.pptx"),
    ],
)
def test_hires_ingestion(client: R2RClient, file_type: str, file_path: str):
    """Test hi-res ingestion with complex documents containing mixed content."""
    if file_type == "pdf":
        try:
            result = file_ingestion(
                client=client,
                file_path=file_path,
                ingestion_mode="hi-res",
                cleanup=True,
                wait_for_completion=True,
            )
            assert result is not None
        except Exception as e:  # Changed from R2RException to Exception
            if "PDF processing requires Poppler to be installed" in str(e):
                pytest.skip(
                    "Skipping PDF test due to missing Poppler dependency"
                )
            raise
    else:
        result = file_ingestion(
            client=client,
            file_path=file_path,
            ingestion_mode="hi-res",
            cleanup=True,
            wait_for_completion=True,
        )
        assert result is not None


def test_custom_ingestion_config(client: R2RClient):
    """Test ingestion with custom configuration parameters."""
    custom_config = {
        "provider": "r2r",
        "strategy": "auto",
        # "chunking_strategy": "by_title", Fixme: This was not implemented in the ingestion config
        "new_after_n_chars": 256,
        "max_characters": 512,
        "combine_under_n_chars": 64,
        "overlap": 100,
    }

    try:
        result = file_ingestion(
            client=client,
            file_path="core/examples/supported_file_types/pdf.pdf",
            ingestion_mode="custom",
            ingestion_config=custom_config,
            cleanup=True,
            wait_for_completion=True,
        )
        assert result is not None
    except Exception as e:
        raise


def test_raw_text_ingestion(client: R2RClient):
    """Test ingestion of raw text content."""
    text_content = "This is a test document.\nIt has multiple lines.\nTesting raw text ingestion."

    response = client.documents.create(
        raw_text=text_content, ingestion_mode="fast"
    )

    assert response is not None
    assert "results" in response
    assert "document_id" in response["results"]

    doc_id = response["results"]["document_id"]

    start_time = time.time()
    while True:
        try:
            retrieval_response = client.documents.retrieve(id=doc_id)
            if retrieval_response["results"]["ingestion_status"] == "success":
                break
        except R2RException as e:
            if time.time() - start_time > 600:
                raise TimeoutError("Ingestion didn't complete within timeout")
            time.sleep(2)

    client.documents.delete(id=doc_id)


def test_chunks_ingestion(client: R2RClient):
    """Test ingestion of pre-processed chunks."""
    chunks = ["This is chunk 1", "This is chunk 2", "This is chunk 3"]

    response = client.documents.create(chunks=chunks, ingestion_mode="fast")

    assert response is not None
    assert "results" in response
    assert "document_id" in response["results"]

    client.documents.delete(id=response["results"]["document_id"])


def test_metadata_handling(client: R2RClient):
    """Test ingestion with metadata."""
    metadata = {
        "title": "Test Document",
        "author": "Test Author",
        "custom_field": "custom_value",
    }

    try:
        doc_id = file_ingestion(
            client=client,
            file_path="core/examples/supported_file_types/pdf.pdf",
            ingestion_mode="fast",
            metadata=metadata,
            cleanup=False,
            wait_for_completion=True,
        )

        # Update metadata with server assigned version
        metadata["version"] = "v0"

        # Verify metadata
        doc = client.documents.retrieve(id=doc_id)
        assert doc["results"]["metadata"] == metadata

        # Cleanup
        client.documents.delete(id=doc_id)
    except Exception as e:
        raise
