import pytest
from uuid import UUID
from datetime import datetime
from shared.api.models.auth.responses import UserResponse
from core.base import RawChunk, DocumentType, IngestionStatus, VectorEntry
from shared.abstractions.ingestion import (
    ChunkEnrichmentStrategy,
    ChunkEnrichmentSettings,
)
import subprocess
from core.main.services.ingestion_service import (
    IngestionService,
    IngestionConfig,
)
from core.main.abstractions import R2RProviders
from core.providers.orchestration import SimpleOrchestrationProvider
from core.providers.ingestion import R2RIngestionConfig, R2RIngestionProvider

from core.base import Vector, VectorType
import random


@pytest.fixture
def sample_document_id():
    return UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_user():
    return UserResponse(
        id=UUID("87654321-8765-4321-8765-432187654321"),
        email="test@example.com",
        is_superuser=True,
    )


@pytest.fixture
def collection_ids():
    return [UUID("12345678-1234-5678-1234-567812345678")]


@pytest.fixture
def extraction_ids():
    return [
        UUID("fce959df-46a2-4983-aa8b-dd1f93777e02"),
        UUID("9a85269c-84cd-4dff-bf21-7bd09974f668"),
        UUID("4b1199b2-2b96-4198-9ded-954c900a23dd"),
    ]


@pytest.fixture
def sample_chunks(
    sample_document_id, sample_user, collection_ids, extraction_ids
):
    return [
        VectorEntry(
            extraction_id=extraction_ids[0],
            document_id=sample_document_id,
            user_id=sample_user.id,
            collection_ids=collection_ids,
            vector=Vector(
                data=[random.random() for _ in range(128)],
                type=VectorType.FIXED,
                length=128,
            ),
            text="This is the first chunk of text.",
            metadata={"chunk_order": 0},
        ),
        VectorEntry(
            extraction_id=extraction_ids[1],
            document_id=sample_document_id,
            user_id=sample_user.id,
            collection_ids=collection_ids,
            vector=Vector(
                data=[random.random() for _ in range(128)],
                type=VectorType.FIXED,
                length=128,
            ),
            text="This is the second chunk with different content.",
            metadata={"chunk_order": 1},
        ),
        VectorEntry(
            extraction_id=extraction_ids[2],
            document_id=sample_document_id,
            user_id=sample_user.id,
            collection_ids=collection_ids,
            vector=Vector(
                data=[random.random() for _ in range(128)],
                type=VectorType.FIXED,
                length=128,
            ),
            text="And this is the third chunk with more information.",
            metadata={"chunk_order": 2},
        ),
    ]


@pytest.fixture
def enrichment_settings():
    return ChunkEnrichmentSettings(
        enable_chunk_enrichment=True,
        strategies=[
            ChunkEnrichmentStrategy.NEIGHBORHOOD,
            ChunkEnrichmentStrategy.SEMANTIC,
        ],
        backward_chunks=1,
        forward_chunks=1,
        semantic_neighbors=2,
        semantic_similarity_threshold=0.7,
    )


@pytest.fixture
def r2r_ingestion_provider(app_config):
    return R2RIngestionProvider(R2RIngestionConfig(app=app_config))


@pytest.fixture
def orchestration_provider(orchestration_config):
    return SimpleOrchestrationProvider(orchestration_config)


@pytest.fixture
def r2r_providers(
    r2r_ingestion_provider,
    r2r_prompt_provider,
    postgres_kg_provider,
    postgres_db_provider,
    litellm_provider_128,
    postgres_file_provider,
    r2r_auth_provider,
    litellm_completion_provider,
    orchestration_provider,
):
    return R2RProviders(
        ingestion=r2r_ingestion_provider,
        prompt=r2r_prompt_provider,
        kg=postgres_kg_provider,
        database=postgres_db_provider,
        embedding=litellm_provider_128,
        file=postgres_file_provider,
        auth=r2r_auth_provider,
        llm=litellm_completion_provider,
        orchestration=orchestration_provider,
    )


@pytest.fixture
def ingestion_config(app_config, enrichment_settings):
    return IngestionConfig(
        app=app_config, chunk_enrichment_settings=enrichment_settings
    )


@pytest.fixture
async def ingestion_service(r2r_providers, ingestion_config):
    # You'll need to mock your dependencies here
    service = IngestionService(
        providers=r2r_providers,
        config=ingestion_config,
        pipes=[],
        pipelines=[],
        agents=[],
        run_manager=None,
        logging_connection=None,
    )
    return service


async def test_chunk_enrichment_basic(
    sample_chunks, ingestion_service, sample_document_id, sample_user
):
    # Test basic chunk enrichment functionality

    # ingest chunks ingress. Just add document info to the table
    await ingestion_service.ingest_chunks_ingress(
        document_id=sample_document_id,
        chunks=sample_chunks,
        metadata={},
        user=sample_user,
    )

    # upsert entries
    await ingestion_service.providers.database.upsert_entries(sample_chunks)

    # enrich chunks
    await ingestion_service.chunk_enrichment(sample_document_id)

    # document chunks
    document_chunks = (
        await ingestion_service.providers.database.get_document_chunks(
            sample_document_id
        )
    )

    assert len(document_chunks["results"]) == len(sample_chunks)

    for document_chunk in document_chunks["results"]:
        assert (
            document_chunk["metadata"]["chunk_enrichment_status"] == "success"
        )
        assert (
            document_chunk["metadata"]["original_text"]
            == sample_chunks[document_chunk["metadata"]["chunk_order"]].text
        )


# Other tests
# TODO: Implement in services/test_ingestion_service.py

# test_enriched_chunk_content:
#     Ingests chunks, enriches them, then verifies each chunk in DB has metadata containing both 'original_text' and 'chunk_enrichment_status' (success/failed)

# test_neighborhood_strategy:
#     Tests _get_enriched_chunk_text() on middle chunk (idx 1) with NEIGHBORHOOD strategy to verify it incorporates text from chunks before/after it

# test_semantic_strategy:
#     Sets ChunkEnrichmentStrategy.SEMANTIC, ingests chunks, then enriches them using semantic similarity to find and incorporate related chunks' content

# test_error_handling:
#     Attempts chunk_enrichment() with non-existent UUID('00000000-0000-0000-0000-000000000000') to verify proper exception handling

# test_empty_chunks:
#     Attempts to ingest_chunks_ingress() with empty chunks list to verify it raises appropriate exception rather than processing empty data

# test_concurrent_processing:
#     Creates 200 RawChunks ("Chunk number {0-199}"), ingests and enriches them all to verify concurrent processing handles large batch correctly

# test_vector_storage:
#     Ingests chunks, enriches them, then verifies get_document_vectors() returns vectors with correct structure including vector data and extraction_id fields
