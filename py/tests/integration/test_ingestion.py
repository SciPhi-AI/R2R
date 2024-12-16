"""
Tests ingestion of all documents supported by R2R, including:

- .bmp
- .csv
- .doc
- .docx
- .eml
- .epub
- .heic
- .html
- .jpeg
- .jpg
- .json
- .md
- .msg
- .odt
- .org
- .p7s
- .pdf
- .png
- .ppt
- .pptx
- .rst
- .rtf
- .tiff
- .txt
- .tsv
- .xls
- .xlsx
"""

import time

import pytest

from r2r import R2RClient, R2RException

from pathlib import Path
from typing import Optional
import time


def file_ingestion(
    client: R2RClient,
    file_path: str,
    ingestion_mode: Optional[str] = None,
    expected_status: str = "success",
    expected_chunk_count: Optional[int] = None,
    cleanup: bool = True,
    wait_for_completion: bool = True,
    timeout: int = 600,
):
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
    try:
        # Verify file exists
        assert Path(file_path).exists(), f"Test file not found: {file_path}"

        # Start ingestion
        ingest_args = {"file_path": file_path}
        if ingestion_mode:
            ingest_args["ingestion_mode"] = ingestion_mode

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
