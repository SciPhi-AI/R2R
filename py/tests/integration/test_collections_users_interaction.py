import uuid

import pytest

from r2r import R2RClient, R2RException

# @pytest.fixture  # (scope="session")
# def client(config):
#     """A client logged in as a superuser."""
#     client = R2RClient(config.base_url)
#     client.users.login(config.superuser_email, config.superuser_password)
#     yield client


@pytest.fixture
def normal_user_client(mutable_client: R2RClient):
    """Create a normal user and log in with that user."""
    # client = R2RClient(config.base_url)

    email = f"normal_{uuid.uuid4()}@test.com"
    password = "normal_password"
    user_resp = mutable_client.users.create(email, password)
    mutable_client.users.login(email, password)

    yield mutable_client

    # Cleanup: Try deleting the normal user if exists
    try:
        mutable_client.users.login(email, password)
        mutable_client.users.delete(id=mutable_client.users.me().results.id,
                                    password=password)
    except R2RException:
        pass


@pytest.fixture
def another_normal_user_client(config):
    """Create another normal user and log in with that user."""
    client = R2RClient(config.base_url)

    email = f"another_{uuid.uuid4()}@test.com"
    password = "another_password"
    user_resp = client.users.create(email, password)
    client.users.login(email, password)
    yield client

    # Cleanup: Try deleting the user if exists
    try:
        client.users.login(email, password)
        client.users.delete(id=client.users.me().results.id, password=password)
    except R2RException:
        pass


@pytest.fixture
def user_owned_collection(normal_user_client: R2RClient):
    """Create a collection owned by the normal user."""
    coll_id = normal_user_client.collections.create(
        name="User Owned Collection",
        description="A collection owned by a normal user",
    ).results.id

    yield coll_id
    # Cleanup
    try:
        normal_user_client.collections.delete(coll_id)
    except R2RException:
        pass


@pytest.fixture
def superuser_owned_collection(client: R2RClient):
    """Create a collection owned by the superuser."""
    collection_id = client.collections.create(
        name="Superuser Owned Collection",
        description="A collection owned by superuser",
    ).results.id
    yield collection_id
    # Cleanup
    try:
        client.collections.delete(collection_id)
    except R2RException:
        pass


def test_non_member_cannot_view_collection(normal_user_client,
                                           superuser_owned_collection):
    """A normal user (not a member of a superuser-owned collection) tries to
    view it."""
    # The normal user is not added to the superuser collection, should fail
    with pytest.raises(R2RException) as exc_info:
        normal_user_client.collections.retrieve(superuser_owned_collection)
    assert exc_info.value.status_code == 403, (
        "Non-member should not be able to view collection.")


def test_collection_owner_can_view_collection(normal_user_client: R2RClient,
                                              user_owned_collection):
    """The owner should be able to view their own collection."""
    coll = normal_user_client.collections.retrieve(
        user_owned_collection).results
    assert coll.id == user_owned_collection, (
        "Owner cannot view their own collection.")


def test_collection_member_can_view_collection(client,
                                               normal_user_client: R2RClient,
                                               user_owned_collection):
    """A user added to a collection should be able to view it."""
    # Create another user and add them to the user's collection
    new_user_email = f"temp_member_{uuid.uuid4()}@test.com"
    new_user_password = "temp_member_password"

    # Store normal user's email before any logouts
    normal_user_email = normal_user_client.users.me().results.email

    # Create a new user and log in as them
    member_client = R2RClient(normal_user_client.base_url)
    member_client.users.create(new_user_email, new_user_password)
    member_client.users.login(new_user_email, new_user_password)
    member_id = member_client.users.me().results.id

    # Owner adds the new user to the collection
    normal_user_client.users.logout()
    normal_user_client.users.login(normal_user_email, "normal_password")

    normal_user_client.collections.add_user(user_owned_collection, member_id)

    # The member now can view the collection
    coll = member_client.collections.retrieve(user_owned_collection).results
    assert coll.id == user_owned_collection


def test_non_owner_member_cannot_edit_collection(
    user_owned_collection,
    another_normal_user_client: R2RClient,
    normal_user_client: R2RClient,
):
    """A member who is not the owner should not be able to edit the
    collection."""
    # Add another normal user to the owner's collection
    another_user_id = another_normal_user_client.users.me().results.id
    normal_user_client.collections.add_user(user_owned_collection,
                                            another_user_id)

    # Another normal user tries to update collection
    with pytest.raises(R2RException) as exc_info:
        another_normal_user_client.collections.update(user_owned_collection,
                                                      name="Malicious Update")
    assert exc_info.value.status_code == 403, (
        "Non-owner member should not be able to edit.")


