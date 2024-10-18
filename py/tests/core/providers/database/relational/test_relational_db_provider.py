# tests/providers/database/test_relational_db_provider.py
import pytest

from core.providers.database import PostgresDBProvider


@pytest.mark.asyncio
async def test_relational_db_initialization(postgres_db_provider):
    assert isinstance(postgres_db_provider, PostgresDBProvider)
    # assert postgres_db_provider.relational is not None
