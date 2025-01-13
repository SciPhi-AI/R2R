import uuid

import pytest

from fuse import FUSEClient, FUSEException


@pytest.fixture(scope="session")
def config():
    class TestConfig:
        base_url = "http://localhost:7272"
        superuser_email = "admin@example.com"
        superuser_password = "change_me_immediately"

    return TestConfig()


@pytest.fixture(scope="session")
def client(config):
    """Create a client instance and log in as superuser."""
    client = FUSEClient(config.base_url)
    client.users.login(config.superuser_email, config.superuser_password)
    return client


def test_create_and_get_index(client):
    index_name = f"test_index_{uuid.uuid4().hex[:8]}"
    config = {
        "table_name": "chunks",
        "index_method": "hnsw",
        "index_measure": "cosine_distance",
        "index_arguments": {"m": 16, "ef_construction": 64, "ef": 40},
        "index_name": index_name,
        "index_column": "vec",
        "concurrently": True,
    }

    # Create the index
    create_resp = client.indices.create(
        config=config, run_with_orchestration=True
    )["results"]
    assert "message" in create_resp, "No message in create response"

    # Get the index details
    get_resp = client.indices.retrieve(
        index_name=index_name, table_name="chunks"
    )["results"]
    assert "index" in get_resp, "No index in get response"
    assert get_resp["index"]["name"] == index_name, "Index name mismatch"


def test_list_indices(client):
    resp = client.indices.list(limit=5)["results"]
    assert "indices" in resp, "No indices field in response"
    # Just ensure we get a list without error. Detailed checks depend on data availability.
    assert isinstance(resp["indices"], list), "Indices field is not a list"


def test_delete_index(client):
    # Create an index to delete
    index_name = f"test_delete_index_{uuid.uuid4().hex[:8]}"
    config = {
        "table_name": "chunks",
        "index_method": "hnsw",
        "index_measure": "cosine_distance",
        "index_arguments": {"m": 16, "ef_construction": 64, "ef": 40},
        "index_name": index_name,
        "index_column": "vec",
        "concurrently": True,
    }

    client.indices.create(config=config, run_with_orchestration=True)[
        "results"
    ]

    # Delete the index
    delete_resp = client.indices.delete(
        index_name=index_name, table_name="chunks"
    )["results"]
    assert "message" in delete_resp, "No message in delete response"

    # Verify deletion by attempting to retrieve the index
    with pytest.raises(FUSEException) as exc_info:
        client.indices.retrieve(index_name=index_name, table_name="chunks")
    assert (
        "not found" in str(exc_info.value).lower()
    ), "Unexpected error message for deleted index"


def test_error_handling(client):
    # Try to get a non-existent index
    with pytest.raises(FUSEException) as exc_info:
        client.indices.retrieve(
            index_name="nonexistent_index", table_name="chunks"
        )
    assert (
        "not found" in str(exc_info.value).lower()
    ), "Unexpected error message for non-existent index"
