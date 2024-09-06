import asyncio
import io
import logging
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import UploadFile

from core import R2RAgents
from core.base import (
    Document,
    DocumentInfo,
    R2RDocumentProcessingError,
    R2RException,
    RunManager,
    UserResponse,
    generate_id_from_label,
)
from core.main import R2RPipelines, R2RProviders
from core.main.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session", autouse=True)
def event_loop_policy():
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="function", autouse=True)
async def cleanup_tasks():
    yield
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)


@pytest.fixture
def mock_vector_db():
    mock_db = MagicMock()
    mock_db.relational = MagicMock()
    mock_db.relational.get_documents_overview.return_value = (
        []
    )  # Default to empty list
    return mock_db


@pytest.fixture
def mock_embedding_model():
    return Mock()


@pytest.fixture
def mock_pipes():
    pipes = Mock()
    pipes.parsing_pipe = AsyncMock()
    pipes.chunking_pipe = AsyncMock()
    pipes.embedding_pipe = AsyncMock()
    pipes.vector_storage_pipe = AsyncMock()
    return pipes


@pytest.fixture
def ingestion_service(mock_vector_db, mock_embedding_model, mock_pipes):
    config = MagicMock()
    config.app.get.return_value = 32  # Default max file size
    providers = Mock(spec=R2RProviders)
    providers.database = mock_vector_db
    providers.embedding_model = mock_embedding_model
    pipelines = Mock(spec=R2RPipelines)
    pipelines.ingestion_pipeline = AsyncMock()
    pipelines.ingestion_pipeline.run.return_value = {
        "embedding_pipeline_output": []
    }
    run_manager = RunManager(logger)
    logging_connection = Mock()
    agents = Mock(spec=R2RAgents)

    return IngestionService(
        config,
        providers,
        mock_pipes,
        pipelines,
        agents,
        run_manager,
        logging_connection=logging_connection,
    )


