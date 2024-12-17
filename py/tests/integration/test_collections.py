import uuid

import pytest

from r2r import R2RClient, R2RException


@pytest.fixture(scope="session")
def test_document_2(config):
    """Create and yield a test document, then clean up."""
    client = R2RClient(config.base_url)
    client.users.login(config.superuser_email, config.superuser_password)

    doc_resp = client.documents.create(
        raw_text="Another test doc for collections",
        run_with_orchestration=False,
    )
    doc_id = doc_resp["results"]["document_id"]
    yield doc_id
    # Cleanup: Try deleting the document if it still exists
    try:
        client.documents.delete(id=doc_id)
    except R2RException:
        pass


def test_create_collection(client):
    resp = client.collections.create(
        name="Test Collection Creation", description="Desc"
    )
    coll_id = resp["results"]["id"]
    assert coll_id is not None, "No collection_id returned"

    # Cleanup
    client.collections.delete(coll_id)


def test_list_collections(client, test_collection):
    listed = client.collections.list(limit=10, offset=0)
    results = listed["results"]
    assert len(results) >= 1, "Expected at least one collection, none found"


def test_retrieve_collection(client, test_collection):
    # Retrieve the collection just created
    print("test_collection = ", test_collection)
    retrieved = client.collections.retrieve(test_collection["collection_id"])[
        "results"
    ]
    assert (
        retrieved["id"] == test_collection["collection_id"]
    ), "Retrieved wrong collection ID"


def test_update_collection(client, test_collection):
    updated_name = "Updated Test Collection"
    updated_desc = "Updated description"
    updated = client.collections.update(
        test_collection["collection_id"],
        name=updated_name,
        description=updated_desc,
    )["results"]
    assert updated["name"] == updated_name, "Collection name not updated"
    assert (
        updated["description"] == updated_desc
    ), "Collection description not updated"


def test_add_document_to_collection(client, test_collection, test_document_2):
    # Add the test document to the test collection
    client.collections.add_document(
        test_collection["collection_id"], test_document_2
    )
    # Verify by listing documents
    docs_in_collection = client.collections.list_documents(
        test_collection["collection_id"]
    )["results"]
    found = any(doc["id"] == test_document_2 for doc in docs_in_collection)
    assert found, "Added document not found in collection"


def test_list_documents_in_collection(client, test_collection, test_document):
    # Document should be in the collection already from previous test
    docs_in_collection = client.collections.list_documents(
        test_collection["collection_id"]
    )["results"]
    print("docs_in_collection = ", docs_in_collection)
    print("test_document = ", test_document)
    found = any(doc["id"] == test_document for doc in docs_in_collection)
    assert found, "Expected document not found in collection"


def test_remove_document_from_collection(
    client, test_collection, test_document
):
    # Remove the document from the collection
    client.collections.remove_document(
        test_collection["collection_id"], test_document
    )
    docs_in_collection = client.collections.list_documents(
        test_collection["collection_id"]
    )["results"]
    found = any(doc["id"] == test_document for doc in docs_in_collection)
    assert not found, "Document still present in collection after removal"


def test_remove_non_member_user_from_collection(client):
    # Create a user and a collection
    user_email = f"user_{uuid.uuid4()}@test.com"
    password = "pwd123"
    client.users.create(user_email, password)
    client.users.login(user_email, password)

    # Create a collection by the same user
    collection_resp = client.collections.create(name="User Owned Collection")[
        "results"
    ]
    collection_id = collection_resp["id"]
    client.users.logout()

    # Create another user who will not be added to the collection
    another_user_email = f"user2_{uuid.uuid4()}@test.com"
    client.users.create(another_user_email, password)
    client.users.login(another_user_email, password)
    another_user_id = client.users.me()["results"]["id"]
    client.users.logout()

    # Re-login as collection owner
    client.users.login(user_email, password)

    # Attempt to remove the other user (who was never added)
    with pytest.raises(R2RException) as exc_info:
        client.collections.remove_user(collection_id, another_user_id)

    assert exc_info.value.status_code in [
        400,
        404,
    ], "Wrong error code for removing non-member user"

    # Cleanup
    client.collections.delete(collection_id)


def test_delete_collection(client):
    # Create a collection and delete it
    coll = client.collections.create(name="Delete Me")["results"]
    coll_id = coll["id"]
    client.collections.delete(coll_id)

    # Verify retrieval fails
    with pytest.raises(R2RException) as exc_info:
        client.collections.retrieve(coll_id)
    assert (
        exc_info.value.status_code == 404
    ), "Wrong error code retrieving deleted collection"


