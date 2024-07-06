import io
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import UploadFile

from r2r.base import (
    Document,
    DocumentInfo,
    R2RDocumentProcessingError,
    R2RException,
    generate_id_from_label,
)
from r2r.main import R2RPipelines, R2RProviders
from r2r.main.services.ingestion_service import IngestionService


@pytest.fixture
def mock_vector_db():
    mock_db = MagicMock()
    mock_db.get_documents_overview.return_value = []  # Default to empty list
    return mock_db


@pytest.fixture
def mock_embedding_model():
    return Mock()


@pytest.fixture
def ingestion_service(mock_vector_db, mock_embedding_model):
    config = MagicMock()
    config.app.get.return_value = 32  # Default max file size
    providers = Mock(spec=R2RProviders)
    providers.vector_db = mock_vector_db
    providers.embedding_model = mock_embedding_model
    pipelines = Mock(spec=R2RPipelines)
    pipelines.ingestion_pipeline = AsyncMock()
    pipelines.ingestion_pipeline.run.return_value = {
        "embedding_pipeline_output": []
    }
    run_manager = Mock()
    logging_connection = Mock()

    service = IngestionService(
        config, providers, pipelines, run_manager, logging_connection
    )
    return service


@pytest.mark.asyncio
async def test_ingest_single_document(ingestion_service, mock_vector_db):
    document = Document(
        id=generate_id_from_label("test_id"),
        data="Test content",
        type="txt",
        metadata={},
    )

    ingestion_service.pipelines.ingestion_pipeline.run.return_value = {
        "embedding_pipeline_output": [(document.id, None)]
    }
    mock_vector_db.get_documents_overview.return_value = (
        []
    )  # No existing documents

    result = await ingestion_service.ingest_documents([document])

    assert result["processed_documents"] == [
        f"Document '{document.id}' processed successfully."
    ]
    assert not result["failed_documents"]
    assert not result["skipped_documents"]


@pytest.mark.asyncio
async def test_ingest_duplicate_document(ingestion_service, mock_vector_db):
    document = Document(
        id=generate_id_from_label("test_id"),
        data="Test content",
        type="txt",
        metadata={},
    )
    mock_vector_db.get_documents_overview.return_value = [
        DocumentInfo(
            document_id=document.id,
            version="v0",
            size_in_bytes=len(document.data),
            metadata={},
            title=str(document.id),
            user_id=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            status="success",
        )
    ]

    with pytest.raises(R2RException) as exc_info:
        await ingestion_service.ingest_documents([document])

    assert (
        f"Document with ID {document.id} was already successfully processed"
        in str(exc_info.value)
    )


@pytest.mark.asyncio
async def test_ingest_file(ingestion_service):
    file_content = b"Test content"
    file_mock = UploadFile(filename="test.txt", file=io.BytesIO(file_content))
    file_mock.file.seek(0)
    file_mock.size = len(file_content)  # Set file size manually

    ingestion_service.pipelines.ingestion_pipeline.run.return_value = {
        "embedding_pipeline_output": [
            (generate_id_from_label("test.txt"), None)
        ]
    }

    result = await ingestion_service.ingest_files([file_mock])

    assert len(result["processed_documents"]) == 1
    assert not result["failed_documents"]
    assert not result["skipped_documents"]


@pytest.mark.asyncio
async def test_ingest_mixed_success_and_failure(
    ingestion_service, mock_vector_db
):
    documents = [
        Document(
            id=generate_id_from_label("success_id"),
            data="Success content",
            type="txt",
            metadata={},
        ),
        Document(
            id=generate_id_from_label("failure_id"),
            data="Failure content",
            type="txt",
            metadata={},
        ),
    ]

    ingestion_service.pipelines.ingestion_pipeline.run.return_value = {
        "embedding_pipeline_output": [
            (
                documents[0].id,
                f"Processed 1 vectors for document {documents[0].id}.",
            ),
            (
                documents[1].id,
                R2RDocumentProcessingError(
                    error_message="Embedding failed",
                    document_id=documents[1].id,
                ),
            ),
        ]
    }

    result = await ingestion_service.ingest_documents(documents)

    assert len(result["processed_documents"]) == 1
    assert len(result["failed_documents"]) == 1
    assert str(documents[0].id) in result["processed_documents"][0]
    assert str(documents[1].id) in result["failed_documents"][0]
    assert "Embedding failed" in result["failed_documents"][0]

    assert mock_vector_db.upsert_documents_overview.call_count == 2
    upserted_docs = mock_vector_db.upsert_documents_overview.call_args[0][0]
    assert len(upserted_docs) == 2
    assert upserted_docs[0].document_id == documents[0].id
    assert upserted_docs[0].status == "success"
    assert upserted_docs[1].document_id == documents[1].id
    assert upserted_docs[1].status == "failure"


@pytest.mark.asyncio
async def test_ingest_unsupported_file_type(ingestion_service):
    file_mock = UploadFile(
        filename="test.unsupported", file=io.BytesIO(b"Test content")
    )
    file_mock.file.seek(0)
    file_mock.size = 12  # Set file size manually

    with pytest.raises(R2RException) as exc_info:
        await ingestion_service.ingest_files([file_mock])

    assert "is not a valid DocumentType" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ingest_large_file(ingestion_service):
    large_content = b"Large content" * 1000000  # 12MB content
    file_mock = UploadFile(
        filename="large_file.txt", file=io.BytesIO(large_content)
    )
    file_mock.file.seek(0)
    file_mock.size = len(large_content)  # Set file size manually

    ingestion_service.config.app.get.return_value = (
        10  # Set max file size to 10MB
    )

    with pytest.raises(R2RException) as exc_info:
        await ingestion_service.ingest_files([file_mock])

    assert "File size exceeds maximum allowed size" in str(exc_info.value)


