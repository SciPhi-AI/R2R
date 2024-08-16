import random
from uuid import UUID, uuid4

import pytest

from r2r.base import DatabaseConfig, Vector, VectorEntry
from r2r.providers import PostgresDBProvider


@pytest.fixture
def vector_db():
    random_collection_name = (
        f"test_collection_{random.randint(0, 1_000_000_000)}"
    )
    config = DatabaseConfig.create(
        provider="postgres", vecs_collection=random_collection_name
    )
    db = PostgresDBProvider(config, dimension=3)
    yield db.vector
    # Teardown
    db.vx.delete_collection(
        db.config.extra_fields.get("vecs_collection", None)
    )


@pytest.fixture
def sample_entries(vector_db):
    entries = [
        VectorEntry(
            fragment_id=uuid4(),
            extraction_id=uuid4(),
            document_id=uuid4(),
            user_id=uuid4(),
            group_ids=[uuid4()],
            vector=Vector([0.1, 0.2, 0.3]),
            text="Apple",
            metadata={
                "category": "fruit",
                "color": "red",
                "price": 1.0,
            },
        ),
        VectorEntry(
            fragment_id=uuid4(),
            extraction_id=uuid4(),
            document_id=uuid4(),
            user_id=uuid4(),
            group_ids=[uuid4()],
            vector=Vector([0.2, 0.3, 0.4]),
            text="Banana",
            metadata={
                "category": "fruit",
                "color": "yellow",
                "price": 0.5,
            },
        ),
        VectorEntry(
            fragment_id=uuid4(),
            extraction_id=uuid4(),
            document_id=uuid4(),
            user_id=uuid4(),
            group_ids=[uuid4()],
            vector=Vector([0.3, 0.4, 0.5]),
            text="Carrot",
            metadata={
                "category": "vegetable",
                "color": "orange",
                "price": 0.75,
            },
        ),
        VectorEntry(
            fragment_id=uuid4(),
            extraction_id=uuid4(),
            document_id=uuid4(),
            user_id=uuid4(),
            group_ids=[uuid4()],
            vector=Vector([0.4, 0.5, 0.6]),
            text="Durian",
            metadata={
                "category": "fruit",
                "color": "green",
                "price": 5.0,
            },
        ),
    ]
    for entry in entries:
        vector_db.upsert(entry)
    return entries


def test_search_equality_filter(vector_db, sample_entries):
    query_vector = Vector([0.2, 0.3, 0.4])
    results = vector_db.search(
        query_vector.data,
        limit=10,
        filters={"category": {"$eq": "fruit"}},
    )
    assert len(results) == 3
    assert all(r.metadata["category"] == "fruit" for r in results)


def test_search_not_equal_filter(vector_db, sample_entries):
    query_vector = Vector([0.2, 0.3, 0.4])
    results = vector_db.search(
        query_vector.data,
        limit=10,
        filters={"category": {"$ne": "fruit"}},
    )
    assert len(results) == 1
    assert results[0].metadata["category"] == "vegetable"


def test_search_greater_than_filter(vector_db, sample_entries):
    query_vector = Vector([0.2, 0.3, 0.4])
    results = vector_db.search(
        query_vector.data,
        limit=10,
        filters={"price": {"$gt": 1.0}},
    )
    assert len(results) == 1
    assert results[0].text == "Durian"


def test_search_less_than_or_equal_filter(vector_db, sample_entries):
    query_vector = Vector([0.2, 0.3, 0.4])
    results = vector_db.search(
        query_vector.data,
        limit=10,
        filters={"price": {"$lte": 1.0}},
    )
    assert len(results) == 3
    assert all(r.metadata["price"] <= 1.0 for r in results)


def test_search_in_filter(vector_db, sample_entries):
    query_vector = Vector([0.2, 0.3, 0.4])
    results = vector_db.search(
        query_vector.data,
        limit=10,
        filters={"color": {"$in": ["red", "yellow"]}},
    )
    assert len(results) == 2
    assert all(r.metadata["color"] in ["red", "yellow"] for r in results)


