import random
from datetime import datetime
from uuid import UUID

import pytest

from core import DatabaseConfig, R2RException
from core.base.abstractions import DocumentInfo, DocumentStatus, DocumentType
from core.providers import BCryptConfig, BCryptProvider, PostgresDBProvider


# Add this fixture to create test documents
@pytest.fixture
def test_documents(pg_db, test_group):
    documents = []
    for i in range(5):
        doc = DocumentInfo(
            id=UUID(f"00000000-0000-0000-0000-{i:012d}"),
            group_ids=[test_group.group_id],
            user_id=UUID("00000000-0000-0000-0000-000000000000"),
            type=DocumentType.PDF,
            metadata={},
            title=f"Test Document {i}",
            version="1.0",
            size_in_bytes=1000,
            status=DocumentStatus.PROCESSING,
        )
        pg_db.relational.upsert_documents_overview([doc])
        documents.append(doc)
    yield documents
    # Clean up documents after the test
    for doc in documents:
        pg_db.relational.delete_from_documents_overview(doc.id)


# Fixture for PostgresDBProvider
@pytest.fixture(scope="function")
def pg_db():
    config = DatabaseConfig.create(
        provider="postgres",
        vecs_collection=f"test_collection_{random.randint(1, 1_000_000_000_000_000_000)}",
    )
    crypto_provider = BCryptProvider(BCryptConfig())
    db = PostgresDBProvider(
        config, dimension=3, crypto_provider=crypto_provider
    )
    yield db
    # Teardown
    db.vx.delete_collection(db.collection_name)


# Improvement: Use a fixture for creating a test group
@pytest.fixture
def test_group(pg_db):
    group = pg_db.relational.create_group(
        "Test Group", "This is a test group."
    )
    yield group
    pg_db.relational.delete_group(group.group_id)


# Improvement: Use a fixture for creating a test user
@pytest.fixture
def test_user(pg_db):

    created_user = pg_db.relational.create_user(
        email=f"test_{datetime.now().timestamp()}@example.com",
        password="password",
    )
    yield created_user
    pg_db.relational.delete_user(created_user.id)


def test_create_group(pg_db):
    group_name = "Test Group"
    group_description = "This is a test group."
    group = pg_db.relational.create_group(
        name=group_name, description=group_description
    )
    assert isinstance(group.group_id, UUID)
    assert group.name == group_name
    assert group.description == group_description
    # Improvement: Check for created_at and updated_at fields
    assert isinstance(group.created_at, datetime)
    assert isinstance(group.updated_at, datetime)


def test_get_group(pg_db, test_group):
    fetched_group = pg_db.relational.get_group(test_group.group_id)
    assert fetched_group == test_group


def test_update_group(pg_db, test_group):
    new_name = "Updated Group"
    new_description = "This is an updated test group."
    updated = pg_db.relational.update_group(
        test_group.group_id, name=new_name, description=new_description
    )
    assert updated
    fetched_group = pg_db.relational.get_group(test_group.group_id)
    assert fetched_group.name == new_name
    assert fetched_group.description == new_description
    # Improvement: Check that updated_at has changed
    assert fetched_group.updated_at > test_group.updated_at


def test_delete_group(pg_db):
    group = pg_db.relational.create_group(
        "Temporary Group", "This group will be deleted"
    )
    pg_db.relational.delete_group(group.group_id)
    with pytest.raises(R2RException):
        fetched_group = pg_db.relational.get_group(group.group_id)


def test_list_groups(pg_db, test_group):
    # First, ensure we have at least two groups
    second_group = pg_db.relational.create_group(
        "Second Test Group", "This is another test group."
    )

    # Now test listing groups
    groups = pg_db.relational.list_groups()
    assert len(groups) >= 2
    assert any(group.group_id == test_group.group_id for group in groups)
    assert any(group.group_id == second_group.group_id for group in groups)

    # Test pagination
    first_page = pg_db.relational.list_groups(limit=1)
    assert len(first_page) == 1
    second_page = pg_db.relational.list_groups(offset=1, limit=1)
    assert len(second_page) == 1

    # Ensure first and second pages are different
    assert first_page[0].group_id != second_page[0].group_id

    # Test requesting more groups than exist
    all_groups = pg_db.relational.list_groups(limit=1000)
    assert len(all_groups) >= 2

    # Clean up the second group
    pg_db.relational.delete_group(second_group.group_id)


