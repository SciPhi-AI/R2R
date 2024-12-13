# tests/integration/test_chunks.py
import asyncio
import uuid
from typing import AsyncGenerator, List, Optional, Tuple

import pytest

from r2r import R2RAsyncClient, R2RException


class AsyncR2RTestClient:
    """Wrapper to ensure async operations use the correct event loop"""

    def __init__(self, base_url: str = "http://localhost:7275"):
        self.client = R2RAsyncClient(base_url)

    async def create_document(
        self, chunks: List[str], run_with_orchestration: bool = False
    ) -> Tuple[str, List[dict]]:
        response = await self.client.documents.create(
            chunks=chunks, run_with_orchestration=run_with_orchestration
        )
        return response["results"]["document_id"], []

    async def delete_document(self, doc_id: str) -> None:
        await self.client.documents.delete(id=doc_id)

    async def list_chunks(self, doc_id: str) -> List[dict]:
        response = await self.client.documents.list_chunks(id=doc_id)
        return response["results"]

    async def retrieve_chunk(self, chunk_id: str) -> dict:
        response = await self.client.chunks.retrieve(id=chunk_id)
        return response["results"]

    async def update_chunk(
        self, chunk_id: str, text: str, metadata: Optional[dict] = None
    ) -> dict:
        response = await self.client.chunks.update(
            {"id": chunk_id, "text": text, "metadata": metadata or {}}
        )
        return response["results"]

    async def delete_chunk(self, chunk_id: str) -> dict:
        response = await self.client.chunks.delete(id=chunk_id)
        return response["results"]

    async def search_chunks(self, query: str, limit: int = 5) -> List[dict]:
        response = await self.client.chunks.search(
            query=query, search_settings={"limit": limit}
        )
        return response["results"]

    async def register_user(self, email: str, password: str) -> None:
        await self.client.users.register(email, password)

    async def login_user(self, email: str, password: str) -> None:
        await self.client.users.login(email, password)

    async def logout_user(self) -> None:
        await self.client.users.logout()


@pytest.fixture
async def test_client() -> AsyncGenerator[AsyncR2RTestClient, None]:
    """Create a test client."""
    client = AsyncR2RTestClient()
    yield client


@pytest.fixture
async def test_document(
    test_client: AsyncR2RTestClient,
) -> AsyncGenerator[Tuple[str, List[dict]], None]:
    """Create a test document with chunks."""
    doc_id, _ = await test_client.create_document(
        ["Test chunk 1", "Test chunk 2"]
    )
    await asyncio.sleep(1)  # Wait for ingestion
    chunks = await test_client.list_chunks(doc_id)
    yield doc_id, chunks
    try:
        await test_client.delete_document(doc_id)
    except R2RException:
        pass


class TestChunks:
    @pytest.mark.asyncio
    async def test_create_and_list_chunks(
        self, test_client: AsyncR2RTestClient
    ):
        # Create document with chunks
        doc_id, _ = await test_client.create_document(
            ["Hello chunk", "World chunk"]
        )
        await asyncio.sleep(1)  # Wait for ingestion

        # List and verify chunks
        chunks = await test_client.list_chunks(doc_id)
        assert len(chunks) == 2, "Expected 2 chunks in the document"

        # Cleanup
        await test_client.delete_document(doc_id)

    @pytest.mark.asyncio
    async def test_retrieve_chunk(
        self, test_client: AsyncR2RTestClient, test_document
    ):
        doc_id, chunks = test_document
        chunk_id = chunks[0]["id"]

        retrieved = await test_client.retrieve_chunk(chunk_id)
        assert retrieved["id"] == chunk_id, "Retrieved wrong chunk ID"
        assert retrieved["text"] == "Test chunk 1", "Chunk text mismatch"

    @pytest.mark.asyncio
    async def test_update_chunk(
        self, test_client: AsyncR2RTestClient, test_document
    ):
        doc_id, chunks = test_document
        chunk_id = chunks[0]["id"]

        # Update chunk
        updated = await test_client.update_chunk(
            chunk_id, "Updated text", {"version": 2}
        )
        assert updated["text"] == "Updated text", "Chunk text not updated"
        assert updated["metadata"]["version"] == 2, "Metadata not updated"

    @pytest.mark.asyncio
    async def test_delete_chunk(
        self, test_client: AsyncR2RTestClient, test_document
    ):
        doc_id, chunks = test_document
        chunk_id = chunks[0]["id"]

        # Delete and verify
        result = await test_client.delete_chunk(chunk_id)
        assert result["success"], "Chunk deletion failed"

        # Verify deletion
        with pytest.raises(R2RException) as exc_info:
            await test_client.retrieve_chunk(chunk_id)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_search_chunks(self, test_client: AsyncR2RTestClient):
        # Create searchable document
        doc_id, _ = await test_client.create_document(
            ["Aristotle reference", "Another piece of text"]
        )
        await asyncio.sleep(1)  # Wait for indexing

        # Search
        results = await test_client.search_chunks("Aristotle")
        assert len(results) > 0, "No search results found"

        # Cleanup
        await test_client.delete_document(doc_id)

    @pytest.mark.asyncio
    async def test_unauthorized_chunk_access(
        self, test_client: AsyncR2RTestClient, test_document
    ):
        doc_id, chunks = test_document
        chunk_id = chunks[0]["id"]

        # Create and login as different user
        non_owner_client = AsyncR2RTestClient()
        email = f"test_{uuid.uuid4()}@example.com"
        await non_owner_client.register_user(email, "password123")
        await non_owner_client.login_user(email, "password123")

        # Attempt unauthorized access
        with pytest.raises(R2RException) as exc_info:
            await non_owner_client.retrieve_chunk(chunk_id)
        assert exc_info.value.status_code == 403


if __name__ == "__main__":
    pytest.main(["-v", "--asyncio-mode=auto"])
