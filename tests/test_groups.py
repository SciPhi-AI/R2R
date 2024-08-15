from datetime import datetime
from uuid import UUID

import pytest

from r2r import DatabaseConfig, R2RException
from r2r.providers import BCryptConfig, BCryptProvider, PostgresDBProvider


# Fixture for PostgresDBProvider
@pytest.fixture(scope="module")
def pg_db():
    config = DatabaseConfig.create(
        provider="postgres",
        vecs_collection=f"test_collection_{int(datetime.now().timestamp())}",
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
    assert added
    user_groups = pg_db.relational.get_groups_for_user(test_user.id)
    assert any(g["group_id"] == test_group.group_id for g in user_groups)

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
    assert removed
    user_groups = pg_db.relational.get_groups_for_user(test_user.id)
    assert all(g["group_id"] != test_group_.group_id for g in user_groups)
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


# Improvement: Add test for non-existent group and user
def test_edge_cases(pg_db):
    non_existent_id = UUID("00000000-0000-0000-0000-000000000000")
    # assert pg_db.relational.get_group(non_existent_id) is None
    # ensure error
    with pytest.raises(R2RException):
        pg_db.relational.get_group(non_existent_id)
    with pytest.raises(R2RException):
        pg_db.relational.update_group(non_existent_id, name="New Name")
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
