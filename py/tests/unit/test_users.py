import pytest
import uuid
from datetime import datetime, timedelta
from core.base.abstractions import R2RException
from fastapi import HTTPException
from shared.abstractions import User


@pytest.mark.asyncio
async def test_create_user(users_handler):
    email = "test@example.com"
    password = "testpass"
    user = await users_handler.create_user(email=email, password=password)
    assert user.email == email
    assert user.is_active is True
    assert user.is_verified is False
    assert user.is_superuser is False
    assert user.collection_ids == []

    # Attempt creating a user with the same email should fail
    with pytest.raises(R2RException) as exc_info:
        await users_handler.create_user(email=email, password=password)
    assert "User with this email already exists" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_user_by_id(users_handler):
    user = await users_handler.create_user("unique@example.com", "pass")
    fetched = await users_handler.get_user_by_id(user.id)
    assert fetched.id == user.id
    assert fetched.email == "unique@example.com"


@pytest.mark.asyncio
async def test_get_user_by_email(users_handler):
    email = "byemail@example.com"
    await users_handler.create_user(email, "pass")
    fetched = await users_handler.get_user_by_email(email)
    assert fetched.email == email

    # Non-existent user
    with pytest.raises(R2RException):
        await users_handler.get_user_by_email("noone@nowhere.com")


@pytest.mark.asyncio
async def test_update_user(users_handler):
    email = "updateuser@example.com"
    user = await users_handler.create_user(email, "pass")
    user.name = "New Name"
    user.bio = "A bio"
    user.is_active = False  # deactivate user

    updated = await users_handler.update_user(user)
    assert updated.name == "New Name"
    assert updated.bio == "A bio"
    assert updated.is_active is False

    # Verify changes persist
    fetched = await users_handler.get_user_by_id(user.id)
    assert fetched.name == "New Name"
    assert fetched.bio == "A bio"
    assert fetched.is_active is False


@pytest.mark.asyncio
async def test_delete_user_relational(users_handler):
    email = "deleteuser@example.com"
    user = await users_handler.create_user(email, "password")
    await users_handler.delete_user_relational(user.id)

    # Try to get the user
    with pytest.raises(R2RException):
        await users_handler.get_user_by_id(user.id)


@pytest.mark.asyncio
async def test_update_user_password(users_handler, crypto_provider):
    email = "updatepw@example.com"
    user = await users_handler.create_user(email, "oldpass")
    new_hash = crypto_provider.get_password_hash("newpass")
    await users_handler.update_user_password(user.id, new_hash)

    fetched = await users_handler.get_user_by_id(user.id)
    assert fetched.hashed_password == new_hash


@pytest.mark.asyncio
async def test_verification_code_flow(users_handler):
    user = await users_handler.create_user("verif@example.com", "pass")
    code = "verify_code"
    expiry = datetime.utcnow() + timedelta(hours=1)

    await users_handler.store_verification_code(user.id, code, expiry)

    # Verify the user
    await users_handler.verify_user(code)
    verified_user = await users_handler.get_user_by_id(user.id)
    assert verified_user.is_verified is True


@pytest.mark.asyncio
async def test_verify_user_invalid_code(users_handler):
    # Non-existent code
    with pytest.raises(R2RException):
        await users_handler.verify_user("invalid_code")


@pytest.mark.asyncio
async def test_reset_token_flow(users_handler):
    user = await users_handler.create_user("reset@example.com", "pass")
    reset_token = "resetme"
    expiry = datetime.utcnow() + timedelta(hours=1)
    await users_handler.store_reset_token(user.id, reset_token, expiry)

    found_id = await users_handler.get_user_id_by_reset_token(reset_token)
    assert found_id == user.id

    # Remove reset token
    await users_handler.remove_reset_token(user.id)
    assert await users_handler.get_user_id_by_reset_token(reset_token) is None


@pytest.mark.asyncio
async def test_remove_user_from_all_collections(users_handler):
    # Create a user and manually assign collections
    user = await users_handler.create_user("collections@example.com", "pass")
    user.collection_ids = [uuid.uuid4(), uuid.uuid4()]
    updated = await users_handler.update_user(user)
    assert len(updated.collection_ids) == 2

    await users_handler.remove_user_from_all_collections(user.id)
    cleared_user = await users_handler.get_user_by_id(user.id)
    assert cleared_user.collection_ids == []


