import uuid

import pytest

from r2r import R2RClient, R2RException


@pytest.fixture(scope="session")
def test_document_2(client: R2RClient):
    """Create and yield a test document, then clean up."""
    doc_resp = client.documents.create(
        raw_text="Another test doc for collections",
        run_with_orchestration=False,
    )
    doc_id = doc_resp.results.document_id
    yield doc_id
    # Cleanup: Try deleting the document if it still exists
    try:
        client.documents.delete(id=doc_id)
    except R2RException:
        pass


def test_create_collection(client: R2RClient):
    collection_id = client.collections.create(name="Test Collection Creation",
                                              description="Desc").results.id
    assert collection_id is not None, "No collection_id returned"

    # Cleanup
    client.collections.delete(collection_id)


def test_list_collections(client: R2RClient, test_collection):
    results = client.collections.list(limit=10, offset=0).results
    assert len(results) >= 1, "Expected at least one collection, none found"


def test_retrieve_collection(client: R2RClient, test_collection):
    # Retrieve the collection just created
    retrieved = client.collections.retrieve(
        test_collection["collection_id"]).results
    assert retrieved.id == test_collection["collection_id"], (
        "Retrieved wrong collection ID")


def test_update_collection(client: R2RClient, test_collection):
    updated_name = "Updated Test Collection"
    updated_desc = "Updated description"
    updated = client.collections.update(
        test_collection["collection_id"],
        name=updated_name,
        description=updated_desc,
    ).results
    assert updated.name == updated_name, "Collection name not updated"
    assert updated.description == updated_desc, (
        "Collection description not updated")


def test_add_document_to_collection(client: R2RClient, test_collection,
                                    test_document_2):
    client.collections.add_document(test_collection["collection_id"],
                                    str(test_document_2))
    docs_in_collection = client.collections.list_documents(
        test_collection["collection_id"]).results
    found = any(
        str(doc.id) == str(test_document_2) for doc in docs_in_collection)
    assert found, "Added document not found in collection"


def test_list_documents_in_collection(client: R2RClient, test_collection,
                                      test_document):
    # Document should be in the collection already from previous test
    docs_in_collection = client.collections.list_documents(
        test_collection["collection_id"]).results
    found = any(
        str(doc.id) == str(test_document) for doc in docs_in_collection)
    assert found, "Expected document not found in collection"


def test_remove_document_from_collection(client: R2RClient, test_collection,
                                         test_document):
    # Remove the document from the collection
    client.collections.remove_document(test_collection["collection_id"],
                                       test_document)
    docs_in_collection = client.collections.list_documents(
        test_collection["collection_id"]).results
    found = any(str(doc.id) == test_document for doc in docs_in_collection)
    assert not found, "Document still present in collection after removal"


def test_remove_non_member_user_from_collection(mutable_client: R2RClient):
    # Create a user and a collection
    user_email = f"user_{uuid.uuid4()}@test.com"
    password = "pwd123"
    mutable_client.users.create(user_email, password)
    mutable_client.users.login(user_email, password)

    # Create a collection by the same user
    collection_id = mutable_client.collections.create(
        name="User Owned Collection").results.id
    mutable_client.users.logout()

    # Create another user who will not be added to the collection
    another_user_email = f"user2_{uuid.uuid4()}@test.com"
    mutable_client.users.create(another_user_email, password)
    mutable_client.users.login(another_user_email, password)
    another_user_id = mutable_client.users.me().results.id
    mutable_client.users.logout()

    # Re-login as collection owner
    mutable_client.users.login(user_email, password)

    # Attempt to remove the other user (who was never added)
    with pytest.raises(R2RException) as exc_info:
        mutable_client.collections.remove_user(collection_id, another_user_id)

    assert exc_info.value.status_code in [
        400,
        404,
    ], "Wrong error code for removing non-member user"

    # Cleanup
    mutable_client.collections.delete(collection_id)


