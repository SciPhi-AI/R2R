import pytest

from core.providers.database import PostgresDBProvider
from r2r import ChunkSearchSettings


@pytest.mark.asyncio
async def test_vector_db_initialization(postgres_db_provider):
    assert isinstance(postgres_db_provider, PostgresDBProvider)
    # assert postgres_db_provider is not None


@pytest.mark.asyncio
async def test_search_equality_filter(postgres_db_provider, sample_entries):
    query_vector = sample_entries[0]
    results = await postgres_db_provider.semantic_search(
        query_vector.vector.data,
        ChunkSearchSettings(
            search_limit=10, filters={"key": {"$eq": "value_id_0"}}
        ),
    )
    assert len(results) == 1
    assert results[0].metadata["key"] == "value_id_0"


@pytest.mark.asyncio
async def test_search_not_equal_filter(postgres_db_provider, sample_entries):
    query_vector = sample_entries[0]
    results = await postgres_db_provider.semantic_search(
        query_vector.vector.data,
        ChunkSearchSettings(
            search_limit=100, filters={"key": {"$ne": "value_id_0"}}
        ),
    )
    assert len(results) == 99
    assert all(r.metadata["key"] != "value_id_0" for r in results)


@pytest.mark.asyncio
async def test_search_greater_than_filter(
    postgres_db_provider, sample_entries
):
    query_vector = sample_entries[0]
    results = await postgres_db_provider.semantic_search(
        query_vector.vector.data,
        ChunkSearchSettings(
            search_limit=100, filters={"raw_key": {"$gt": 50}}
        ),
    )
    assert len(results) == 49
    assert all(int(r.text.split("_")[-1]) > 50 for r in results)


@pytest.mark.asyncio
async def test_search_less_than_or_equal_filter(
    postgres_db_provider, sample_entries
):
    query_vector = sample_entries[0]
    results = await postgres_db_provider.semantic_search(
        query_vector.vector.data,
        ChunkSearchSettings(
            search_limit=10,
            filters={"raw_key": {"$lte": 20}},
            ef_search=100,  # TODO - Better understand why we need to set this to search the entire database.
        ),
    )  # TODO - Why is this number not always 10?
    assert len(results) == 10

    results = await postgres_db_provider.semantic_search(
        query_vector.vector.data,
        ChunkSearchSettings(
            search_limit=100, filters={"raw_key": {"$lte": 20}}
        ),
    )
    assert len(results) == 21
    assert all(int(r.text.split("_")[-1]) <= 20 for r in results)


@pytest.mark.asyncio
async def test_search_in_filter(postgres_db_provider, sample_entries):
    query_vector = sample_entries[0]
    results = await postgres_db_provider.semantic_search(
        query_vector.vector.data,
        ChunkSearchSettings(
            search_limit=10,
            filters={"key": {"$in": ["value_id_0", "value_id_1"]}},
        ),
    )
    assert len(results) == 2
    assert all(
        r.metadata["key"] in ["value_id_0", "value_id_1"] for r in results
    )


@pytest.mark.asyncio
async def test_search_complex_and_filter(postgres_db_provider, sample_entries):
    query_vector = sample_entries[0]
    results = await postgres_db_provider.semantic_search(
        query_vector.vector.data,
        ChunkSearchSettings(
            search_limit=10,
            filters={
                "$and": [
                    {"key": {"$eq": "value_id_0"}},
                    {"raw_key": {"$lt": 50}},
                ]
            },
        ),
    )
    assert len(results) == 1
    assert results[0].metadata["key"] == "value_id_0"
    assert int(results[0].text.split("_")[-1]) < 50


@pytest.mark.asyncio
async def test_search_complex_or_filter(postgres_db_provider, sample_entries):
    query_vector = sample_entries[0]
    results = await postgres_db_provider.semantic_search(
        query_vector.vector.data,
        ChunkSearchSettings(
            search_limit=11,
            ef_search=100,  # TODO - Better understand why we need to set this to search the entire database.
            filters={
                "$or": [
                    {"key": {"$eq": "value_id_0"}},
                    {"raw_key": {"$gte": 90}},
                ]
            },
        ),
    )
    assert len(results) == 11
    assert any(r.metadata["key"] == "value_id_0" for r in results)
    assert any(int(r.text.split("_")[-1]) >= 90 for r in results)


