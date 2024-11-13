from uuid import UUID

import pytest

from core.base import DocumentResponse, DocumentType, R2RException
from core.base.api.models import CollectionResponse


@pytest.mark.asyncio
async def test_create_collection(temporary_postgres_db_provider):
    collection = await temporary_postgres_db_provider.create_collection(
        "Test Collection", "Test Description"
    )
    assert isinstance(collection, CollectionResponse)
    assert collection.name == "Test Collection"
    assert collection.description == "Test Description"


@pytest.mark.asyncio
async def test_get_collection(temporary_postgres_db_provider):
    created_collection = (
        await temporary_postgres_db_provider.create_collection(
            "Test Collection", "Test Description"
        )
    )
    retrieved_collection = await temporary_postgres_db_provider.get_collection(
        created_collection.collection_id
    )
    assert retrieved_collection == created_collection


@pytest.mark.asyncio
async def test_update_collection(temporary_postgres_db_provider):
    created_collection = (
        await temporary_postgres_db_provider.create_collection(
            "Test Collection", "Test Description"
        )
    )
    updated_collection = (
        await temporary_postgres_db_provider.update_collection(
            created_collection.collection_id,
            name="Updated Collection",
            description="Updated Description",
        )
    )
    assert updated_collection.name == "Updated Collection"
    assert updated_collection.description == "Updated Description"


@pytest.mark.asyncio
async def test_delete_collection(temporary_postgres_db_provider):
    created_collection = (
        await temporary_postgres_db_provider.create_collection(
            "Test Collection", "Test Description"
        )
    )
    await temporary_postgres_db_provider.delete_collection_relational(
        created_collection.collection_id
    )
    with pytest.raises(R2RException):
        await temporary_postgres_db_provider.delete_collection_relational(
            created_collection.collection_id
        )

    # await temporary_postgres_db_provider.delete_collection_vector(
    #     created_collection.collection_id
    # )
    # with pytest.raises(R2RException):
    #     await temporary_postgres_db_provider.delete_collection_vector(
    #         created_collection.collection_id
    #     )


@pytest.mark.asyncio
async def test_list_collections(temporary_postgres_db_provider):
    await temporary_postgres_db_provider.create_collection(
        "Collection 1", "Description 1"
    )
    await temporary_postgres_db_provider.create_collection(
        "Collection 2", "Description 2"
    )
    collections = await temporary_postgres_db_provider.list_collections()
    assert len(collections["results"]) >= 2
    assert collections["total_entries"] >= 2


@pytest.mark.asyncio
async def test_get_collections_by_ids(temporary_postgres_db_provider):
    collection1 = await temporary_postgres_db_provider.create_collection(
        "Collection 1", "Description 1"
    )
    collection2 = await temporary_postgres_db_provider.create_collection(
        "Collection 2", "Description 2"
    )
    collections = await temporary_postgres_db_provider.get_collections_by_ids(
        [collection1.collection_id, collection2.collection_id]
    )
    assert len(collections) == 2
    assert collections[0].collection_id == collection1.collection_id
    assert collections[1].collection_id == collection2.collection_id


@pytest.mark.asyncio
async def test_assign_and_remove_document_from_collection(
    temporary_postgres_db_provider,
):
    collection = await temporary_postgres_db_provider.create_collection(
        "Test Collection", "Test Description"
    )
    document_id = UUID("00000000-0000-0000-0000-000000000001")
    await temporary_postgres_db_provider.upsert_documents_overview(
        DocumentResponse(
            id=document_id,
            collection_ids=[],
            user_id=UUID("00000000-0000-0000-0000-000000000002"),
            document_type=DocumentType.PDF,
            metadata={},
            version="v1",
            size_in_bytes=0,
        )
    )
    await temporary_postgres_db_provider.assign_document_to_collection_relational(
        document_id, collection.collection_id
    )
    await temporary_postgres_db_provider.assign_document_to_collection_vector(
        document_id, collection.collection_id
    )
    document_collections = (
        await temporary_postgres_db_provider.document_collections(document_id)
    )
    assert len(document_collections["results"]) == 1
    assert (
        document_collections["results"][0].collection_id
        == collection.collection_id
    )

    await temporary_postgres_db_provider.remove_document_from_collection_relational(
        document_id, collection.collection_id
    )
    await temporary_postgres_db_provider.remove_document_from_collection_vector(
        document_id, collection.collection_id
    )
    document_collections = (
        await temporary_postgres_db_provider.document_collections(document_id)
    )
    assert len(document_collections["results"]) == 0


@pytest.mark.asyncio
async def test_get_collections_for_user(temporary_postgres_db_provider):
    user = await temporary_postgres_db_provider.create_user(
        "test@example.com", "password"
    )
    collection1 = await temporary_postgres_db_provider.create_collection(
        "Collection 1", "Description 1"
    )
    collection2 = await temporary_postgres_db_provider.create_collection(
        "Collection 2", "Description 2"
    )
    await temporary_postgres_db_provider.add_user_to_collection(
        user.id, collection1.collection_id
    )
    await temporary_postgres_db_provider.add_user_to_collection(
        user.id, collection2.collection_id
    )
    user_collections = (
        await temporary_postgres_db_provider.get_collections_for_user(user.id)
    )
    assert len(user_collections["results"]) == 2
    assert user_collections["total_entries"] == 2
