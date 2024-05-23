import unittest
from uuid import uuid4

import pytest
from unittest.mock import MagicMock, patch

from r2r.core.abstractions.vector import VectorEntry, VectorSearchResult
from r2r.vector_dbs.milvus.base import MilvusVectorDB, CollectionNotInitializedError
from r2r.core import VectorDBConfig
import os

os.environ['MILVUS_URI'] = "https://in03-d33c3d7fa502071.api.gcp-us-west1.zillizcloud.com"
os.environ['ZILLIZ_CLOUD_API_KEY'] = "4e4cacaf44822536891630f8457822e930b4896c6623b16575e9e4802e74bdc5adbc355fc0a789d09185772e4a7a71afc10fd46a"

class TestMilvusVectorDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up the test class with a mock configuration for the MilvusVectorDB."""
        config = MagicMock(spec=VectorDBConfig)
        config.collection_name = "test_collection"
        config.provider = "milvus"
        cls.db = MilvusVectorDB(config)
        print('Start of TestMilvusVectorDB tests\n')

    def test_initialize_milvus_db(self):
        """Test the initialization of the Milvus database collection."""
        print('Running test_initialize_milvus_db\n')
        try:
            # Attempt to initialize the collection
            self.db.initialize_collection(dimension=3)

            # Check if the collection exists in the database
            assert self.db.client.has_collection(self.db.config.collection_name), "Collection does not exist after initialization"
        except CollectionNotInitializedError:
            pytest.fail("Collection not initialized")
        except Exception as e:
            pytest.fail(f"Unexpected error during initialization: {e}")

    def test_upsert(self):
        """Test the upsert functionality of the Milvus database."""
        print('Running test_upsert\n')
        # Create sample VectorEntry objects
        entries = [
            VectorEntry(entry_id=1, vector=[0.1, 0.2, 0.3], metadata={"label": "A"}),
            VectorEntry(entry_id=2, vector=[0.2, 0.9, 0.1], metadata={"label": "B", "test": 123}),
            VectorEntry(entry_id=3, vector=[0.8, 0.7, 0.6], metadata={"label": "C"}),
            VectorEntry(entry_id=4, vector=[0.4, 0.5, 0.9], metadata={"label": "D"})
        ]

        try:
            for entry in entries:
                self.db.upsert(entry)
        except Exception as e:
            pytest.fail(f"Upsert failed: {e}")

    def test_search(self):
        """Test the search functionality of the Milvus database."""
        print('Running test_search')
        try:
            results = self.db.search(
                query_vector=[0.4, 0.5, 0.9],
                filters={"label": "D"},
                output_fields=['vector', 'label']
            )
        except Exception as e:
            pytest.fail(f"Search failed: {e}")

        print(f"{results}\n")

    def test_filtered_deletion(self):
        """Test the filtered deletion functionality of the Milvus database."""
        print('Running test_filtered_deletion')
        try:
            self.db.filtered_deletion(
                key="test",
                value=123
            )
        except Exception as e:
            pytest.fail("Filtered deletion failed")

    def test_get_all_unique_values(self):
        """Test the retrieval of all unique values for a given metadata field."""
        print('Running test_get_all_unique_values')
        try:
            res = self.db.get_all_unique_values(
                metadata_field='id',
                filter_field='label',
                filter_value='C'
            )
        except Exception as e:
            pytest.fail(f"get_all_unique_values failed: {e}")

        print(f"{res}\n")
        assert res[0] == 3, "No unique values returned"


if __name__ == "__main__":
    test = TestMilvusVectorDB()
    test.setUpClass()
    test.test_initialize_milvus_db()
    test.test_upsert()
    test.test_search()
    test.test_filtered_deletion()
    test.test_get_all_unique_values()

