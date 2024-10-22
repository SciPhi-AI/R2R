# tests/providers/database/relational/test_user_db.py
from datetime import datetime, timedelta
from uuid import UUID

import pytest

from core.base.api.models import UserResponse


@pytest.mark.asyncio
async def test_create_user(temporary_postgres_db_provider):
    user = await temporary_postgres_db_provider.create_user(
        "test@example.com", "password"
    )
    assert isinstance(user, UserResponse)
    assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_get_user_by_id(temporary_postgres_db_provider):
    user = await temporary_postgres_db_provider.create_user(
        "test@example.com", "password"
    )
    retrieved_user = await temporary_postgres_db_provider.get_user_by_id(
        user.id
    )
    assert retrieved_user == user


@pytest.mark.asyncio
async def test_get_user_by_email(temporary_postgres_db_provider):
    user = await temporary_postgres_db_provider.create_user(
        "test@example.com", "password"
    )
    retrieved_user = await temporary_postgres_db_provider.get_user_by_email(
        "test@example.com"
    )
    assert retrieved_user == user


@pytest.mark.asyncio
async def test_delete_user(temporary_postgres_db_provider):
    user = await temporary_postgres_db_provider.create_user(
        "test@example.com", "password"
    )
    await temporary_postgres_db_provider.delete_user_relational(user.id)
    await temporary_postgres_db_provider.delete_user_vector(user.id)
    try:
        user = await temporary_postgres_db_provider.get_user_by_id(user.id)
        raise ValueError("User should not exist")
    except:
        pass


@pytest.mark.asyncio
async def test_update_user(temporary_postgres_db_provider):
    user = await temporary_postgres_db_provider.create_user(
        "test@example.com", "password"
    )
    updated_user = UserResponse(
        id=user.id,
        email="updated@example.com",
        is_superuser=True,
        is_active=False,
        is_verified=True,
        name="Updated Name",
        profile_picture="updated_picture.jpg",
        bio="Updated bio",
        collection_ids=[],
    )
    result = await temporary_postgres_db_provider.update_user(updated_user)
    assert result.email == updated_user.email


@pytest.mark.asyncio
async def test_update_user_password(temporary_postgres_db_provider):
    user = await temporary_postgres_db_provider.create_user(
        "test@example.com", "password"
    )
    await temporary_postgres_db_provider.update_user_password(
        user.id, "new_password"
    )
    # Additional assertions can be added based on the expected behavior


@pytest.mark.asyncio
async def test_get_all_users(temporary_postgres_db_provider):
    await temporary_postgres_db_provider.create_user(
        "test1@example.com", "password"
    )
    await temporary_postgres_db_provider.create_user(
        "test2@example.com", "password"
    )
    users = await temporary_postgres_db_provider.get_all_users()
    assert len(users) >= 2
    assert any(user.email == "test1@example.com" for user in users)
    assert any(user.email == "test2@example.com" for user in users)


@pytest.mark.asyncio
async def test_store_and_verify_verification_code(
    temporary_postgres_db_provider,
):
    user = await temporary_postgres_db_provider.create_user(
        "test@example.com", "password"
    )
    verification_code = "123456"
    expiry = datetime.utcnow() + timedelta(hours=1)
    await temporary_postgres_db_provider.store_verification_code(
        user.id, verification_code, expiry
    )
    await temporary_postgres_db_provider.verify_user(verification_code)
    updated_user = await temporary_postgres_db_provider.get_user_by_id(user.id)
    assert updated_user.is_verified


@pytest.mark.asyncio
async def test_store_and_get_reset_token(temporary_postgres_db_provider):
    user = await temporary_postgres_db_provider.create_user(
        "test@example.com", "password"
    )
    reset_token = "reset_token"
    expiry = datetime.utcnow() + timedelta(hours=1)
    await temporary_postgres_db_provider.store_reset_token(
        user.id, reset_token, expiry
    )
    user_id = await temporary_postgres_db_provider.get_user_id_by_reset_token(
        reset_token
    )
    assert user_id == user.id


@pytest.mark.asyncio
async def test_add_and_remove_user_from_collection(
    temporary_postgres_db_provider,
):
    user = await temporary_postgres_db_provider.create_user(
        "test@example.com", "password"
    )
    collection_id = UUID("00000000-0000-0000-0000-000000000001")
    await temporary_postgres_db_provider.add_user_to_collection(
        user.id, collection_id
    )
    updated_user = await temporary_postgres_db_provider.get_user_by_id(user.id)
    assert collection_id in updated_user.collection_ids
    await temporary_postgres_db_provider.remove_user_from_collection(
        user.id, collection_id
    )
    updated_user = await temporary_postgres_db_provider.get_user_by_id(user.id)
    assert collection_id not in updated_user.collection_ids