def test_non_owner_member_cannot_delete_collection(
    user_owned_collection,
    another_normal_user_client: R2RClient,
    normal_user_client: R2RClient,
):
    """A member who is not the owner should not be able to delete the
    collection."""
    # Add the other user
    another_user_id = another_normal_user_client.users.me().results.id
    normal_user_client.collections.add_user(user_owned_collection,
                                            another_user_id)

    # Another user tries to delete
    with pytest.raises(R2RException) as exc_info:
        another_normal_user_client.collections.delete(user_owned_collection)
    assert exc_info.value.status_code == 403, (
        "Non-owner member should not be able to delete.")


def test_non_owner_member_cannot_add_other_users(
    user_owned_collection,
    another_normal_user_client: R2RClient,
    normal_user_client: R2RClient,
):
    """A member who is not the owner should not be able to add other users."""
    # Another user tries to add a third user
    third_email = f"third_user_{uuid.uuid4()}@test.com"
    third_password = "third_password"
    # Need to create third user as a superuser or owner
    normal_user_email = normal_user_client.users.me().results.email
    normal_user_client.users.logout()

    # Login as normal user again
    # NOTE: We assume normal_password known here; in a real scenario, store it or use fixtures more dynamically
    # This code snippet assumes we have these credentials available.
    # If not, manage credentials store in fixture creation.
    normal_user_client.users.login(normal_user_email, "normal_password")
    third_user_id = normal_user_client.users.create(third_email,
                                                    third_password).results.id

    # Add another user as a member
    another_user_id = another_normal_user_client.users.me().results.id
    normal_user_client.collections.add_user(user_owned_collection,
                                            another_user_id)

    # Now, another_normal_user_client tries to add the third user
    with pytest.raises(R2RException) as exc_info:
        another_normal_user_client.collections.add_user(
            user_owned_collection, third_user_id)
    assert exc_info.value.status_code == 403, (
        "Non-owner member should not be able to add users.")


def test_owner_can_remove_member_from_collection(
    user_owned_collection,
    another_normal_user_client: R2RClient,
    normal_user_client: R2RClient,
):
    """The owner should be able to remove a member from their collection."""
    # Add another user to the collection
    another_user_id = another_normal_user_client.users.me().results.id
    normal_user_client.collections.add_user(user_owned_collection,
                                            another_user_id)

    # Remove them
    remove_resp = normal_user_client.collections.remove_user(
        user_owned_collection, another_user_id).results
    assert remove_resp.success, "Owner could not remove member."

    # The removed user should no longer have access
    with pytest.raises(R2RException) as exc_info:
        another_normal_user_client.collections.retrieve(user_owned_collection)
    assert exc_info.value.status_code == 403, (
        "Removed user still has access after removal.")


def test_superuser_can_access_any_collection(client: R2RClient,
                                             user_owned_collection):
    """A superuser should be able to view and edit any collection."""
    # Superuser can view
    coll = client.collections.retrieve(user_owned_collection).results
    assert coll.id == user_owned_collection, (
        "Superuser cannot view a user collection.")

    # Superuser can also update
    updated = client.collections.update(user_owned_collection,
                                        name="Superuser Edit").results
    assert updated.name == "Superuser Edit", (
        "Superuser cannot edit collection.")


def test_unauthenticated_cannot_access_collections(config,
                                                   user_owned_collection):
    """An unauthenticated (no login) client should not access protected
    endpoints."""
    unauth_client = R2RClient(config.base_url)
    # we must CREATE + LOGIN as superuser is default user for unauth in basic config
    user_name = f"unauth_user_{uuid.uuid4()}@email.com"
    unauth_client.users.create(user_name, "unauth_password")
    unauth_client.users.login(user_name, "unauth_password")
    with pytest.raises(R2RException) as exc_info:
        unauth_client.collections.retrieve(user_owned_collection)
    assert exc_info.value.status_code == 403, (
        "Unaurthorized user should get 403")


