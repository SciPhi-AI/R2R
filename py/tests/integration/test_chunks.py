import asyncio
import contextlib
import uuid
from typing import AsyncGenerator, Optional, Tuple

import pytest

from r2r import R2RAsyncClient, R2RException


class AsyncR2RTestClient:
    """Wrapper to ensure async operations use the correct event loop."""

    def __init__(self, base_url: str = "http://localhost:7272"):
        self.client = R2RAsyncClient(base_url)

    async def create_document(self,
                              chunks: list[str],
                              run_with_orchestration: bool = False):
        response = await self.client.documents.create(
            chunks=chunks, run_with_orchestration=run_with_orchestration)
        return response.results.document_id, []

    async def delete_document(self, doc_id: str):
        await self.client.documents.delete(id=doc_id)

    async def list_chunks(self, doc_id: str):
        response = await self.client.documents.list_chunks(id=doc_id)
        return response.results

    async def retrieve_chunk(self, chunk_id: str):
        response = await self.client.chunks.retrieve(id=chunk_id)
        return response.results

    async def update_chunk(self,
                           chunk_id: str,
                           text: str,
                           metadata: Optional[dict] = None):
        response = await self.client.chunks.update({
            "id": chunk_id,
            "text": text,
            "metadata": metadata or {}
        })
        return response.results

    async def delete_chunk(self, chunk_id: str):
        response = await self.client.chunks.delete(id=chunk_id)
        return response.results

    async def search_chunks(self, query: str, limit: int = 5):
        response = await self.client.chunks.search(
            query=query, search_settings={"limit": limit})
        return response.results

    async def register_user(self, email: str, password: str):
        await self.client.users.create(email, password)

    async def login_user(self, email: str, password: str):
        await self.client.users.login(email, password)

    async def logout_user(self):
        await self.client.users.logout()


@pytest.fixture
async def test_client() -> AsyncGenerator[AsyncR2RTestClient, None]:
    """Create a test client."""
    yield AsyncR2RTestClient()


@pytest.fixture
async def test_document(
    test_client: AsyncR2RTestClient,
) -> AsyncGenerator[Tuple[str, list[dict]], None]:
    """Create a test document with chunks."""
    uuid_1 = uuid.uuid4()
    uuid_2 = uuid.uuid4()
    doc_id, _ = await test_client.create_document(
        [f"Test chunk 1_{uuid_1}", f"Test chunk 2_{uuid_2}"])
    await asyncio.sleep(1)  # Wait for ingestion
    chunks = await test_client.list_chunks(str(doc_id))
    yield doc_id, chunks
    with contextlib.suppress(R2RException):
        await test_client.delete_document(str(doc_id))