def test_add_user_to_group(pg_db, test_group, test_user):
    added = pg_db.relational.add_user_to_group(
        test_user.id, test_group.group_id
    )
    user_groups = pg_db.relational.get_groups_for_user(test_user.id)
    assert any(g.group_id == test_group.group_id for g in user_groups)

    test_group = pg_db.relational.create_group(
        "Another Group", "Another test group"
    )
    # # Improvement: Test adding the same user twice
    pg_db.relational.add_user_to_group(test_user.id, test_group.group_id)


def test_remove_user_from_group(pg_db, test_group, test_user):
    # TODO - modify this test to use a fixture for creating a test group
    test_group_ = pg_db.relational.create_group(
        "Another Group", "Another test group"
    )

    pg_db.relational.add_user_to_group(test_user.id, test_group_.group_id)
    removed = pg_db.relational.remove_user_from_group(
        test_user.id, test_group_.group_id
    )
    user_groups = pg_db.relational.get_groups_for_user(test_user.id)
    assert all(g.group_id != test_group_.group_id for g in user_groups)
    # Improvement: Test removing a user that's not in the group
    with pytest.raises(R2RException):
        pg_db.relational.remove_user_from_group(
            test_user.id, test_group_.group_id
        )


def test_get_users_in_group(pg_db, test_group, test_user):
    pg_db.relational.add_user_to_group(test_user.id, test_group.group_id)
    users_in_group = pg_db.relational.get_users_in_group(test_group.group_id)
    assert any(u.id == test_user.id for u in users_in_group)
    # Improvement: Test pagination
    first_page = pg_db.relational.get_users_in_group(
        test_group.group_id, limit=1
    )
    assert len(first_page) == 1


def test_get_all_groups(pg_db, test_group):
    # Create multiple groups
    group1 = pg_db.relational.create_group("Group 1", "Description 1")
    group2 = pg_db.relational.create_group("Group 2", "Description 2")

    all_groups = pg_db.relational.list_groups()

    assert len(all_groups) >= 3  # Including test_group
    assert any(g.group_id == test_group.group_id for g in all_groups)
    assert any(g.group_id == group1.group_id for g in all_groups)
    assert any(g.group_id == group2.group_id for g in all_groups)


def test_get_groups_by_ids(pg_db):
    group1 = pg_db.relational.create_group("Group 1", "Description 1")
    group2 = pg_db.relational.create_group("Group 2", "Description 2")

    groups = pg_db.relational.get_groups_by_ids(
        [group1.group_id, group2.group_id]
    )

    assert len(groups) == 2
    assert any(g.group_id == group1.group_id for g in groups)
    assert any(g.group_id == group2.group_id for g in groups)


def test_get_groups_overview(pg_db, test_group, test_user):
    pg_db.relational.add_user_to_group(test_user.id, test_group.group_id)

    overview = pg_db.relational.get_groups_overview([test_group.group_id])

    assert len(overview) == 1
    assert overview[0].group_id == test_group.group_id
    assert overview[0].name == test_group.name
    assert overview[0].description == test_group.description
    assert overview[0].user_count == 1


# Test for adding the same user twice (idempotency)
def test_add_user_to_group_idempotency(pg_db, test_group, test_user):
    # Add user for the first time
    added1 = pg_db.relational.add_user_to_group(
        test_user.id, test_group.group_id
    )
    assert added1

    # Try to add the same user again
    added2 = pg_db.relational.add_user_to_group(
        test_user.id, test_group.group_id
    )
    assert not added2  # Should return False as user is already in the group

    # Verify user is in the group only once
    users_in_group = pg_db.relational.get_users_in_group(test_group.group_id)
    assert len([u for u in users_in_group if u.id == test_user.id]) == 1


# Test for removing a user that's not in the group
def test_remove_user_not_in_group(pg_db, test_group, test_user):
    # Ensure user is not in the group
    pg_db.relational.add_user_to_group(test_user.id, test_group.group_id)
    pg_db.relational.remove_user_from_group(test_user.id, test_group.group_id)

    # Try to remove the user again
    with pytest.raises(R2RException):
        pg_db.relational.remove_user_from_group(
            test_user.id, test_group.group_id
        )