def test_user_cannot_add_document_to_collection_they_cannot_edit(
        client: R2RClient, normal_user_client: R2RClient):
    """A normal user who is just a member (not owner) of a collection should
    not be able to add documents."""
    # Create a collection as normal user (owner)
    coll_id = normal_user_client.collections.create(
        name="Owned by user", description="desc").results.id

    # Create a second user and add them as member
    second_email = f"second_{uuid.uuid4()}@test.com"
    second_password = "pwd"
    client.users.logout()
    second_client = R2RClient(normal_user_client.base_url)
    second_client.users.create(second_email, second_password)
    second_client.users.login(second_email, second_password)
    second_id = second_client.users.me().results.id

    # Owner adds second user as a member
    email_of_normal_user = normal_user_client.users.me().results.email
    normal_user_client.users.logout()
    # Re-login owner (assuming we stored the original user's creds)
    # For demonstration, we assume we know the normal_user_client creds or re-use fixtures carefully.
    # In a real test environment, you'd maintain credentials more robustly.
    # Here we rely on the normal_user_client fixture being re-instantiated per test if needed.
    normal_user_client.users.login(email_of_normal_user, "normal_password")
    normal_user_client.collections.add_user(coll_id, second_id)

    # Create a document as owner
    doc_id = normal_user_client.documents.create(
        raw_text="Test Document").results.document_id

    # Now second user tries to add another document (which they do not have edit rights for)
    second_client.users.logout()
    second_client.users.login(second_email, second_password)
    # Another doc created by second user (just for attempt)
    doc2_id = second_client.documents.create(
        raw_text="Doc by second user").results.document_id

    # Second user tries to add their doc2_id to the owner’s collection
    with pytest.raises(R2RException) as exc_info:
        second_client.collections.add_document(coll_id, doc2_id)
    assert exc_info.value.status_code == 403, (
        "Non-owner member should not add documents.")

    # Cleanup
    normal_user_client.collections.delete(coll_id)
    normal_user_client.documents.delete(doc_id)
    second_client.documents.delete(doc2_id)


def test_user_cannot_remove_document_from_collection_they_cannot_edit(
    normal_user_client: R2RClient, ):
    """A user who is just a member should not remove documents."""
    # Create a collection
    coll_id = normal_user_client.collections.create(
        name="Removable", description="desc").results.id

    # Create a document in it
    doc_id = normal_user_client.documents.create(
        raw_text="Doc in coll").results.document_id
    normal_user_client.collections.add_document(coll_id, doc_id)

    # Create another user and add as member
    another_email = f"amember_{uuid.uuid4()}@test.com"
    another_password = "memberpwd"
    member_client = R2RClient(normal_user_client.base_url)
    member_client.users.create(another_email, another_password)
    member_client.users.login(another_email, another_password)
    member_id = member_client.users.me().results.id
    user_email = normal_user_client.users.me().results.email

    # Add member to collection
    normal_user_client.users.logout()
    normal_user_client.users.login(user_email, "normal_password")
    normal_user_client.collections.add_user(coll_id, member_id)

    # Member tries to remove the document
    with pytest.raises(R2RException) as exc_info:
        member_client.collections.remove_document(coll_id, doc_id)
    assert exc_info.value.status_code == 403, (
        "Member should not remove documents.")

    # Cleanup
    normal_user_client.collections.delete(coll_id)


def test_normal_user_cannot_make_another_user_superuser(
    normal_user_client: R2RClient, ):
    """A normal user tries to update another user to superuser, should fail."""
    # Create another user
    email = f"regular_{uuid.uuid4()}@test.com"
    password = "not_superuser"
    new_user_id = normal_user_client.users.create(email, password).results.id

    # Try updating their superuser status
    with pytest.raises(R2RException) as exc_info:
        normal_user_client.users.update(new_user_id, is_superuser=True)
    assert exc_info.value.status_code == 403, (
        "Non-superuser should not grant superuser status.")


def test_normal_user_cannot_view_other_users_if_not_superuser(
    normal_user_client: R2RClient, ):
    """A normal user tries to list all users, should fail."""
    with pytest.raises(R2RException) as exc_info:
        normal_user_client.users.list()
    assert exc_info.value.status_code == 403, (
        "Non-superuser should not list all users.")


def test_normal_user_cannot_update_other_users_details(
        normal_user_client: R2RClient, client: R2RClient):
    """A normal user tries to update another normal user's details."""
    # Create another normal user
    email = f"other_normal_{uuid.uuid4()}@test.com"
    password = "pwd123"
    client.users.logout()
    another_client = R2RClient(normal_user_client.base_url)
    another_client.users.create(email, password)
    another_client.users.login(email, password)
    another_user_id = another_client.users.me().results.id
    another_client.users.logout()

    # Try to update as first normal user (not superuser, not same user)
    with pytest.raises(R2RException) as exc_info:
        normal_user_client.users.update(another_user_id, name="Hacked Name")
    assert exc_info.value.status_code == 403, (
        "Non-superuser should not update another user's info.")


# Additional Tests for Strengthened Coverage


