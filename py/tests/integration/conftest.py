import uuid
import asyncio
import time
from typing import AsyncGenerator

import pytest

from r2r import R2RAsyncClient, R2RClient, R2RException


class RetryableR2RAsyncClient(R2RAsyncClient):
    """R2RAsyncClient with automatic retry logic for timeouts"""

    async def _make_request(self, method, endpoint, version="v3", **kwargs):
        retries = 0
        max_retries = 3
        delay = 1.0

        while True:
            try:
                return await super()._make_request(method, endpoint, version, **kwargs)
            except R2RException as e:
                if "Request failed" in str(e) and retries < max_retries:
                    retries += 1
                    wait_time = delay * (2 ** (retries - 1))
                    print(f"Request timed out. Retrying ({retries}/{max_retries}) after {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                elif "429" in str(e) and retries < max_retries:
                    retries += 1
                    wait_time = delay * (3 ** (retries - 1))
                    print(f"Rate limited. Retrying ({retries}/{max_retries}) after {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise

class RetryableR2RClient(R2RClient):
    """R2RClient with automatic retry logic for timeouts"""

    def _make_request(self, method, endpoint, version="v3", **kwargs):
        retries = 0
        max_retries = 3
        delay = 1.0

        while True:
            try:
                return super()._make_request(method, endpoint, version, **kwargs)
            except R2RException as e:
                if "Request failed" in str(e) and "timed out" in str(e) and retries < max_retries:
                    retries += 1
                    wait_time = delay * (2 ** (retries - 1))
                    print(f"Request timed out. Retrying ({retries}/{max_retries}) after {wait_time:.2f}s...")
                    time.sleep(wait_time)
                elif "429" in str(e) and retries < max_retries:
                    retries += 1
                    wait_time = delay * (3 ** (retries - 1))
                    print(f"Rate limited. Retrying ({retries}/{max_retries}) after {wait_time:.2f}s...")
                    time.sleep(wait_time)
                else:
                    raise



class TestConfig:
    def __init__(self):
        self.base_url = "http://localhost:7272"
        self.index_wait_time = 1.0
        self.chunk_creation_wait_time = 1.0
        self.superuser_email = "admin@example.com"
        self.superuser_password = "change_me_immediately"
        self.test_timeout = 30  # seconds


# Change this to session scope to match the client fixture
@pytest.fixture(scope="session")
def config() -> TestConfig:
    return TestConfig()


@pytest.fixture(scope="session")
async def client(config) -> AsyncGenerator[R2RClient, None]:
    """Create a shared client instance for the test session."""
    yield RetryableR2RClient(config.base_url)


@pytest.fixture
def mutable_client(config) -> R2RClient:
    """Create a shared client instance for the test session."""
    return RetryableR2RClient(config.base_url)


@pytest.fixture
async def aclient(config) -> AsyncGenerator[R2RAsyncClient, None]:
    """Create a retryable client instance for the test session."""
    yield RetryableR2RAsyncClient(config.base_url)


@pytest.fixture
async def superuser_client(
        mutable_client: R2RClient,
        config: TestConfig) -> AsyncGenerator[R2RClient, None]:
    """Creates a superuser client for tests requiring elevated privileges."""
    await mutable_client.users.login(config.superuser_email, config.superuser_password)
    yield mutable_client
    await mutable_client.users.logout()


@pytest.fixture(scope="session")
def test_document(client: R2RClient):
    """Create and yield a test document, then clean up."""
    random_suffix = str(uuid.uuid4())
    doc_id = client.documents.create(
        raw_text=f"{random_suffix} Test doc for collections",
        run_with_orchestration=False,
    ).results.document_id

    yield doc_id
    # Cleanup: Try deleting the document if it still exists
    try:
        client.documents.delete(id=doc_id)
    except R2RException:
        pass


@pytest.fixture(scope="session")
def test_collection(client: R2RClient, test_document):
    """Create a test collection with sample documents and clean up after
    tests."""
    collection_name = f"Test Collection {uuid.uuid4()}"
    collection_id = client.collections.create(name=collection_name).results.id

    docs = [
        {
            "text":
            f"Aristotle was a Greek philosopher who studied under Plato {str(uuid.uuid4())}.",
            "metadata": {
                "rating": 5,
                "tags": ["philosophy", "greek"],
                "category": "ancient",
            },
        },
        {
            "text":
            f"Socrates is considered a founder of Western philosophy  {str(uuid.uuid4())}.",
            "metadata": {
                "rating": 3,
                "tags": ["philosophy", "classical"],
                "category": "ancient",
            },
        },
        {
            "text":
            f"Rene Descartes was a French philosopher. unique_philosopher  {str(uuid.uuid4())}",
            "metadata": {
                "rating": 8,
                "tags": ["rationalism", "french"],
                "category": "modern",
            },
        },
        {
            "text":
            f"Immanuel Kant, a German philosopher, influenced Enlightenment thought  {str(uuid.uuid4())}.",
            "metadata": {
                "rating": 7,
                "tags": ["enlightenment", "german"],
                "category": "modern",
            },
        },
    ]

    doc_ids = []
    for doc in docs:
        doc_id = client.documents.create(
            raw_text=doc["text"], metadata=doc["metadata"]).results.document_id
        doc_ids.append(doc_id)
        client.collections.add_document(collection_id, doc_id)
    client.collections.add_document(collection_id, test_document)

    yield {"collection_id": collection_id, "document_ids": doc_ids}

    # Cleanup after tests
    try:
        # Remove and delete all documents
        for doc_id in doc_ids:
            try:
                client.documents.delete(id=doc_id)
            except R2RException:
                pass
        # Delete the collection
        try:
            client.collections.delete(collection_id)
        except R2RException:
            pass
    except Exception as e:
        print(f"Error during test_collection cleanup: {e}")
