import uuid
import pytest
from core.base import Vector, VectorEntry


@pytest.mark.asyncio
async def test_upsert_and_get_chunk(chunks_handler):
    # Create a sample vector entry
    entry = VectorEntry(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        collection_ids=[],
        vector=Vector(data=[0.1, 0.2, 0.3, 0.4]),
        text="This is a test chunk.",
        metadata={"foo": "bar"},
    )

    await chunks_handler.upsert(entry)

    fetched = await chunks_handler.get_chunk(entry.id)
    assert fetched["id"] == entry.id
    assert fetched["text"] == "This is a test chunk."
    assert fetched["metadata"]["foo"] == "bar"


@pytest.mark.asyncio
async def test_upsert_entries(chunks_handler):
    entries = []
    for i in range(5):
        entries.append(
            VectorEntry(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                owner_id=uuid.uuid4(),
                collection_ids=[],
                vector=Vector(data=[float(i)] * 4),
                text=f"Chunk number {i}",
                metadata={"i": i},
            )
        )

    await chunks_handler.upsert_entries(entries)

    # Fetch one of them to ensure it's there
    fetched = await chunks_handler.get_chunk(entries[2].id)
    assert fetched["text"] == "Chunk number 2"
    assert fetched["metadata"]["i"] == 2


@pytest.mark.asyncio
async def test_delete(chunks_handler):
    entry = VectorEntry(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        collection_ids=[],
        vector=Vector(data=[0.5, 0.5, 0.5, 0.5]),
        text="To be deleted",
        metadata={"delete": True},
    )

    await chunks_handler.upsert(entry)

    # Ensure it exists
    fetched = await chunks_handler.get_chunk(entry.id)
    assert fetched["metadata"]["delete"] is True

    # Delete
    res = await chunks_handler.delete({"id": str(entry.id)})
    assert str(entry.id) in res
    assert res[str(entry.id)]["status"] == "deleted"

    # Try fetching again
    with pytest.raises(Exception):
        await chunks_handler.get_chunk(entry.id)

@pytest.mark.asyncio
async def test_full_text_search(chunks_handler):
    # Insert chunks with distinct text
    entry1 = VectorEntry(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        collection_ids=[],
        vector=Vector(data=[0.1, 0.1, 0.1, 0.1]),
        text="Aristotle was a Greek philosopher",
        metadata={"category": "philosophy"},
    )
    entry2 = VectorEntry(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        collection_ids=[],
        vector=Vector(data=[0.2, 0.2, 0.2, 0.2]),
        text="This chunk mentions Plato and Aristotle",
        metadata={"category": "philosophy"},
    )

    await chunks_handler.upsert(entry1)
    await chunks_handler.upsert(entry2)

    from core.base import SearchSettings

    search_settings = SearchSettings(
        limit=5,
        # We rely on default full-text search language = english
    )
    results = await chunks_handler.full_text_search(
        "Aristotle", search_settings
    )
    texts = [r.text for r in results]
    assert len(results) > 0
    assert (
        "Aristotle" in texts[0]
    )  # Ensure Aristotle is found in at least one.


@pytest.mark.asyncio
async def test_list_document_chunks(chunks_handler):
    doc_id = uuid.uuid4()
    entries = []
    for i in range(3):
        entries.append(
            VectorEntry(
                id=uuid.uuid4(),
                document_id=doc_id,
                owner_id=uuid.uuid4(),
                collection_ids=[],
                vector=Vector(data=[float(i)] * 4),
                text=f"Doc chunk {i}",
                metadata={"chunk_order": i},
            )
        )

    await chunks_handler.upsert_entries(entries)

    res = await chunks_handler.list_document_chunks(
        document_id=doc_id, offset=0, limit=2
    )
    assert len(res["results"]) == 2
    assert res["total_entries"] == 3
    # Check order
    assert res["results"][0]["text"] == "Doc chunk 0"


@pytest.mark.asyncio
async def test_hybrid_search(chunks_handler):
    # Hybrid search uses both semantic and full-text
    # Insert some chunks that mention Aristotle and have distinctive vectors
    entries = []
    for i in range(3):
        entries.append(
            VectorEntry(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                owner_id=uuid.uuid4(),
                collection_ids=[],
                vector=Vector(data=[float(i)] * 4),
                text=f"Aristotle contribution {i}",
                metadata={},
            )
        )

    await chunks_handler.upsert_entries(entries)

    from core.base import (
        ChunkSearchSettings,
        HybridSearchSettings,
        SearchSettings,
    )

    hybrid_settings = HybridSearchSettings(
        full_text_limit=10,
        semantic_weight=0.5,
        full_text_weight=0.5,
        rrf_k=60,
    )

    search_settings = SearchSettings(
        limit=3,
        offset=0,
        use_hybrid_search=True,
        hybrid_settings=hybrid_settings,
        chunk_settings=ChunkSearchSettings(),
    )

    query_text = "Aristotle"
    query_vector = [0.0, 0.0, 0.0, 0.0]
    results = await chunks_handler.hybrid_search(
        query_text, query_vector, search_settings
    )
    assert len(results) <= 3
    assert any("Aristotle contribution" in r.text for r in results)