# @pytest.mark.asyncio
# async def test_concurrent_ingestion(ingestion_service, mock_vector_db):
#     document = Document(id=generate_id_from_label("test_id"), data="Test content", type="txt", metadata={})

#     async def ingestion_task():
#         return await ingestion_service.ingest_documents([document])

#     # Simulate concurrent ingestion attempts
#     results = await asyncio.gather(ingestion_task(), ingestion_task(), ingestion_task())

#     # Check that only one ingestion succeeded and others were skipped
#     assert sum(len(r["processed_documents"]) for r in results) == 1
#     assert sum(len(r["skipped_documents"]) for r in results) == 2


@pytest.mark.asyncio
async def test_partial_ingestion_success(ingestion_service, mock_vector_db):
    documents = [
        Document(
            id=generate_id_from_label("success_1"),
            data="Success content 1",
            type="txt",
            metadata={},
        ),
        Document(
            id=generate_id_from_label("fail"),
            data="Fail content",
            type="txt",
            metadata={},
        ),
        Document(
            id=generate_id_from_label("success_2"),
            data="Success content 2",
            type="txt",
            metadata={},
        ),
    ]

    ingestion_service.pipelines.ingestion_pipeline.run.return_value = {
        "embedding_pipeline_output": [
            (documents[0].id, None),
            (
                documents[1].id,
                R2RDocumentProcessingError(
                    error_message="Embedding failed",
                    document_id=documents[1].id,
                ),
            ),
            (documents[2].id, None),
        ]
    }

    result = await ingestion_service.ingest_documents(documents)

    assert len(result["processed_documents"]) == 2
    assert len(result["failed_documents"]) == 1
    assert str(documents[1].id) in result["failed_documents"][0]


@pytest.mark.asyncio
async def test_version_increment(ingestion_service, mock_vector_db):
    document = Document(
        id=generate_id_from_label("test_id"),
        data="Test content",
        type="txt",
        metadata={},
    )
    mock_vector_db.get_documents_overview.return_value = [
        DocumentInfo(
            document_id=document.id,
            version="v2",
            status="success",
            size_in_bytes=0,
            metadata={},
        )
    ]

    file_mock = UploadFile(
        filename="test.txt", file=io.BytesIO(b"Updated content")
    )
    await ingestion_service.update_files([file_mock], [document.id])

    calls = mock_vector_db.upsert_documents_overview.call_args_list
    assert len(calls) == 2
    assert calls[1][0][0][0].version == "v3"


@pytest.mark.asyncio
async def test_process_ingestion_results_error_handling(ingestion_service):
    document_infos = [
        DocumentInfo(
            document_id=uuid.uuid4(),
            version="v0",
            status="processing",
            size_in_bytes=0,
            metadata={},
        )
    ]
    ingestion_results = {
        "embedding_pipeline_output": [
            (
                document_infos[0].document_id,
                R2RDocumentProcessingError(
                    "Unexpected error",
                    document_id=document_infos[0].document_id,
                ),
            )
        ]
    }

    result = ingestion_service._process_ingestion_results(
        ingestion_results,
        document_infos,
        [],
        {document_infos[0].document_id: "test"},
    )

    assert len(result["failed_documents"]) == 1
    assert "Unexpected error" in result["failed_documents"][0]


@pytest.mark.asyncio
async def test_file_size_limit_edge_cases(ingestion_service):
    ingestion_service.config.app.get.return_value = 1  # 1MB limit

    just_under_limit = b"x" * (1024 * 1024 - 1)
    at_limit = b"x" * (1024 * 1024)
    over_limit = b"x" * (1024 * 1024 + 1)

    file_under = UploadFile(
        filename="under.txt",
        file=io.BytesIO(just_under_limit),
        size=1024 * 1024 - 1,
    )
    file_at = UploadFile(
        filename="at.txt", file=io.BytesIO(at_limit), size=1024 * 1024
    )
    file_over = UploadFile(
        filename="over.txt", file=io.BytesIO(over_limit), size=1024 * 1024 + 1
    )

    await ingestion_service.ingest_files([file_under])  # Should succeed
    await ingestion_service.ingest_files([file_at])  # Should succeed

    with pytest.raises(
        R2RException, match="File size exceeds maximum allowed size"
    ):
        await ingestion_service.ingest_files([file_over])


@pytest.mark.asyncio
async def test_document_status_update_after_ingestion(
    ingestion_service, mock_vector_db
):
    document = Document(
        id=generate_id_from_label("test_id"),
        data="Test content",
        type="txt",
        metadata={},
    )

    ingestion_service.pipelines.ingestion_pipeline.run.return_value = {
        "embedding_pipeline_output": [(document.id, None)]
    }
    mock_vector_db.get_documents_overview.return_value = (
        []
    )  # No existing documents

    await ingestion_service.ingest_documents([document])

    # Check that upsert_documents_overview was called twice
    assert mock_vector_db.upsert_documents_overview.call_count == 2

    # Check the second call to upsert_documents_overview (status update)
    second_call_args = mock_vector_db.upsert_documents_overview.call_args_list[
        1
    ][0][0]
    assert len(second_call_args) == 1
    assert second_call_args[0].document_id == document.id
    assert second_call_args[0].status == "success"
