# tests/conftest.py
import os

import pytest

from core.base import AppConfig, DatabaseConfig, VectorQuantizationType
from core.providers import NaClCryptoConfig, NaClCryptoProvider
from core.providers.database.postgres import (
    PostgresChunksHandler,
    PostgresCollectionsHandler,
    PostgresConversationsHandler,
    PostgresDatabaseProvider,
    PostgresDocumentsHandler,
    PostgresGraphsHandler,
    PostgresLimitsHandler,
    PostgresPromptsHandler,
)
from core.providers.database.users import (  # Make sure this import is correct
    PostgresUserHandler, )

TEST_DB_CONNECTION_STRING = os.environ.get(
    "TEST_DB_CONNECTION_STRING",
    "postgresql://postgres:postgres@localhost:5432/test_db",
)


@pytest.fixture
async def db_provider():
    crypto_provider = NaClCryptoProvider(NaClCryptoConfig(app={}))
    db_config = DatabaseConfig(
        app=AppConfig(project_name="test_project"),
        provider="postgres",
        connection_string=TEST_DB_CONNECTION_STRING,
        postgres_configuration_settings={
            "max_connections": 10,
            "statement_cache_size": 100,
        },
        project_name="test_project",
    )

    dimension = 4
    quantization_type = VectorQuantizationType.FP32

    db_provider = PostgresDatabaseProvider(db_config, dimension,
                                           crypto_provider, quantization_type)

    await db_provider.initialize()
    yield db_provider
    # Teardown logic if needed
    await db_provider.close()


@pytest.fixture
def crypto_provider():
    # Provide a crypto provider fixture if needed separately
    return NaClCryptoProvider(NaClCryptoConfig(app={}))


@pytest.fixture
async def chunks_handler(db_provider):
    dimension = db_provider.dimension
    quantization_type = db_provider.quantization_type
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager

    handler = PostgresChunksHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        dimension=dimension,
        quantization_type=quantization_type,
    )
    await handler.create_tables()
    return handler


@pytest.fixture
async def collections_handler(db_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager
    config = db_provider.config

    handler = PostgresCollectionsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        config=config,
    )
    await handler.create_tables()
    return handler


@pytest.fixture
async def conversations_handler(db_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager

    handler = PostgresConversationsHandler(project_name, connection_manager)
    await handler.create_tables()
    return handler


@pytest.fixture
async def documents_handler(db_provider):
    dimension = db_provider.dimension
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager

    handler = PostgresDocumentsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        dimension=dimension,
    )
    await handler.create_tables()
    return handler


@pytest.fixture
async def graphs_handler(db_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager
    dimension = db_provider.dimension
    quantization_type = db_provider.quantization_type

    # If collections_handler is needed, you can depend on the collections_handler fixture
    # or pass None if it's optional.
    handler = PostgresGraphsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        dimension=dimension,
        quantization_type=quantization_type,
        collections_handler=
        None,  # if needed, or await collections_handler fixture
    )
    await handler.create_tables()
    return handler


@pytest.fixture
async def limits_handler(db_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager
    config = db_provider.config

    handler = PostgresLimitsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        config=config,
    )
    await handler.create_tables()
    # Optionally truncate
    await connection_manager.execute_query(
        f"TRUNCATE {handler._get_table_name('request_log')};")
    return handler


@pytest.fixture
async def users_handler(db_provider, crypto_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager

    handler = PostgresUserHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        crypto_provider=crypto_provider,
    )
    await handler.create_tables()

    # Optionally clean up users table before each test
    await connection_manager.execute_query(
        f"TRUNCATE {handler._get_table_name('users')} CASCADE;")
    await connection_manager.execute_query(
        f"TRUNCATE {handler._get_table_name('users_api_keys')} CASCADE;")

    return handler


@pytest.fixture
async def prompt_handler(db_provider):
    """Returns an instance of PostgresPromptsHandler, creating the necessary
    tables first."""
    # from core.providers.database.postgres_prompts import PostgresPromptsHandler

    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager

    handler = PostgresPromptsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        # You can specify a local prompt directory if desired
        prompt_directory=None,
    )
    # Create necessary tables and do initial prompt load
    await handler.create_tables()
    return handler


@pytest.fixture
async def graphs_handler(db_provider):
    project_name = db_provider.project_name
    connection_manager = db_provider.connection_manager
    dimension = db_provider.dimension
    quantization_type = db_provider.quantization_type

    # Optionally ensure 'collection_ids' column exists on your table(s), e.g.:
    create_col_sql = f"""
        ALTER TABLE "{project_name}"."graphs_entities"
        ADD COLUMN IF NOT EXISTS collection_ids UUID[] DEFAULT '{{}}';
    """
    await connection_manager.execute_query(create_col_sql)

    handler = PostgresGraphsHandler(
        project_name=project_name,
        connection_manager=connection_manager,
        dimension=dimension,
        quantization_type=quantization_type,
        collections_handler=None,
    )
    await handler.create_tables()
    return handler