# Improvement: Add test for non-existent group and user
def test_edge_cases(pg_db):
    non_existent_id = UUID("00000000-0000-0000-0000-000000000000")
    # assert pg_db.relational.get_group(non_existent_id) is None
    # ensure error
    with pytest.raises(R2RException):
        pg_db.relational.get_group(non_existent_id)
    with pytest.raises(R2RException):
        pg_db.relational.update_group(
            non_existent_id, name="New Name", description="New Description"
        )
    with pytest.raises(R2RException):
        pg_db.relational.delete_group(non_existent_id)
    with pytest.raises(R2RException):
        pg_db.relational.add_user_to_group(non_existent_id, non_existent_id)
    with pytest.raises(R2RException):
        assert not pg_db.relational.remove_user_from_group(
            non_existent_id, non_existent_id
        )
    with pytest.raises(R2RException):
        assert pg_db.relational.get_users_in_group(non_existent_id) == []


def test_get_users_in_group_with_pagination(pg_db, test_group):
    # Create multiple users and add them to the group
    users = []
    for i in range(5):
        user = pg_db.relational.create_user(
            email=f"test_user_{i}@example.com", password="password"
        )
        pg_db.relational.add_user_to_group(user.id, test_group.group_id)
        users.append(user)

    # Test first page
    first_page = pg_db.relational.get_users_in_group(
        test_group.group_id, offset=0, limit=3
    )
    assert len(first_page) == 3

    # Test second page
    second_page = pg_db.relational.get_users_in_group(
        test_group.group_id, offset=3, limit=3
    )
    assert len(second_page) == 2

    # Ensure all users are different
    all_users = first_page + second_page
    assert len(set(u.id for u in all_users)) == 5

    # Clean up
    for user in users:
        pg_db.relational.delete_user(user.id)


def test_get_groups_overview_with_pagination(pg_db):
    # Create multiple groups
    groups = [
        pg_db.relational.create_group(f"Group {i}", f"Description {i}")
        for i in range(5)
    ]

    # Test first page
    first_page = pg_db.relational.get_groups_overview(offset=0, limit=3)
    assert len(first_page) == 3

    # Test second page
    second_page = pg_db.relational.get_groups_overview(offset=3, limit=3)
    assert len(second_page) == 2

    # Ensure all groups are different
    all_groups = first_page + second_page
    assert len(set(g.group_id for g in all_groups)) == 5

    # Clean up
    for group in groups:
        pg_db.relational.delete_group(group.group_id)


def test_get_groups_for_user_with_pagination(pg_db, test_user):
    # Create multiple groups and add the user to them
    groups = []
    for i in range(5):
        group = pg_db.relational.create_group(f"Group {i}", f"Description {i}")
        pg_db.relational.add_user_to_group(test_user.id, group.group_id)
        groups.append(group)

    # Test first page
    first_page = pg_db.relational.get_groups_for_user(
        test_user.id, offset=0, limit=3
    )
    assert len(first_page) == 3

    # Test second page
    second_page = pg_db.relational.get_groups_for_user(
        test_user.id, offset=3, limit=3
    )
    assert len(second_page) == 2

    # Ensure all groups are different
    all_groups = first_page + second_page
    assert len(set(g.group_id for g in all_groups)) == 5

    # Clean up
    for group in groups:
        pg_db.relational.delete_group(group.group_id)


def test_documents_in_group(pg_db, test_group, test_documents):
    # Test getting all documents
    all_docs = pg_db.relational.documents_in_group(test_group.group_id)
    assert len(all_docs) == 5
    assert all(isinstance(doc, DocumentInfo) for doc in all_docs)
    assert all(test_group.group_id in doc.group_ids for doc in all_docs)

    # Test pagination - first page
    first_page = pg_db.relational.documents_in_group(
        test_group.group_id, offset=0, limit=3
    )
    assert len(first_page) == 3

    # Test pagination - second page
    second_page = pg_db.relational.documents_in_group(
        test_group.group_id, offset=3, limit=3
    )
    assert len(second_page) == 2

    # Ensure all documents are different
    all_docs = first_page + second_page
    assert len(set(doc.id for doc in all_docs)) == 5

    # Test ordering (should be in descending order of created_at)
    assert all(
        all_docs[i].created_at >= all_docs[i + 1].created_at
        for i in range(len(all_docs) - 1)
    )

    # Test with non-existent group
    non_existent_id = UUID("00000000-0000-0000-0000-000000000000")
    with pytest.raises(R2RException):
        pg_db.relational.documents_in_group(non_existent_id)

    # Test with empty group
    empty_group = pg_db.relational.create_group("Empty Group", "No documents")
    empty_docs = pg_db.relational.documents_in_group(empty_group.group_id)
    assert len(empty_docs) == 0

    # Clean up
    pg_db.relational.delete_group(empty_group.group_id)