def test_add_user_to_non_existent_collection(client):
    # Create a regular user
    user_email = f"test_user_{uuid.uuid4()}@test.com"
    user_password = "test_password"
    client.users.create(user_email, user_password)
    client.users.login(user_email, user_password)
    user_id = client.users.me()["results"]["id"]
    client.users.logout()

    # Re-login as superuser to try adding user to a non-existent collection
    # (Assumes superuser credentials are already in the client fixture)
    fake_collection_id = str(uuid.uuid4())  # Non-existent collection ID
    with pytest.raises(R2RException) as exc_info:
        result = client.collections.add_user(fake_collection_id, user_id)
        print("result = ", result)
    assert (
        exc_info.value.status_code == 404
    ), "Wrong error code for non-existent collection"


# def test_remove_non_member_user_from_collection_duplicate(client):
#     # Similar to the previous non-member removal test but just to ensure coverage.
#     owner_email = f"owner_{uuid.uuid4()}@test.com"
#     owner_password = "password123"
#     client.users.create(owner_email, owner_password)
#     client.users.login(owner_email, owner_password)

#     # Create a collection by this owner
#     coll = client.collections.create(name="Another Non-member Test")["results"]
#     collection_id = coll["id"]

#     # Create another user who will NOT be added
#     other_user_email = f"other_{uuid.uuid4()}@test.com"
#     other_password = "password456"
#     client.users.create(other_user_email, other_password)
#     client.users.login(other_user_email, other_password)
#     other_user_id = client.users.me()["results"]["id"]
#     client.users.logout()

#     # Re-login as collection owner
#     client.users.login(owner_email, owner_password)

#     # Attempt to remove non-member
#     with pytest.raises(R2RException) as exc_info:
#         client.collections.remove_user(collection_id, other_user_id)
#     assert exc_info.value.status_code in [400, 404], "Wrong error code for removing non-member user"

#     # Cleanup
#     client.collections.delete(collection_id)


def test_create_collection_without_name(client):
    # Attempt to create a collection without a name
    with pytest.raises(R2RException) as exc_info:
        client.collections.create(name="", description="No name")
    # TODO - Error should be a 400 or 422, not 409
    assert exc_info.value.status_code in [
        400,
        422,
        409,
    ], "Expected validation error for empty name"


def test_create_collection_with_invalid_data(client):
    # Placeholder: If your API supports different data validation,
    # you'd try invalid inputs here. If strongly typed, this might not be feasible.
    # For now, we skip since the example client might prevent invalid data from being sent.
    pass


def test_filter_collections_by_non_existent_id(client):
    # Filter collections by an ID that does not exist
    random_id = str(uuid.uuid4())
    resp = client.collections.list(ids=[random_id])
    assert (
        len(resp["results"]) == 0
    ), "Expected no collections for a non-existent ID"


def test_list_documents_in_empty_collection(client):
    # Create a new collection with no documents
    resp = client.collections.create(name="Empty Collection")["results"]
    empty_coll_id = resp["id"]
    docs = client.collections.list_documents(empty_coll_id)["results"]
    assert len(docs) == 0, "Expected no documents in a new empty collection"
    client.collections.delete(empty_coll_id)


def test_remove_document_not_in_collection(client, test_document):
    # Create collection without adding the test_document
    resp = client.collections.create(name="NoDocCollection")["results"]
    coll_id = resp["id"]

    # Try removing the test_document that was never added
    with pytest.raises(R2RException) as exc_info:
        client.collections.remove_document(coll_id, test_document)
    # Expect 404 or 400 since doc not in collection
    assert exc_info.value.status_code in [
        400,
        404,
    ], "Expected error removing doc not in collection"
    client.collections.delete(coll_id)


def test_add_non_existent_document_to_collection(client):
    # Create a collection
    resp = client.collections.create(name="AddNonExistentDoc")["results"]
    coll_id = resp["id"]

    # Try adding a non-existent document
    fake_doc_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.collections.add_document(coll_id, fake_doc_id)
    assert exc_info.value.status_code in [
        400,
        404,
    ], "Expected error adding non-existent document"
    client.collections.delete(coll_id)


def test_delete_non_existent_collection(client):
    # Try deleting a collection that doesn't exist
    fake_collection_id = str(uuid.uuid4())
    with pytest.raises(R2RException) as exc_info:
        client.collections.delete(fake_collection_id)
    assert (
        exc_info.value.status_code == 404
    ), "Expected 404 when deleting non-existent collection"