@pytest.mark.asyncio
async def test_ingest_single_document(
    ingestion_service, mock_vector_db, mock_pipes
):
    document = Document(
        id=generate_id_from_label("test_id"),
        group_ids=[],
        user_id=generate_id_from_label("user_1"),
        type="txt",
        data="Test content",
        metadata={},
    )

    mock_pipes.parsing_pipe.run.return_value = [{"content": "Test content"}]
    mock_pipes.chunking_pipe.run.return_value = [{"chunk": "Test content"}]
    mock_pipes.embedding_pipe.run.return_value = [
        {"embedding": [0.1, 0.2, 0.3]}
    ]
    mock_pipes.vector_storage_pipe.run.return_value = ["stored_id"]

    ingestion_service.pipelines.ingestion_pipeline.run.return_value = {
        "embedding_pipeline_output": [(document.id, None)]
    }
    mock_vector_db.relational.get_documents_overview.return_value = (
        []
    )  # No existing documents

    result = await ingestion_service.ingest_documents([document])

    assert result["processed_documents"][0].id == generate_id_from_label(
        "test_id"
    )
    assert not result["failed_documents"]
    assert not result["skipped_documents"]

    mock_pipes.parsing_pipe.run.assert_called_once()
    mock_pipes.chunking_pipe.run.assert_called_once()
    mock_pipes.embedding_pipe.run.assert_called_once()
    mock_pipes.vector_storage_pipe.run.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_duplicate_document(ingestion_service, mock_vector_db):
    document = Document(
        id=generate_id_from_label("test_id"),
        group_ids=[],
        user_id=generate_id_from_label("user_1"),
        type="txt",
        metadata={},
    )
    mock_vector_db.relational.get_documents_overview.return_value = [
        DocumentInfo(
            id=document.id,
            group_ids=[],
            user_id=generate_id_from_label("user_1"),
            version="v0",
            size_in_bytes=1024,
            metadata={},
            title=str(document.id),
            type="txt",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            ingestion_status="success",
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

    user = UserResponse(
        id=generate_id_from_label("user1"),
        email="email@test.com",
        hashed_password="password",
    )
    ingestion_service.pipelines.ingestion_pipeline.run.return_value = {
        "embedding_pipeline_output": [
            (generate_id_from_label(f"test.txt-{user.id}"), None)
        ]
    }

    result = await ingestion_service.ingest_files([file_mock], user=user)

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
            group_ids=[],
            user_id=generate_id_from_label("user_1"),
            type="txt",
            metadata={},
        ),
        Document(
            id=generate_id_from_label("failure_id"),
            data="Failure content",
            type="txt",
            group_ids=[],
            user_id=generate_id_from_label("user_1"),
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
    assert documents[0].id in [doc.id for doc in result["processed_documents"]]
    assert documents[1].id in [
        doc["document_id"] for doc in result["failed_documents"]
    ]
    assert "Embedding failed" in str(result["failed_documents"][0]["result"])

    assert mock_vector_db.relational.upsert_documents_overview.call_count == 2
    upserted_docs = (
        mock_vector_db.relational.upsert_documents_overview.call_args[0][0]
    )
    assert len(upserted_docs) == 2
    assert upserted_docs[0].id == documents[0].id
    assert upserted_docs[0].ingestion_status == "success"
    assert upserted_docs[1].id == documents[1].id
    assert upserted_docs[1].ingestion_status == "failure"


@pytest.mark.asyncio
async def test_ingest_unsupported_file_type(ingestion_service):
    file_mock = UploadFile(
        filename="test.unsupported", file=io.BytesIO(b"Test content")
    )
    file_mock.file.seek(0)
    file_mock.size = 12  # Set file size manually

    user = UserResponse(
        id=generate_id_from_label("user1"),
        email="email@test.com",
        hashed_password="password",
    )

    with pytest.raises(R2RException) as exc_info:
        await ingestion_service.ingest_files([file_mock], user=user)

    assert "is not a valid DocumentType" in str(exc_info.value)


@pytest.mark.asyncio
async def test_partial_ingestion_success(ingestion_service, mock_vector_db):
    documents = [
        Document(
            id=generate_id_from_label("success_1"),
            data="Success content 1",
            group_ids=[],
            user_id=generate_id_from_label("user_1"),
            type="txt",
            metadata={},
        ),
        Document(
            id=generate_id_from_label("fail"),
            data="Fail content",
            group_ids=[],
            user_id=generate_id_from_label("user_1"),
            type="txt",
            metadata={},
        ),
        Document(
            id=generate_id_from_label("success_2"),
            data="Success content 2",
            group_ids=[],
            user_id=generate_id_from_label("user_1"),
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
    assert documents[1].id in [
        doc["document_id"] for doc in result["failed_documents"]
    ]


@pytest.mark.asyncio
async def test_version_increment(ingestion_service, mock_vector_db):

    user = UserResponse(
        id=generate_id_from_label("user1"),
        email="email@test.com",
        hashed_password="password",
    )

    document = Document(
        id=generate_id_from_label("test_id"),
        data="Test content",
        group_ids=[],
        user_id=generate_id_from_label("user_1"),
        type="txt",
        metadata={},
    )
    mock_vector_db.relational.get_documents_overview.return_value = [
        DocumentInfo(
            id=document.id,
            group_ids=[],
            user_id=generate_id_from_label("user_1"),
            type="txt",
            version="v2",
            ingestion_status="success",
            size_in_bytes=0,
            metadata={},
        )
    ]

    file_mock = UploadFile(
        filename="test.txt", file=io.BytesIO(b"Updated content")
    )
    await ingestion_service.update_files(
        files=[file_mock], document_ids=[document.id], user=user
    )

    calls = mock_vector_db.relational.upsert_documents_overview.call_args_list
    assert len(calls) == 2
    assert calls[1][0][0][0].version == "v3"


@pytest.mark.asyncio
async def test_process_ingestion_results_error_handling(ingestion_service):
    document_infos = [
        DocumentInfo(
            id=uuid.uuid4(),
            group_ids=[],
            user_id=generate_id_from_label("user_1"),
            type="txt",
            version="v0",
            ingestion_status="processing",
            size_in_bytes=0,
            metadata={},
        )
    ]
    ingestion_results = {
        "embedding_pipeline_output": [
            (
                document_infos[0].id,
                R2RDocumentProcessingError(
                    "Unexpected error",
                    document_id=document_infos[0].id,
                ),
            )
        ]
    }

    result = await ingestion_service._process_ingestion_results(
        ingestion_results,
        document_infos,
        [],
    )

    assert len(result["failed_documents"]) == 1
    assert "Unexpected error" in str(result["failed_documents"][0])


@pytest.mark.asyncio
async def test_document_status_update_after_ingestion(
    ingestion_service, mock_vector_db
):
    document = Document(
        id=generate_id_from_label("test_id"),
        data="Test content",
        group_ids=[],
        user_id=generate_id_from_label("user_1"),
        type="txt",
        metadata={},
    )

    ingestion_service.pipelines.ingestion_pipeline.run.return_value = {
        "embedding_pipeline_output": [(document.id, None)]
    }
    mock_vector_db.relational.get_documents_overview.return_value = (
        []
    )  # No existing documents

    await ingestion_service.ingest_documents([document])

    # Check that upsert_documents_overview was called twice
    assert mock_vector_db.relational.upsert_documents_overview.call_count == 2

    # Check the second call to upsert_documents_overview (status update)
    second_call_args = (
        mock_vector_db.relational.upsert_documents_overview.call_args_list[1][
            0
        ][0]
    )
    assert len(second_call_args) == 1
    assert second_call_args[0].id == document.id
    assert second_call_args[0].ingestion_status == "success"