class TestChunks:

    @pytest.mark.asyncio
    async def test_create_and_list_chunks(self,
                                          test_client: AsyncR2RTestClient,
                                          cleanup_documents):
        # Create document with chunks
        doc_id, _ = await test_client.create_document(
            ["Hello chunk", "World chunk"])
        cleanup_documents(str(doc_id))
        await asyncio.sleep(1)  # Wait for ingestion

        # List and verify chunks
        chunks = await test_client.list_chunks(str(doc_id))
        assert len(chunks) == 2, "Expected 2 chunks in the document"

    @pytest.mark.asyncio
    async def test_retrieve_chunk(self, test_client: AsyncR2RTestClient,
                                  test_document):
        doc_id, chunks = test_document
        chunk_id = chunks[0].id

        retrieved = await test_client.retrieve_chunk(chunk_id)
        assert str(retrieved.id) == str(chunk_id), "Retrieved wrong chunk ID"
        assert retrieved.text.split("_")[0] == "Test chunk 1", (
            "Chunk text mismatch")

    @pytest.mark.asyncio
    async def test_update_chunk(self, test_client: AsyncR2RTestClient,
                                test_document):
        doc_id, chunks = test_document
        chunk_id = chunks[0].id

        # Update chunk
        updated = await test_client.update_chunk(str(chunk_id), "Updated text",
                                                 {"version": 2})
        assert updated.text == "Updated text", "Chunk text not updated"
        assert updated.metadata["version"] == 2, "Metadata not updated"

    @pytest.mark.asyncio
    async def test_delete_chunk(self, test_client: AsyncR2RTestClient,
                                test_document):
        doc_id, chunks = test_document
        chunk_id = chunks[0].id

        # Delete and verify
        result = await test_client.delete_chunk(str(chunk_id))
        assert result.success, "Chunk deletion failed"

        # Verify deletion
        with pytest.raises(R2RException) as exc_info:
            await test_client.retrieve_chunk(str(chunk_id))
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_search_chunks(self, test_client: AsyncR2RTestClient,
                                 cleanup_documents):
        # Create searchable document
        random_1 = uuid.uuid4()
        random_2 = uuid.uuid4()
        doc_id, _ = await test_client.create_document([
            f"Aristotle reference {random_1}",
            f"Another piece of text {random_2}",
        ])
        cleanup_documents(doc_id)
        await asyncio.sleep(1)  # Wait for indexing

        # Search
        results = await test_client.search_chunks("Aristotle")
        assert len(results) > 0, "No search results found"

    @pytest.mark.asyncio
    async def test_unauthorized_chunk_access(self,
                                             test_client: AsyncR2RTestClient,
                                             test_document):
        doc_id, chunks = test_document
        chunk_id = chunks[0].id

        # Create and login as different user
        non_owner_client = AsyncR2RTestClient()
        email = f"test_{uuid.uuid4()}@example.com"
        await non_owner_client.register_user(email, "password123")
        await non_owner_client.login_user(email, "password123")

        # Attempt unauthorized access
        with pytest.raises(R2RException) as exc_info:
            await non_owner_client.retrieve_chunk(str(chunk_id))
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_list_chunks_with_filters(self,
                                            test_client: AsyncR2RTestClient,
                                            cleanup_documents):
        """Test listing chunks with owner_id filter."""
        # Create and login as temporary user
        temp_email = f"{uuid.uuid4()}@example.com"
        await test_client.register_user(temp_email, "password123")
        await test_client.login_user(temp_email, "password123")

        # Create a document with chunks
        doc_id, _ = await test_client.create_document(
            ["Test chunk 1", "Test chunk 2"])
        cleanup_documents(doc_id)
        await asyncio.sleep(1)  # Wait for ingestion

    @pytest.mark.asyncio
    async def test_list_chunks_pagination(self,
                                          test_client: AsyncR2RTestClient):
        """Test chunk listing with pagination."""
        # Create and login as temporary user
        temp_email = f"{uuid.uuid4()}@example.com"
        await test_client.register_user(temp_email, "password123")
        await test_client.login_user(temp_email, "password123")

        doc_id = None
        try:
            # Create a document with multiple chunks
            chunks = [f"Test chunk {i}" for i in range(5)]
            doc_id, _ = await test_client.create_document(chunks)
            await asyncio.sleep(1)  # Wait for ingestion

            # Test first page
            response1 = await test_client.client.chunks.list(offset=0, limit=2)

            assert len(
                response1.results) == 2, ("Expected 2 results on first page")

            # Test second page
            response2 = await test_client.client.chunks.list(offset=2, limit=2)

            assert len(
                response2.results) == 2, ("Expected 2 results on second page")

            # Verify no duplicate results
            ids_page1 = {str(chunk.id) for chunk in response1.results}
            ids_page2 = {str(chunk.id) for chunk in response2.results}
            assert not ids_page1.intersection(ids_page2), (
                "Found duplicate chunks across pages")

        finally:
            # Cleanup
            if doc_id:
                try:
                    await test_client.delete_document(doc_id)
                except:
                    pass
            await test_client.logout_user()

    @pytest.mark.asyncio
    async def test_list_chunks_with_multiple_documents(
            self, test_client: AsyncR2RTestClient):
        """Test listing chunks across multiple documents."""
        # Create and login as temporary user
        temp_email = f"{uuid.uuid4()}@example.com"
        await test_client.register_user(temp_email, "password123")
        await test_client.login_user(temp_email, "password123")

        doc_ids = []
        try:
            # Create multiple documents
            for i in range(2):
                doc_id, _ = await test_client.create_document(
                    [f"Doc {i} chunk 1", f"Doc {i} chunk 2"])
                doc_ids.append(doc_id)

            await asyncio.sleep(1)  # Wait for ingestion

            # List all chunks
            response = await test_client.client.chunks.list(offset=0, limit=10)

            assert len(response.results) == 4, "Expected 4 total chunks"

            chunk_doc_ids = {
                str(chunk.document_id)
                for chunk in response.results
            }
            assert all(
                str(doc_id) in chunk_doc_ids
                for doc_id in doc_ids), ("Got chunks from wrong documents")

        finally:
            # Cleanup
            for doc_id in doc_ids:
                try:
                    await test_client.delete_document(doc_id)
                except:
                    pass
            await test_client.logout_user()


@pytest.fixture
async def cleanup_documents(test_client: AsyncR2RTestClient):
    doc_ids = []

    def _track_document(doc_id: str) -> str:
        doc_ids.append(doc_id)
        return doc_id

    yield _track_document

    # Cleanup all documents
    for doc_id in doc_ids:
        with contextlib.suppress(R2RException):
            await test_client.delete_document(doc_id)


if __name__ == "__main__":
    pytest.main(["-v", "--asyncio-mode=auto"])
