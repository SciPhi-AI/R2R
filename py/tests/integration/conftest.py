# tests/conftest.py
import asyncio
import uuid
from typing import AsyncGenerator, Generator

import pytest

from r2r import R2RAsyncClient, R2RClient


class TestConfig:
    def __init__(self):
        self.base_url = "http://localhost:7272"
        self.index_wait_time = 1.0
        self.chunk_creation_wait_time = 1.0
        self.superuser_email = "admin@example.com"
        self.superuser_password = "change_me_immediately"
        self.test_timeout = 30  # seconds


@pytest.fixture  # (scope="session")
def config() -> TestConfig:
    return TestConfig()


@pytest.fixture  # scope="session")
async def client(config) -> AsyncGenerator[R2RClient, None]:
    """Create a shared client instance for the test session."""
    client = R2RClient(config.base_url)
    yield client
    # Session cleanup if needed


@pytest.fixture  # (scope="session")
async def aclient(config) -> AsyncGenerator[R2RClient, None]:
    """Create a shared client instance for the test session."""
    client = R2RAsyncClient(config.base_url)
    yield client
    # Session cleanup if needed


@pytest.fixture
async def superuser_client(
    client: R2RClient, config: TestConfig
) -> AsyncGenerator[R2RClient, None]:
    """Creates a superuser client for tests requiring elevated privileges."""
    await client.users.login(config.superuser_email, config.superuser_password)
    yield client
    await client.users.logout()


import uuid

import pytest

from r2r import Message, R2RClient, R2RException, SearchMode


@pytest.fixture(scope="session")
def config():
    class TestConfig:
        base_url = "http://localhost:7272"
        superuser_email = "admin@example.com"
        superuser_password = "change_me_immediately"

    return TestConfig()


@pytest.fixture(scope="session")
def client(config):
    """Create a client instance and log in as a superuser."""
    client = R2RClient(config.base_url)
    client.users.login(config.superuser_email, config.superuser_password)
    return client


@pytest.fixture(scope="session")
def test_document(config):
    """Create and yield a test document, then clean up."""
    client = R2RClient(config.base_url)
    client.users.login(config.superuser_email, config.superuser_password)

    random_suffix = str(uuid.uuid4())
    doc_resp = client.documents.create(
        raw_text=f"{random_suffix} Test doc for collections",
        run_with_orchestration=False,
    )

    doc_id = doc_resp["results"]["document_id"]
    yield doc_id
    # Cleanup: Try deleting the document if it still exists
    try:
        client.documents.delete(id=doc_id)
    except R2RException:
        pass


@pytest.fixture(scope="session")
def test_collection(client, test_document):
    """Create a test collection with sample documents."""
    collection_name = f"Test Collection {uuid.uuid4()}"
    collection_id = client.collections.create(name=collection_name)["results"][
        "id"
    ]

    docs = [
        {
            "text": f"Aristotle was a Greek philosopher who studied under Plato {str(uuid.uuid4())}.",
            "metadata": {
                "rating": 5,
                "tags": ["philosophy", "greek"],
                "category": "ancient",
            },
        },
        {
            "text": f"Socrates is considered a founder of Western philosophy  {str(uuid.uuid4())}.",
            "metadata": {
                "rating": 3,
                "tags": ["philosophy", "classical"],
                "category": "ancient",
            },
        },
        {
            "text": f"Rene Descartes was a French philosopher. unique_philosopher  {str(uuid.uuid4())}",
            "metadata": {
                "rating": 8,
                "tags": ["rationalism", "french"],
                "category": "modern",
            },
        },
        {
            "text": f"Immanuel Kant, a German philosopher, influenced Enlightenment thought  {str(uuid.uuid4())}.",
            "metadata": {
                "rating": 7,
                "tags": ["enlightenment", "german"],
                "category": "modern",
            },
        },
    ]

    doc_ids = []
    for doc in docs:
        result = client.documents.create(
            raw_text=doc["text"], metadata=doc["metadata"]
        )["results"]
        doc_id = result["document_id"]
        doc_ids.append(doc_id)
        client.collections.add_document(collection_id, doc_id)
    client.collections.add_document(collection_id, test_document)
    return {"collection_id": collection_id, "document_ids": doc_ids}