@pytest.mark.asyncio
async def test_search_nested_and_or_filters(
    postgres_db_provider, sample_entries
):
    query_vector = sample_entries[0]
    results = await postgres_db_provider.semantic_search(
        query_vector.vector.data,
        ChunkSearchSettings(
            search_limit=10,
            ef_search=100,  # TODO - Better understand why we need to set this to search the entire database.
            filters={
                "$and": [
                    {"key": {"$eq": "value_id_0"}},
                    {
                        "$or": [
                            {"key": {"$in": ["value_id_0", "value_id_1"]}},
                            {"raw_key": {"$gt": 98}},
                        ]
                    },
                ]
            },
        ),
    )
    assert len(results) == 1
    assert results[0].metadata["key"] == "value_id_0"
    assert results[0].text == "Sample text for id_0"


@pytest.mark.asyncio
async def test_delete_equality(temporary_postgres_db_provider, sample_entries):
    deleted_ids = await temporary_postgres_db_provider.delete(
        {"key": {"$eq": "value_id_0"}}
    )
    assert len(deleted_ids) == 1
    remaining = await temporary_postgres_db_provider.semantic_search(
        sample_entries[0].vector.data,
        ChunkSearchSettings(search_limit=100),
    )
    assert len(remaining) == 99
    assert all(r.metadata["key"] != "value_id_0" for r in remaining)


@pytest.mark.asyncio
async def test_delete_greater_than(
    temporary_postgres_db_provider, sample_entries
):
    deleted_ids = await temporary_postgres_db_provider.delete(
        {"raw_key": {"$gt": 90}}
    )
    assert len(deleted_ids) == 9
    remaining = await temporary_postgres_db_provider.semantic_search(
        sample_entries[0].vector.data,
        ChunkSearchSettings(search_limit=100),
    )
    assert len(remaining) == 91
    assert all(int(r.text.split("_")[-1]) <= 90 for r in remaining)


@pytest.mark.asyncio
async def test_delete_in(temporary_postgres_db_provider, sample_entries):
    deleted_ids = await temporary_postgres_db_provider.delete(
        {"key": {"$in": ["value_id_0", "value_id_1"]}}
    )
    assert len(deleted_ids) == 2
    remaining = await temporary_postgres_db_provider.semantic_search(
        sample_entries[0].vector.data,
        ChunkSearchSettings(search_limit=100),
    )
    assert len(remaining) == 98
    assert all(
        r.metadata["key"] not in ["value_id_0", "value_id_1"]
        for r in remaining
    )


@pytest.mark.asyncio
async def test_delete_complex_and(
    temporary_postgres_db_provider, sample_entries
):
    deleted_ids = await temporary_postgres_db_provider.delete(
        {
            "$and": [
                {"key": {"$eq": "value_id_0"}},
                {"raw_key": {"$lt": 50}},
            ]
        }
    )
    assert len(deleted_ids) == 1
    remaining = await temporary_postgres_db_provider.semantic_search(
        sample_entries[0].vector.data,
        ChunkSearchSettings(search_limit=100),
    )
    assert len(remaining) == 99
    assert not any(
        r.metadata["key"] == "value_id_0" and int(r.text.split("_")[-1]) < 50
        for r in remaining
    )


@pytest.mark.asyncio
async def test_delete_complex_or(
    temporary_postgres_db_provider, sample_entries
):
    deleted_ids = await temporary_postgres_db_provider.delete(
        {
            "$or": [
                {"key": {"$eq": "value_id_0"}},
                {"raw_key": {"$gte": 90}},
            ]
        }
    )
    assert len(deleted_ids) == 11
    remaining = await temporary_postgres_db_provider.semantic_search(
        sample_entries[0].vector.data,
        ChunkSearchSettings(search_limit=100),
    )
    assert len(remaining) == 89
    assert all(
        r.metadata["key"] != "value_id_0" and int(r.text.split("_")[-1]) < 90
        for r in remaining
    )


@pytest.mark.asyncio
async def test_delete_nested_and_or(
    temporary_postgres_db_provider, sample_entries
):
    deleted_ids = await temporary_postgres_db_provider.delete(
        {
            "$and": [
                {"key": {"$eq": "value_id_0"}},
                {
                    "$or": [
                        {"key": {"$in": ["value_id_0", "value_id_1"]}},
                        {"raw_key": {"$gt": 98}},
                    ]
                },
            ]
        }
    )
    assert len(deleted_ids) == 1
    remaining = await temporary_postgres_db_provider.semantic_search(
        sample_entries[0].vector.data,
        ChunkSearchSettings(search_limit=100),
    )
    assert len(remaining) == 99
    assert not any(
        r.metadata["key"] == "value_id_0"
        and (
            r.metadata["key"] in ["value_id_0", "value_id_1"]
            or int(r.text.split("_")[-1]) > 98
        )
        for r in remaining
    )