def test_search_complex_and_filter(vector_db, sample_entries):
    query_vector = Vector([0.2, 0.3, 0.4])
    results = vector_db.search(
        query_vector.data,
        limit=10,
        filters={
            "$and": [
                {"category": {"$eq": "fruit"}},
                {"price": {"$lt": 2.0}},
                {"color": {"$ne": "yellow"}},
            ]
        },
    )
    assert len(results) == 1
    assert results[0].text == "Apple"


def test_search_complex_or_filter(vector_db, sample_entries):
    query_vector = Vector([0.2, 0.3, 0.4])
    results = vector_db.search(
        query_vector.data,
        limit=10,
        filters={
            "$or": [
                {"category": {"$eq": "vegetable"}},
                {"price": {"$gte": 5.0}},
            ]
        },
    )
    assert len(results) == 2
    assert any(r.metadata["category"] == "vegetable" for r in results)
    assert any(r.metadata["price"] >= 5.0 for r in results)


def test_search_nested_and_or_filters(vector_db, sample_entries):
    query_vector = Vector([0.2, 0.3, 0.4])
    results = vector_db.search(
        query_vector.data,
        limit=10,
        filters={
            "$and": [
                {"category": {"$eq": "fruit"}},
                {
                    "$or": [
                        {"color": {"$in": ["red", "yellow"]}},
                        {"price": {"$gt": 2.0}},
                    ]
                },
            ]
        },
    )
    assert len(results) == 3
    assert all(r.metadata["category"] == "fruit" for r in results)
    assert all(
        r.metadata["color"] in ["red", "yellow"] or r.metadata["price"] > 2.0
        for r in results
    )


def test_delete_equality(vector_db, sample_entries):
    deleted_ids = vector_db.delete({"category": {"$eq": "vegetable"}})
    assert len(deleted_ids) == 1
    remaining = vector_db.search(Vector([0.2, 0.3, 0.4]).data, limit=10)
    assert len(remaining) == 3
    assert all(r.metadata["category"] == "fruit" for r in remaining)


def test_delete_greater_than(vector_db, sample_entries):
    deleted_ids = vector_db.delete({"price": {"$gt": 1.0}})
    assert len(deleted_ids) == 1
    remaining = vector_db.search(Vector([0.2, 0.3, 0.4]).data, limit=10)
    assert len(remaining) == 3
    assert all(r.metadata["price"] <= 1.0 for r in remaining)


def test_delete_in(vector_db, sample_entries):
    deleted_ids = vector_db.delete({"color": {"$in": ["red", "yellow"]}})
    assert len(deleted_ids) == 2
    remaining = vector_db.search(Vector([0.2, 0.3, 0.4]).data, limit=10)
    assert len(remaining) == 2
    assert all(r.metadata["color"] not in ["red", "yellow"] for r in remaining)


def test_delete_complex_and(vector_db, sample_entries):
    deleted_ids = vector_db.delete(
        {
            "$and": [
                {"category": {"$eq": "fruit"}},
                {"price": {"$lt": 1.0}},
            ]
        }
    )
    assert len(deleted_ids) == 1
    remaining = vector_db.search(Vector([0.2, 0.3, 0.4]).data, limit=10)
    assert len(remaining) == 3
    assert not any(
        r.metadata["category"] == "fruit" and r.metadata["price"] < 1.0
        for r in remaining
    )


def test_delete_complex_or(vector_db, sample_entries):
    deleted_ids = vector_db.delete(
        {
            "$or": [
                {"category": {"$eq": "vegetable"}},
                {"price": {"$gte": 5.0}},
            ]
        }
    )
    assert len(deleted_ids) == 2
    remaining = vector_db.search(Vector([0.2, 0.3, 0.4]).data, limit=10)
    assert len(remaining) == 2
    assert all(
        r.metadata["category"] != "vegetable" and r.metadata["price"] < 5.0
        for r in remaining
    )


def test_delete_nested_and_or(vector_db, sample_entries):
    deleted_ids = vector_db.delete(
        {
            "$and": [
                {"category": {"$eq": "fruit"}},
                {
                    "$or": [
                        {"color": {"$in": ["red", "yellow"]}},
                        {"price": {"$gt": 2.0}},
                    ]
                },
            ]
        }
    )
    assert len(deleted_ids) == 3
    remaining = vector_db.search(Vector([0.2, 0.3, 0.4]).data, limit=10)
    assert len(remaining) == 1
    assert remaining[0].metadata["category"] == "vegetable"
