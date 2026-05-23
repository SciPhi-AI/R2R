import pytest
import re
from unittest.mock import MagicMock, AsyncMock

from core.providers.database.chunks import PostgresChunksHandler
from core.base.abstractions import VectorTableName, IndexMeasure, IndexMethod

@pytest.fixture
def mock_connection_manager():
    manager = MagicMock()
    manager.execute_query = AsyncMock()
    manager.fetchrow_query = AsyncMock()
    manager.pool.get_connection = MagicMock()
    return manager

@pytest.fixture
def chunks_handler(mock_connection_manager):
    return PostgresChunksHandler(
        project_name="test_project",
        connection_manager=mock_connection_manager,
        dimension=128
    )

@pytest.mark.asyncio
async def test_create_index_malicious_column(chunks_handler):
    # Test that malicious index_column is rejected by whitelisting
    with pytest.raises(ValueError, match="Invalid index_column"):
        await chunks_handler.create_index(
            table_name=VectorTableName.CHUNKS,
            index_column="vec); DROP TABLE users; --"
        )

@pytest.mark.asyncio
async def test_create_index_malicious_name(chunks_handler):
    # Test that malicious index_name is rejected by regex validation
    with pytest.raises(ValueError, match="Invalid index_name"):
        await chunks_handler.create_index(
            table_name=VectorTableName.CHUNKS,
            index_name="idx; DROP TABLE users; --"
        )

@pytest.mark.asyncio
async def test_create_index_invalid_project_name(mock_connection_manager):
    # Test that malicious project_name (schema) is rejected
    handler = PostgresChunksHandler(
        project_name="malicious'; DROP SCHEMA public; --",
        connection_manager=mock_connection_manager,
        dimension=128
    )
    with pytest.raises(ValueError, match="Invalid project_name"):
        await handler.create_index(
            table_name=VectorTableName.CHUNKS
        )

@pytest.mark.asyncio
async def test_delete_index_validation(chunks_handler):
    # Test that delete_index correctly validates index_name and uses quoted identifiers
    conn_mgr = chunks_handler.connection_manager
    conn_mgr.fetchrow_query.return_value = {"indexdef": "CREATE INDEX ... (vec ...)"}

    index_name = "valid_idx"

    await chunks_handler.delete_index(
        index_name=index_name,
        table_name=VectorTableName.CHUNKS,
        concurrently=False,
    )

    # Assert: ensure execute_query was awaited and DROP INDEX appears with quotes
    assert conn_mgr.execute_query.await_count == 1
    called_sql = conn_mgr.execute_query.await_args.args[0]
    assert "DROP INDEX" in called_sql
    assert f'"{index_name}"' in called_sql

@pytest.mark.asyncio
async def test_index_name_too_long(chunks_handler):
    # index_name longer than 63 characters should be rejected
    long_name = "x" * 64
    with pytest.raises(ValueError, match="exceeds maximum length"):
        await chunks_handler.create_index(
            table_name=VectorTableName.CHUNKS,
            index_name=long_name
        )