def test_delete_collection(client: R2RClient):
    # Create a collection and delete it
    coll_id = client.collections.create(name="Delete Me").results.id
    client.collections.delete(coll_id)

    # Verify retrieval fails
    with pytest.raises(R2RException) as exc_info:
        client.collections.retrieve(coll_id)
    assert exc_info.value.status_code == 404, (
        "Wrong error code retrieving deleted collection")


def test_add_user_to_non_existent_collection(mutable_client: R2RClient):
    # Create a regular user
    user_email = f"test_user_{uuid.uuid4()}@test.com"
    user_password = "test_password"
    mutable_client.users.create(user_email, user_password)
    mutable_client.users.login(user_email, user_password)
    user_id = mutable_client.users.me().results.id
    mutable_client.users.logout()

    # Re-login as superuser to try adding user to a non-existent collection
    # (Assumes superuser credentials are already in the client fixture)
    fake_collection_id = str(uuid.uuid4())  # Non-existent collection ID
    with pytest.raises(R2RException) as exc_info:
        result = mutable_client.collections.add_user(fake_collection_id,
                                                     user_id)
    assert exc_info.value.status_code == 404, (
        "Wrong error code for non-existent collection")


def test_create_collection_without_name(client: R2RClient):
    # Attempt to create a collection without a name
    with pytest.raises(R2RException) as exc_info:
        client.collections.create(name="", description="No name")
    # TODO - Error should be a 400 or 422, not 409
    assert exc_info.value.status_code in [
        400,
        422,
        409,
    ], "Expected validation error for empty name"


def test_filter_collections_by_non_existent_id(client: R2RClient):
    # Filter collections by an ID that does not exist
    random_id = str(uuid.uuid4())
    resp = client.collections.list(ids=[random_id])
    assert len(
        resp.results) == 0, ("Expected no collections for a non-existent ID")


def test_list_documents_in_empty_collection(client: R2RClient):
    # Create a new collection with no documents
    empty_coll_id = client.collections.create(
        name="Empty Collection").results.id

    docs = client.collections.list_documents(empty_coll_id).results
    assert len(docs) == 0, "Expected no documents in a new empty collection"
    client.collections.delete(empty_coll_id)


def test_remove_document_not_in_collection(client: R2RClient, test_document):
    # Create collection without adding the test_document
    coll_id = client.collections.create(name="NoDocCollection").results.id

    # Try removing the test_document that was never added
    with pytest.raises(R2RException) as exc_info:
        client.collections.remove_document(coll_id, test_document)
    # Expect 404 or 400 since doc not in collection
    assert exc_info.value.status_code in [
        400,
        404,
    ], "Expected error removing doc not in collection"
    client.collections.delete(coll_id)


def test_add_non_existent_document_to_collection(client: R2RClient):
    # Create a collection
    coll_id = client.collections.create(name="AddNonExistentDoc").results.id

    # Try adding a non-existent document
    fake_doc_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.collections.add_document(coll_id, fake_doc_id)
    assert exc_info.value.status_code in [
        400,
        404,
    ], "Expected error adding non-existent document"
    client.collections.delete(coll_id)


def test_delete_non_existent_collection(client: R2RClient):
    # Try deleting a collection that doesn't exist
    fake_collection_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.collections.delete(fake_collection_id)
    assert exc_info.value.status_code == 404, (
        "Expected 404 when deleting non-existent collection")


def test_retrieve_collection_by_name(client: R2RClient):
    # Generate a unique collection name
    unique_name = f"TestRetrieveByName-{uuid.uuid4()}"

    # Create a collection with the unique name
    created_resp = client.collections.create(
        name=unique_name, description="Collection for retrieval by name test")
    created = created_resp.results
    assert created.id is not None, (
        "Creation did not return a valid collection ID")

    # Retrieve the collection by its name
    retrieved_resp = client.collections.retrieve_by_name(unique_name)
    retrieved = retrieved_resp.results
    assert retrieved.id == created.id, (
        "Retrieved collection does not match the created collection")

    # Cleanup: Delete the created collection
    client.collections.delete(created.id)