def test_owner_cannot_promote_member_to_superuser_via_collection(
    user_owned_collection,
    normal_user_client: R2RClient,
    another_normal_user_client: R2RClient,
):
    """Ensures that being a collection owner doesn't confer the right to
    promote a user to superuser."""
    # Add another user to the collection
    another_user_id = another_normal_user_client.users.me().results.id
    normal_user_client.collections.add_user(user_owned_collection,
                                            another_user_id)

    # Try to update the member's superuser status
    with pytest.raises(R2RException) as exc_info:
        normal_user_client.users.update(another_user_id, is_superuser=True)
    assert exc_info.value.status_code == 403, (
        "Collection owners should not grant superuser status.")


def test_member_cannot_view_other_users_info(
    user_owned_collection,
    normal_user_client: R2RClient,
    another_normal_user_client: R2RClient,
):
    """A member (non-owner) of a collection should not be able to retrieve
    other users' details outside of their allowed scope."""
    # Add the other normal user as a member
    another_user_id = another_normal_user_client.users.me().results.id
    normal_user_client.collections.add_user(user_owned_collection,
                                            another_user_id)

    # As another_normal_user_client (a member), try to retrieve owner user details
    owner_id = normal_user_client.users.me().results.id
    with pytest.raises(R2RException) as exc_info:
        another_normal_user_client.users.retrieve(owner_id)
    assert exc_info.value.status_code == 403, (
        "Members should not be able to view other users' details.")


def test_unauthenticated_user_cannot_join_collection(config,
                                                     user_owned_collection):
    """An unauthenticated user should not be able to join or view
    collections."""
    unauth_client = R2RClient(config.base_url)
    # we must CREATE + LOGIN as superuser is default user for unauth in basic config
    user_name = f"unauth_user_{uuid.uuid4()}@email.com"
    unauth_client.users.create(user_name, "unauth_password")
    unauth_client.users.login(user_name, "unauth_password")

    # No login performed here, client is unauthenticated
    with pytest.raises(R2RException) as exc_info:
        unauth_client.collections.retrieve(user_owned_collection)
    assert exc_info.value.status_code in [
        401,
        403,
    ], "Unauthenticated user should not access collections."


def test_non_owner_cannot_remove_users_they_did_not_add(
    user_owned_collection,
    normal_user_client: R2RClient,
    another_normal_user_client: R2RClient,
):
    """A member who is not the owner cannot remove other members from the
    collection."""
    # Add another user as a member
    another_user_id = another_normal_user_client.users.me().results.id
    normal_user_client.collections.add_user(user_owned_collection,
                                            another_user_id)

    # Now try removing that user as another_normal_user_client
    with pytest.raises(R2RException) as exc_info:
        another_normal_user_client.collections.remove_user(
            user_owned_collection, another_user_id)
    assert exc_info.value.status_code == 403, (
        "Non-owner member should not remove other users.")


def test_owner_cannot_access_deleted_member_info_after_removal(
    user_owned_collection,
    normal_user_client: R2RClient,
    another_normal_user_client: R2RClient,
):
    """After the owner removes a user from the collection, ensure that attempts
    to perform collection-specific actions with that user fail."""
    # Add another user to the collection
    another_user_id = another_normal_user_client.users.me().results.id
    normal_user_client.collections.add_user(user_owned_collection,
                                            another_user_id)

    # Remove them
    normal_user_client.collections.remove_user(user_owned_collection,
                                               another_user_id)

    # Now, try listing collections for that removed user (as owner),
    # if there's an endpoint that filters by user, to ensure no special access remains.
    # If no such endpoint exists, this test can be adapted to try another relevant action.
    # For demonstration, we might attempt to retrieve user details as owner:
    with pytest.raises(R2RException) as exc_info:
        normal_user_client.users.retrieve(another_user_id)
    # We expect a 403 because normal_user_client is not superuser and not that user.
    assert exc_info.value.status_code == 403, (
        "Owner should not access removed member's user info.")


def test_member_cannot_add_document_to_non_existent_collection(
    normal_user_client: R2RClient, ):
    """A member tries to add a document to a collection that doesn't exist."""
    fake_coll_id = str(uuid.uuid4())
    doc_id = normal_user_client.documents.create(
        raw_text="Test Doc").results.document_id
    with pytest.raises(R2RException) as exc_info:
        normal_user_client.collections.add_document(fake_coll_id, doc_id)
    assert exc_info.value.status_code in [
        400,
        404,
    ], "Expected error when adding doc to non-existent collection."

    normal_user_client.documents.delete(doc_id)
