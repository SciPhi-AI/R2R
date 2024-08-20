import random
import uuid

import pytest
from core import (
    DatabaseConfig,
    DatabaseProvider,
    Vector,
    VectorEntry,
    generate_id_from_label,
)
from core.providers import PostgresDBProvider
from dotenv import load_dotenv

load_dotenv()


# Sample vector entries
def generate_random_vector_entry(id: str, dimension: int) -> VectorEntry:
    vector = [random.random() for _ in range(dimension)]
    metadata = {"key": f"value_{id}"}
    return VectorEntry(
        fragment_id=generate_id_from_label(id),
        extraction_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        group_ids=[uuid.uuid4()],
        vector=Vector(vector),
        text=f"Sample text for {id}",
        metadata=metadata,
    )


dimension = 3
num_entries = 100
sample_entries = [
    generate_random_vector_entry(f"id_{i}", dimension)
    for i in range(num_entries)
]


# Fixture for PostgresDBProvider
@pytest.fixture
def pg_vector_db():
    random_collection_name = (
        f"test_collection_{random.randint(0, 1_000_000_000)}"
    )
    config = DatabaseConfig.create(
        provider="postgres", vecs_collection=random_collection_name
    )
    db = PostgresDBProvider(config, dimension=3)
    yield db
    # Teardown
    db.vx.delete_collection(
        db.config.extra_fields.get("vecs_collection", None)
    )


@pytest.mark.parametrize("db_fixture", ["pg_vector_db"])
def test_db_initialization(request, db_fixture):
    db = request.getfixturevalue(db_fixture)
    assert isinstance(db, DatabaseProvider)


@pytest.mark.parametrize("db_fixture", ["pg_vector_db"])
def test_db_copy_and_search(request, db_fixture):
    db = request.getfixturevalue(db_fixture)
    db.vector.upsert(sample_entries[0])
    results = db.vector.search(query_vector=sample_entries[0].vector.data)
    assert len(results) == 1
    assert results[0].fragment_id == sample_entries[0].fragment_id
    assert results[0].score == pytest.approx(1.0, rel=1e-3)


@pytest.mark.parametrize("db_fixture", ["pg_vector_db"])
def test_db_upsert_and_search(request, db_fixture):
    db = request.getfixturevalue(db_fixture)
    db.vector.upsert(sample_entries[0])
    results = db.vector.search(query_vector=sample_entries[0].vector.data)
    assert len(results) == 1
    assert results[0].fragment_id == sample_entries[0].fragment_id
    assert results[0].score == pytest.approx(1.0, rel=1e-3)


@pytest.mark.parametrize("db_fixture", ["pg_vector_db"])
def test_imperfect_match(request, db_fixture):
    db = request.getfixturevalue(db_fixture)
    db.vector.upsert(sample_entries[0])
    query_vector = [val + 0.1 for val in sample_entries[0].vector.data]
    results = db.vector.search(query_vector=query_vector)
    assert len(results) == 1
    assert results[0].fragment_id == sample_entries[0].fragment_id
    assert results[0].score < 1.0


@pytest.mark.parametrize("db_fixture", ["pg_vector_db"])
def test_bulk_insert_and_search(request, db_fixture):
    db = request.getfixturevalue(db_fixture)
    for entry in sample_entries:
        db.vector.upsert(entry)

    query_vector = sample_entries[0].vector.data
    results = db.vector.search(query_vector=query_vector, limit=5)
    assert len(results) == 5
    assert results[0].fragment_id == sample_entries[0].fragment_id
    assert results[0].score == pytest.approx(1.0, rel=1e-3)


@pytest.mark.parametrize("db_fixture", ["pg_vector_db"])
def test_search_with_filters(request, db_fixture):
    db = request.getfixturevalue(db_fixture)
    for entry in sample_entries:
        db.vector.upsert(entry)

    filtered_id = sample_entries[0].metadata["key"]
    query_vector = sample_entries[0].vector.data
    results = db.vector.search(
        query_vector=query_vector, filters={"key": filtered_id}
    )
    assert len(results) == 1
    assert results[0].fragment_id == sample_entries[0].fragment_id
    assert results[0].metadata["key"] == filtered_id


@pytest.mark.parametrize("db_fixture", ["pg_vector_db"])
def test_delete(request, db_fixture):
    db = request.getfixturevalue(db_fixture)
    for entry in sample_entries:
        db.vector.upsert(entry)

    key_to_delete = sample_entries[0].metadata["key"]
    db.vector.delete(filters={"key": {"$eq": key_to_delete}})

    results = db.vector.search(query_vector=sample_entries[0].vector.data)
    assert all(result.metadata["key"] != key_to_delete for result in results)


@pytest.mark.parametrize("db_fixture", ["pg_vector_db"])
def test_upsert(request, db_fixture):
    db = request.getfixturevalue(db_fixture)
    db.vector.upsert(sample_entries[0])
    modified_entry = VectorEntry(
        fragment_id=sample_entries[0].fragment_id,
        extraction_id=sample_entries[0].extraction_id,
        document_id=sample_entries[0].document_id,
        user_id=sample_entries[0].user_id,
        group_ids=sample_entries[0].group_ids,
        vector=Vector([0.5, 0.5, 0.5]),
        text="Modified text",
        metadata={"key": "new_value"},
    )
    db.vector.upsert(modified_entry)

    results = db.vector.search(query_vector=[0.5, 0.5, 0.5])
    assert len(results) == 1
    assert results[0].fragment_id == sample_entries[0].fragment_id
    assert results[0].metadata["key"] == "new_value"
    assert results[0].text == "Modified text"
