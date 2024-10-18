# tests//conftest.py
import os
import random
import uuid
from uuid import UUID

import pytest

from core import (
    AppConfig,
    AuthConfig,
    BCryptConfig,
    CompletionConfig,
    DatabaseConfig,
    EmbeddingConfig,
    KGConfig,
    FileConfig,
    LoggingConfig,
    PromptConfig,
    SqlitePersistentLoggingProvider,
    Vector,
    VectorEntry,
)

from core.base import (
    DocumentInfo,
    DocumentType,
    IngestionStatus,
    KGEnrichmentStatus,
    KGExtractionStatus,
)

from core.providers import (
    BCryptProvider,
    LiteCompletionProvider,
    LiteLLMEmbeddingProvider,
    PostgresDBProvider,
    PostgresFileProvider,
    R2RAuthProvider,
    R2RPromptProvider,
    PostgresKGProvider,
)

from shared.abstractions.vector import VectorQuantizationType


# Vectors
@pytest.fixture(scope="function")
def dimension():
    return 128


@pytest.fixture(scope="function")
def num_entries():
    return 100


@pytest.fixture(scope="function")
def sample_entries(dimension, num_entries):
    def generate_random_vector_entry(
        id_value: int, dimension: int
    ) -> VectorEntry:
        vector_data = [random.random() for _ in range(dimension)]
        metadata = {"key": f"value_id_{id_value}", "raw_key": id_value}
        return VectorEntry(
            extraction_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            collection_ids=[uuid.uuid4()],
            vector=Vector(data=vector_data),
            text=f"Sample text for id_{id_value}",
            metadata=metadata,
        )

    return [
        generate_random_vector_entry(i, dimension) for i in range(num_entries)
    ]


@pytest.fixture(scope="function")
def app_config():
    collection_id = uuid.uuid4()

    random_project_name = f"a_{collection_id.hex}_test_project"

    return AppConfig(project_name=random_project_name)


# Crypto
@pytest.fixture(scope="function")
def crypto_config(app_config):
    return BCryptConfig(app=app_config)


@pytest.fixture(scope="function")
def crypto_provider(crypto_config, app_config):
    return BCryptProvider(crypto_config)


# Postgres
@pytest.fixture(scope="function")
def db_config(app_config):
    return DatabaseConfig.create(provider="postgres", app=app_config)


@pytest.fixture(scope="function")
async def postgres_db_provider(
    db_config, dimension, crypto_provider, sample_entries, app_config
):
    db = PostgresDBProvider(
        db_config, dimension=dimension, crypto_provider=crypto_provider
    )
    await db.initialize()
    db.vector.upsert_entries(sample_entries)
    yield db
    # Teardown
    # TODO - Add teardown methods
    # await db.delete_project(db.project_name)


@pytest.fixture(scope="function")
def db_config_temporary(app_config):
    collection_id = uuid.uuid4()

    random_project_name = f"test_collection_{collection_id.hex}"
    return DatabaseConfig.create(
        provider="postgres", project_name=random_project_name, app=app_config
    )


@pytest.fixture(scope="function")
async def temporary_postgres_db_provider(
    db_config_temporary, dimension, crypto_provider, sample_entries
):
    db = PostgresDBProvider(
        db_config_temporary,
        dimension=dimension,
        crypto_provider=crypto_provider,
    )
    await db.initialize()
    db.vector.upsert_entries(sample_entries)
    try:
        yield db
    finally:
        await db.relational.close()
        db.vector.close()


# Auth
@pytest.fixture(scope="function")
def auth_config(app_config):
    return AuthConfig(
        secret_key="test_secret_key",
        access_token_lifetime_in_minutes=15,
        refresh_token_lifetime_in_days=1,
        require_email_verification=False,
        app=app_config,
    )


@pytest.fixture(scope="function")
async def r2r_auth_provider(
    auth_config, crypto_provider, temporary_postgres_db_provider
):
    auth_provider = R2RAuthProvider(
        auth_config, crypto_provider, temporary_postgres_db_provider
    )
    await auth_provider.initialize()
    yield auth_provider


# Embeddings
@pytest.fixture
def litellm_provider(app_config):
    config = EmbeddingConfig(
        provider="litellm",
        base_model="text-embedding-3-small",
        base_dimension=1536,
        app=app_config,
    )
    return LiteLLMEmbeddingProvider(config)


# File Provider
@pytest.fixture(scope="function")
def file_config(app_config):
    return FileConfig(provider="postgres", app=app_config)


@pytest.fixture(scope="function")
async def postgres_file_provider(file_config, temporary_postgres_db_provider):
    file_provider = PostgresFileProvider(
        file_config, temporary_postgres_db_provider
    )
    await file_provider.initialize()
    yield file_provider
    await file_provider._close_connection()


# LLM provider
@pytest.fixture
def litellm_completion_provider(app_config):
    config = CompletionConfig(provider="litellm", app=app_config)
    return LiteCompletionProvider(config)


# Logging
@pytest.fixture(scope="function")
async def local_logging_provider(app_config):
    unique_id = str(uuid.uuid4())
    logging_path = f"test_{unique_id}.sqlite"
    provider = SqlitePersistentLoggingProvider(
        LoggingConfig(logging_path=logging_path, app=app_config)
    )
    await provider._init()
    yield provider
    await provider.close()
    if os.path.exists(logging_path):
        os.remove(logging_path)


@pytest.fixture(scope="function")
def kg_config_temporary(app_config):
    return KGConfig(provider="postgres", app=app_config)


# KG


@pytest.fixture(scope="function")
def embedding_dimension():
    return 128


@pytest.fixture(scope="function")
def vector_quantization_type():
    return VectorQuantizationType.FP32


@pytest.fixture(scope="function")
async def postgres_kg_provider(
    kg_config_temporary,
    temporary_postgres_db_provider,
    litellm_provider,
    embedding_dimension,
    vector_quantization_type,
):

    # upsert into documents_overview
    document_info = DocumentInfo(
        id=UUID("9fbe403b-c11c-5aae-8ade-ef22980c3ad1"),
        collection_ids=[UUID("122fdf6a-e116-546b-a8f6-e4cb2e2c0a09")],
        user_id=UUID("00000000-0000-0000-0000-000000000003"),
        type=DocumentType.PDF,
        metadata={},
        title="Test Document for KG",
        version="1.0",
        size_in_bytes=1024,
        ingestion_status=IngestionStatus.PENDING,
        kg_extraction_status=KGExtractionStatus.PENDING,
    )

    await temporary_postgres_db_provider.relational.upsert_documents_overview(
        document_info
    )

    kg_provider = PostgresKGProvider(
        kg_config_temporary, temporary_postgres_db_provider, litellm_provider
    )
    await kg_provider.create_tables(
        embedding_dimension, vector_quantization_type
    )
    yield kg_provider


@pytest.fixture(scope="function")
def prompt_config(app_config):
    return PromptConfig(provider="r2r", app=app_config)


@pytest.fixture(scope="function")
async def r2r_prompt_provider(prompt_config, temporary_postgres_db_provider):
    prompt_provider = R2RPromptProvider(
        prompt_config, temporary_postgres_db_provider
    )
    await prompt_provider.initialize()
    yield prompt_provider
