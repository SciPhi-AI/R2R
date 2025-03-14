import uuid

import pytest

from core.base import R2RException
from core.base.api.models import CollectionResponse


@pytest.mark.asyncio
async def test_create_collection(collections_handler):
    owner_id = uuid.uuid4()
    resp = await collections_handler.create_collection(
        owner_id=owner_id,
        name="Test Collection",
        description="A test collection",
    )
    assert isinstance(resp, CollectionResponse)
    assert resp.name == "Test Collection"
    assert resp.owner_id == owner_id
    assert resp.description == "A test collection"


@pytest.mark.asyncio
async def test_create_collection_default_name(collections_handler):
    owner_id = uuid.uuid4()
    # If no name provided, should use default_collection_name from config
    resp = await collections_handler.create_collection(owner_id=owner_id)
    assert isinstance(resp, CollectionResponse)
    assert resp.name is not None  # default collection name should be set
    assert resp.owner_id == owner_id


@pytest.mark.asyncio
async def test_update_collection(collections_handler):
    owner_id = uuid.uuid4()
    coll = await collections_handler.create_collection(
        owner_id=owner_id, name="Original Name", description="Original Desc")

    updated = await collections_handler.update_collection(
        collection_id=coll.id,
        name="Updated Name",
        description="New Description",
    )
    assert updated.name == "Updated Name"
    assert updated.description == "New Description"
    # user_count and document_count should be integers
    assert isinstance(updated.user_count, int)
    assert isinstance(updated.document_count, int)


@pytest.mark.asyncio
async def test_update_collection_no_fields(collections_handler):
    owner_id = uuid.uuid4()
    coll = await collections_handler.create_collection(owner_id=owner_id,
                                                       name="NoUpdate",
                                                       description="No Update")

    with pytest.raises(R2RException) as exc:
        await collections_handler.update_collection(collection_id=coll.id)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_delete_collection_relational(collections_handler):
    owner_id = uuid.uuid4()
    coll = await collections_handler.create_collection(owner_id=owner_id,
                                                       name="ToDelete")

    # Confirm existence
    exists = await collections_handler.collection_exists(coll.id)
    assert exists is True

    await collections_handler.delete_collection_relational(coll.id)

    exists = await collections_handler.collection_exists(coll.id)
    assert exists is False


@pytest.mark.asyncio
async def test_collection_exists(collections_handler):
    owner_id = uuid.uuid4()
    coll = await collections_handler.create_collection(owner_id=owner_id)
    assert await collections_handler.collection_exists(coll.id) is True


@pytest.mark.asyncio
async def test_documents_in_collection(collections_handler, db_provider):
    # Create a collection
    owner_id = uuid.uuid4()
    coll = await collections_handler.create_collection(owner_id=owner_id,
                                                       name="DocCollection")

    # Insert some documents related to this collection
    # We'll directly insert into the documents table for simplicity
    doc_id = uuid.uuid4()
    insert_doc_query = f"""
        INSERT INTO {db_provider.project_name}.documents (id, collection_ids, owner_id, type, metadata, title, version, size_in_bytes, ingestion_status, extraction_status)
        VALUES ($1, $2, $3, 'txt', '{{}}', 'Test Doc', 'v1', 1234, 'pending', 'pending')
    """
    await db_provider.connection_manager.execute_query(
        insert_doc_query, [doc_id, [coll.id], owner_id])

    # Now fetch documents in collection
    res = await collections_handler.documents_in_collection(coll.id,
                                                            offset=0,
                                                            limit=10)
    assert len(res["results"]) == 1
    assert res["total_entries"] == 1
    assert res["results"][0].id == doc_id
    assert res["results"][0].title == "Test Doc"


@pytest.mark.asyncio
async def test_get_collections_overview(collections_handler, db_provider):
    owner_id = uuid.uuid4()
    coll1 = await collections_handler.create_collection(owner_id=owner_id,
                                                        name="Overview1")
    coll2 = await collections_handler.create_collection(owner_id=owner_id,
                                                        name="Overview2")

    overview = await collections_handler.get_collections_overview(offset=0,
                                                                  limit=10)
    # There should be at least these two
    ids = [c.id for c in overview["results"]]
    assert coll1.id in ids
    assert coll2.id in ids


@pytest.mark.asyncio
async def test_assign_document_to_collection_relational(
        collections_handler, db_provider):
    owner_id = uuid.uuid4()
    coll = await collections_handler.create_collection(owner_id=owner_id,
                                                       name="Assign")

    # Insert a doc
    doc_id = uuid.uuid4()
    insert_doc_query = f"""
        INSERT INTO {db_provider.project_name}.documents (id, owner_id, type, metadata, title, version, size_in_bytes, ingestion_status, extraction_status, collection_ids)
        VALUES ($1, $2, 'txt', '{{}}', 'Standalone Doc', 'v1', 10, 'pending', 'pending', ARRAY[]::uuid[])
    """
    await db_provider.connection_manager.execute_query(insert_doc_query,
                                                       [doc_id, owner_id])

    # Assign this doc to the collection
    await collections_handler.assign_document_to_collection_relational(
        doc_id, coll.id)

    # Verify doc is now in collection
    docs = await collections_handler.documents_in_collection(coll.id,
                                                             offset=0,
                                                             limit=10)
    assert len(docs["results"]) == 1
    assert docs["results"][0].id == doc_id


@pytest.mark.asyncio
async def test_remove_document_from_collection_relational(
        collections_handler, db_provider):
    owner_id = uuid.uuid4()
    coll = await collections_handler.create_collection(owner_id=owner_id,
                                                       name="RemoveDoc")

    # Insert a doc already in collection
    doc_id = uuid.uuid4()
    insert_doc_query = f"""
        INSERT INTO {db_provider.project_name}.documents
        (id, owner_id, type, metadata, title, version, size_in_bytes, ingestion_status, extraction_status, collection_ids)
        VALUES ($1, $2, 'txt', '{{}}'::jsonb, 'Another Doc', 'v1', 10, 'pending', 'pending', $3)
    """
    await db_provider.connection_manager.execute_query(
        insert_doc_query, [doc_id, owner_id, [coll.id]])

    # Remove it
    await collections_handler.remove_document_from_collection_relational(
        doc_id, coll.id)

    docs = await collections_handler.documents_in_collection(coll.id,
                                                             offset=0,
                                                             limit=10)
    assert len(docs["results"]) == 0


@pytest.mark.asyncio
async def test_delete_nonexistent_collection(collections_handler):
    non_existent_id = uuid.uuid4()
    with pytest.raises(R2RException) as exc:
        await collections_handler.delete_collection_relational(non_existent_id)
    assert exc.value.status_code == 404, (
        "Should raise 404 for non-existing collection")