@pytest.mark.asyncio
async def test_add_user_to_collection(users_handler, mocker):
    # Mock _collection_exists to return True
    mocker.patch.object(users_handler, "_collection_exists", return_value=True)

    user = await users_handler.create_user("addcol@example.com", "pass")
    coll_id = uuid.uuid4()
    await users_handler.add_user_to_collection(user.id, coll_id)

    fetched = await users_handler.get_user_by_id(user.id)
    assert coll_id in fetched.collection_ids

    # Try adding again should raise R2RException
    with pytest.raises(R2RException) as exc_info:
        await users_handler.add_user_to_collection(user.id, coll_id)
    assert "User already in collection" in str(exc_info.value)


@pytest.mark.asyncio
async def test_remove_user_from_collection(users_handler, mocker):
    mocker.patch.object(users_handler, "_collection_exists", return_value=True)
    user = await users_handler.create_user("removecol@example.com", "pass")
    coll_id = uuid.uuid4()
    await users_handler.add_user_to_collection(user.id, coll_id)

    # Now remove
    await users_handler.remove_user_from_collection(user.id, coll_id)
    fetched = await users_handler.get_user_by_id(user.id)
    assert coll_id not in fetched.collection_ids

    # Removing again should fail
    with pytest.raises(R2RException) as exc_info:
        await users_handler.remove_user_from_collection(user.id, coll_id)
    assert "User is not a member of the specified collection" in str(
        exc_info.value
    )


@pytest.mark.asyncio
async def test_get_users_in_collection(users_handler, mocker):
    mocker.patch.object(users_handler, "_collection_exists", return_value=True)
    user1 = await users_handler.create_user("col1@example.com", "pass")
    user2 = await users_handler.create_user("col2@example.com", "pass")
    coll_id = uuid.uuid4()

    await users_handler.add_user_to_collection(user1.id, coll_id)
    await users_handler.add_user_to_collection(user2.id, coll_id)

    data = await users_handler.get_users_in_collection(
        collection_id=coll_id, offset=0, limit=10
    )
    assert data["total_entries"] == 2
    emails = [u.email for u in data["results"]]
    assert "col1@example.com" in emails
    assert "col2@example.com" in emails


@pytest.mark.asyncio
async def test_mark_user_as_superuser(users_handler):
    user = await users_handler.create_user("super@example.com", "pass")
    await users_handler.mark_user_as_superuser(user.id)
    updated = await users_handler.get_user_by_id(user.id)
    assert updated.is_superuser is True
    assert updated.is_verified is True


@pytest.mark.asyncio
async def test_get_user_validation_data(users_handler):
    user = await users_handler.create_user("validate@example.com", "pass")
    code = "validate_code"
    expiry = datetime.utcnow() + timedelta(hours=1)
    await users_handler.store_verification_code(user.id, code, expiry)

    data = await users_handler.get_user_validation_data(user.id)
    assert data["verification_data"]["verification_code"] == code
    assert data["verification_data"]["verification_code_expiry"] is not None
    assert data["verification_data"]["reset_token"] is None


@pytest.mark.asyncio
async def test_api_keys(users_handler):
    user = await users_handler.create_user("apikey@example.com", "pass")
    key_id = "public_key_id"
    hashed_key = "hashed_key_value"

    key_uuid = await users_handler.store_user_api_key(
        user.id, key_id, hashed_key, name="My API Key"
    )
    assert isinstance(key_uuid, uuid.UUID)

    # Retrieve api keys
    keys = await users_handler.get_user_api_keys(user.id)
    assert len(keys) == 1
    assert keys[0]["public_key"] == key_id

    # Get API key record
    record = await users_handler.get_api_key_record(key_id)
    assert record["hashed_key"] == hashed_key

    # Update name
    new_name = "Updated API Key Name"
    await users_handler.update_api_key_name(
        user.id, uuid.UUID(keys[0]["key_id"]), new_name
    )
    keys_updated = await users_handler.get_user_api_keys(user.id)
    assert keys_updated[0]["name"] == new_name

    # Delete the key
    deleted_key_info = await users_handler.delete_api_key(
        user.id, uuid.UUID(keys[0]["key_id"])
    )
    assert deleted_key_info["public_key"] == key_id

    # Ensure it's actually deleted
    keys_after_deletion = await users_handler.get_user_api_keys(user.id)
    assert len(keys_after_deletion) == 0


@pytest.mark.asyncio
async def test_get_all_users(users_handler):
    # Create multiple users
    await users_handler.create_user("all1@example.com", "pass")
    await users_handler.create_user("all2@example.com", "pass")

    all_users = await users_handler.get_all_users()
    emails = [u.email for u in all_users]
    # Check that both are present
    assert "all1@example.com" in emails
    assert "all2@example.com" in emails
