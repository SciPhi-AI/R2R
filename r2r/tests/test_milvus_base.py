import pytest
from unittest.mock import MagicMock, patch
from r2r.vector_dbs.milvus.base import MilvusVectorDB, CollectionNotInitializedError, MilvusException
from r2r.core import VectorDBConfig

@pytest.fixture
def setup_milvus_db():
    config = MagicMock(spec=VectorDBConfig)
    config.collection_name = "test_collection"
    config.provider = "milvus"
    client = MagicMock()
    db = MilvusVectorDB(config)
    db.client = client
    return db, client

def test_filtered_deletion_without_initialization(setup_milvus_db):
    db, client = setup_milvus_db
    client.has_collection.return_value = False

    with pytest.raises(CollectionNotInitializedError):
        db.filtered_deletion("key", "str", "value")

def test_filtered_deletion_with_initialization(setup_milvus_db):
    db, client = setup_milvus_db
    client.has_collection.return_value = True

    try:
        db.filtered_deletion("key", "str", "value")
    except CollectionNotInitializedError:
        pytest.fail("filtered_deletion() raised CollectionNotInitializedError unexpectedly!")

def test_get_all_unique_values_without_initialization(setup_milvus_db):
    db, client = setup_milvus_db
    client.has_collection.return_value = False

    with pytest.raises(CollectionNotInitializedError):
        db.get_all_unique_values("metadata_field", "filter_field", "filter_value")

def test_get_all_unique_values_with_initialization(setup_milvus_db):
    db, client = setup_milvus_db
    client.has_collection.return_value = True
    client.query.return_value = ["value1", "value2"]

    result = db.get_all_unique_values("metadata_field", "filter_field", "filter_value")
    assert result == ["value1", "value2"]

if __name__ == "__main__":
    pytest.main()

