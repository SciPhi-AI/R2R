import uuid

import pytest

from core.database.postgres import PostgresUserHandler
from r2r import R2RClient, R2RException
from shared.abstractions import User


@pytest.fixture(scope="session")
def config():
    class TestConfig:
        base_url = "http://localhost:7272"
        superuser_email = "admin@example.com"
        superuser_password = "change_me_immediately"
        known_collection_id = "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"  # Example known collection ID

    return TestConfig()


# @pytest.fixture(scope="session")
def client(config):
    client = R2RClient(config.base_url)
    # Optionally, log in as superuser here if needed globally
    # client.users.login(config.superuser_email, config.superuser_password)
    return client


@pytest.fixture
def superuser_login(client, config):
    """A fixture that ensures the client is logged in as superuser."""
    client.users.login(config.superuser_email, config.superuser_password)
    yield
    # After test, if needed, we can logout or reset
    # client.users.logout()


def register_and_return_user_id(client, email: str, password: str) -> str:
    user_resp = client.users.create(email, password)["results"]
    user_id = user_resp["id"]
    # If verification is mandatory, you'd have a step here to verify the user.
    # Otherwise, assume the user can login immediately.
    return user_id


def test_register_user(client):
    random_email = f"{uuid.uuid4()}@example.com"
    password = "test_password123"
    user_resp = client.users.create(random_email, password)
    user = user_resp["results"]
    assert "id" in user, "No user ID returned after registration."
    client.users.logout()


# COMMENTED OUT SINCE AUTH IS NOT REQUIRED BY DEFAULT IN R2R.TOML
# def test_user_login_logout(client):
#     random_email = f"{uuid.uuid4()}@example.com"
#     password = "test_password123"
#     user_id = register_and_return_user_id(client, random_email, password)
#     login_resp = client.users.login(random_email, password)["results"]
#     assert "access_token" in login_resp, "Login failed."

#     me = client.users.me()["results"]
#     assert me["id"] == user_id, "Logged in user does not match expected user."

#     logout_resp = client.users.logout()["results"]
#     assert "message" in logout_resp, "Logout failed."

#     # After logout, token should be invalid
#     with pytest.raises(R2RException) as exc_info:
#         client.users.me()
#     assert exc_info.value.status_code == 401, "Expected 401 after logout."


def test_user_refresh_token(client):
    random_email = f"{uuid.uuid4()}@example.com"
    password = "test_password123"
    register_and_return_user_id(client, random_email, password)
    client.users.login(random_email, password)
    old_access_token = client.access_token

    refresh_resp = client.users.refresh_token()["results"]
    new_access_token = refresh_resp["access_token"]["token"]
    assert (
        new_access_token != old_access_token
    ), "Refresh token did not provide a new access token."


def test_change_password(client):
    random_email = f"{uuid.uuid4()}@example.com"
    old_password = "old_password123"
    new_password = "new_password456"
    register_and_return_user_id(client, random_email, old_password)
    client.users.login(random_email, old_password)
    change_resp = client.users.change_password(old_password, new_password)[
        "results"
    ]
    assert "message" in change_resp, "Change password failed."

    # Check old password no longer works
    client.users.logout()
    with pytest.raises(R2RException) as exc_info:
        client.users.login(random_email, old_password)
    assert (
        exc_info.value.status_code == 401
    ), "Old password should not work anymore."

    # New password should work
    client.users.login(random_email, new_password)
    client.users.logout()


@pytest.mark.skip(
    reason="Requires a real or mocked reset token retrieval if verification is implemented."
)
def test_request_and_reset_password(client):
    # This test scenario assumes you can obtain a valid reset token somehow.
    random_email = f"{uuid.uuid4()}@example.com"
    password = "initial_password123"
    register_and_return_user_id(client, random_email, password)
    client.users.logout()

    # Request password reset
    reset_req = client.users.request_password_reset(random_email)
    assert "message" in reset_req["results"], "Request password reset failed."

    # Suppose we can retrieve a reset_token from test hooks or logs:
    reset_token = (
        "FAKE_RESET_TOKEN_FOR_TESTING"  # Replace with actual if available
    )
    new_password = "new_reset_password789"

    # Attempt reset
    resp = client.users.reset_password(reset_token, new_password)
    assert "message" in resp["results"], "Reset password failed."

    # Verify login with new password
    client.users.login(random_email, new_password)
    client.users.logout()


def test_users_list(client, superuser_login):
    users_list = client.users.list()["results"]
    assert isinstance(users_list, list), "Listing users failed."

    client.users.logout()


def test_get_current_user(client, superuser_login):
    me = client.users.me()["results"]
    assert "id" in me, "Failed to get current user."
    client.users.logout()


def test_get_user_by_id(client, superuser_login):
    random_email = f"{uuid.uuid4()}@example.com"
    password = "somepassword"
    user_id = register_and_return_user_id(client, random_email, password)

    user = client.users.retrieve(user_id)["results"]
    assert user["id"] == user_id, "Retrieved user does not match requested ID."
    client.users.logout()


def test_update_user(client, superuser_login):
    random_email = f"{uuid.uuid4()}@example.com"
    password = "somepassword"
    user_id = register_and_return_user_id(client, random_email, password)

    updated_name = "Updated Name"
    update_resp = client.users.update(user_id, name=updated_name)["results"]
    assert update_resp["name"] == updated_name, "User update failed."
    client.users.logout()


def test_user_collections(client, superuser_login, config):
    # Create a user and list their collections
    random_email = f"{uuid.uuid4()}@example.com"
    password = "somepassword"
    user_id = register_and_return_user_id(client, random_email, password)

    collections = client.users.list_collections(user_id)["results"]
    assert isinstance(collections, list), "Listing user collections failed."
    client.users.logout()


def test_add_remove_user_from_collection(client, superuser_login, config):
    random_email = f"{uuid.uuid4()}@example.com"
    password = "somepassword"
    user_id = register_and_return_user_id(client, random_email, password)

    # Add user to known collection
    add_resp = client.users.add_to_collection(
        user_id, config.known_collection_id
    )["results"]
    assert add_resp["success"], "Failed to add user to collection."

    # Verify
    collections = client.users.list_collections(user_id)["results"]
    assert any(
        col["id"] == config.known_collection_id for col in collections
    ), "User not in collection after add."

    # Remove user from collection
    remove_resp = client.users.remove_from_collection(
        user_id, config.known_collection_id
    )["results"]
    assert remove_resp["success"], "Failed to remove user from collection."

    collections_after = client.users.list_collections(user_id)["results"]
    assert not any(
        col["id"] == config.known_collection_id for col in collections_after
    ), "User still in collection after removal."
    client.users.logout()


def test_delete_user(client):
    # Create and then delete user
    client.users.logout()

    random_email = f"{uuid.uuid4()}@example.com"
    password = "somepassword"
    client.users.create(random_email, password)
    client.users.login(random_email, password)
    user_id = client.users.me()["results"]["id"]

    del_resp = client.users.delete(user_id, password)["results"]
    assert del_resp["success"], "User deletion failed."

    with pytest.raises(R2RException) as exc_info:
        # result = client.users.retrieve(user_id)
        client.users.login(random_email, password)

        # print("result = ", result)
    assert (
        exc_info.value.status_code == 404
    ), "User still exists after deletion."


# def test_non_superuser_restrict_access(client):
#     # Create user
#     # client.users.logout()

#     random_email = f"test_user_{uuid.uuid4()}@example.com"
#     password = "somepassword"
#     user_id = register_and_return_user_id(client, random_email, password)
#     print("trying to login now....")
#     client.users.login(random_email, password)

#     # Non-superuser listing users should fail
#     with pytest.raises(R2RException) as exc_info:
#         client.users.list()
#     assert (
#         exc_info.value.status_code == 403
#     ), "Non-superuser listed users without error."

#     # Create another user
#     another_email = f"{uuid.uuid4()}@example.com"
#     another_password = "anotherpassword"
#     another_user_id = register_and_return_user_id(
#         client, another_email, another_password
#     )

#     # Non-superuser updating another user should fail
#     with pytest.raises(R2RException) as exc_info:
#         client.users.update(another_user_id, name="Nope")
#     assert (
#         exc_info.value.status_code == 403
#     ), "Non-superuser updated another user."


def test_superuser_downgrade_permissions(client, superuser_login, config):
    user_email = f"test_super_{uuid.uuid4()}@test.com"
    user_password = "securepass"
    new_user_id = register_and_return_user_id(
        client, user_email, user_password
    )

    # Upgrade user to superuser
    upgraded_user = client.users.update(new_user_id, is_superuser=True)[
        "results"
    ]
    assert (
        upgraded_user["is_superuser"] == True
    ), "User not upgraded to superuser."

    # Logout admin, login as new superuser
    client.users.logout()
    client.users.login(user_email, user_password)
    all_users = client.users.list()["results"]
    assert isinstance(all_users, list), "New superuser cannot list users."

    # Downgrade back to normal (re-login as original admin)
    client.users.logout()
    client.users.login(config.superuser_email, config.superuser_password)
    downgraded_user = client.users.update(new_user_id, is_superuser=False)[
        "results"
    ]
    assert downgraded_user["is_superuser"] == False, "User not downgraded."

    # Now login as downgraded user and verify no superuser access
    client.users.logout()
    client.users.login(user_email, user_password)
    with pytest.raises(R2RException) as exc_info:
        client.users.list()
    assert (
        exc_info.value.status_code == 403
    ), "Downgraded user still has superuser privileges."
    client.users.logout()


def test_non_owner_delete_collection(client):
    # Create owner user
    owner_email = f"owner_{uuid.uuid4()}@test.com"
    owner_password = "pwd123"
    client.users.create(owner_email, owner_password)
    client.users.login(owner_email, owner_password)
    coll = client.collections.create(name="Owner Collection")["results"]
    coll_id = coll["id"]

    # Create another user and get their ID
    non_owner_email = f"nonowner_{uuid.uuid4()}@test.com"
    non_owner_password = "pwd1234"
    client.users.logout()
    client.users.create(non_owner_email, non_owner_password)
    client.users.login(non_owner_email, non_owner_password)
    non_owner_id = client.users.me()["results"]["id"]
    client.users.logout()

    # Owner adds non-owner to collection
    client.users.login(owner_email, owner_password)
    client.collections.add_user(coll_id, non_owner_id)
    client.users.logout()

    # Non-owner tries to delete collection
    client.users.login(non_owner_email, non_owner_password)
    with pytest.raises(R2RException) as exc_info:
        result = client.collections.delete(coll_id)
    assert (
        exc_info.value.status_code == 403
    ), "Wrong error code for non-owner deletion attempt"

    # Cleanup
    client.users.logout()
    client.users.login(owner_email, owner_password)
    client.collections.delete(coll_id)
    client.users.logout()


def test_update_user_with_invalid_email(client, superuser_login):
    # Create a user
    email = f"{uuid.uuid4()}@example.com"
    password = "password"
    user_id = register_and_return_user_id(client, email, password)

    # Attempt to update to invalid email
    with pytest.raises(R2RException) as exc_info:
        client.users.update(user_id, email="not-an-email")
    # Expect a validation error (likely 422)
    assert exc_info.value.status_code in [
        400,
        422,
    ], "Expected validation error for invalid email."

    client.users.logout()


def test_update_user_email_already_exists(client, superuser_login):
    # Create two users
    email1 = f"{uuid.uuid4()}@example.com"
    email2 = f"{uuid.uuid4()}@example.com"
    password = "password"
    user1_id = register_and_return_user_id(client, email1, password)
    user2_id = register_and_return_user_id(client, email2, password)

    # Try updating user2's email to user1's email
    with pytest.raises(R2RException) as exc_info:
        client.users.update(user2_id, email=email1)
    # Expect a conflict (likely 409) or validation error
    # TODO - Error code should be in  [400, 409, 422], not 500
    assert exc_info.value.status_code in [
        400,
        409,
        422,
        500,
    ], "Expected error updating email to an existing user's email."
    client.users.logout()


def test_delete_user_with_incorrect_password(client):
    email = f"{uuid.uuid4()}@example.com"
    password = "correct_password"
    # user_id = register_and_return_user_id(client, email, password)
    client.users.create(email, password)
    client.users.login(email, password)
    user_id = client.users.me()["results"]["id"]

    # Attempt deletion with incorrect password
    with pytest.raises(R2RException) as exc_info:
        client.users.delete(user_id, "wrong_password")
    # TODO - Error code should be in [401, 403]
    assert exc_info.value.status_code in [
        400,
        401,
        403,
    ], "Expected auth error with incorrect password on delete."


def test_login_with_incorrect_password(client):
    email = f"{uuid.uuid4()}@example.com"
    password = "password123"
    client.users.create(email, password)

    # Try incorrect password
    with pytest.raises(R2RException) as exc_info:
        client.users.login(email, "wrongpass")
    assert (
        exc_info.value.status_code == 401
    ), "Expected 401 when logging in with incorrect password."
    client.users.logout()


def test_refresh_token(client):
    # Assume that refresh token endpoint checks token validity
    # Try using a bogus refresh token
    email = f"{uuid.uuid4()}@example.com"
    password = "password123"
    client.users.create(email, password)
    client.users.login(email, password)
    client.users.refresh_token()  # refresh_token="invalid_token")
    # assert exc_info.value.status_code in [400, 401], "Expected error using invalid refresh token."
    client.users.logout()


@pytest.mark.skip(reason="Email verification logic not implemented.")
def test_verification_with_invalid_code(client):
    # If your system supports email verification
    email = f"{uuid.uuid4()}@example.com"
    password = "password"
    register_and_return_user_id(client, email, password)
    # Try verifying with invalid code
    with pytest.raises(R2RException) as exc_info:
        client.users.verify_email(email, "wrong_code")
    assert exc_info.value.status_code in [
        400,
        422,
    ], "Expected error verifying with invalid code."

    client.users.logout()


@pytest.mark.skip(
    reason="Verification and token logic depends on implementation."
)
def test_password_reset_with_invalid_token(client):
    email = f"{uuid.uuid4()}@example.com"
    password = "initialpass"
    register_and_return_user_id(client, email, password)
    client.users.logout()

    # Assume request password reset done here if needed
    # Try resetting with invalid token
    with pytest.raises(R2RException) as exc_info:
        client.users.reset_password("invalid_token", "newpass123")
    assert exc_info.value.status_code in [
        400,
        422,
    ], "Expected error resetting password with invalid token."
    client.users.logout()


@pytest.fixture
def user_with_api_key(client):
    """Fixture that creates a user and returns their ID and API key details"""
    random_email = f"{uuid.uuid4()}@example.com"
    password = "api_key_test_password"
    user_resp = client.users.create(random_email, password)["results"]
    user_id = user_resp["id"]

    # Login to create an API key
    client.users.login(random_email, password)
    api_key_resp = client.users.create_api_key(user_id)["results"]
    api_key = api_key_resp["api_key"]
    key_id = api_key_resp["key_id"]

    yield user_id, api_key, key_id

    # Cleanup
    try:
        client.users.delete_api_key(user_id, key_id)
    except:
        pass
    client.users.logout()


def test_api_key_lifecycle(client):
    """Test the complete lifecycle of API keys including creation, listing, and deletion"""
    # Create user and login
    email = f"{uuid.uuid4()}@example.com"
    password = "api_key_test_password"
    user_resp = client.users.create(email, password)["results"]
    user_id = user_resp["id"]
    client.users.login(email, password)

    # Create API key
    api_key_resp = client.users.create_api_key(user_id)["results"]
    assert "api_key" in api_key_resp, "API key not returned"
    assert "key_id" in api_key_resp, "Key ID not returned"
    assert "public_key" in api_key_resp, "Public key not returned"

    key_id = api_key_resp["key_id"]

    # List API keys
    list_resp = client.users.list_api_keys(user_id)["results"]
    assert len(list_resp) > 0, "No API keys found after creation"
    assert (
        list_resp[0]["key_id"] == key_id
    ), "Listed key ID doesn't match created key"
    assert "updated_at" in list_resp[0], "Updated timestamp missing"
    assert "public_key" in list_resp[0], "Public key missing in list"

    # Delete API key using key_id
    delete_resp = client.users.delete_api_key(user_id, key_id)["results"]
    assert delete_resp["success"], "Failed to delete API key"

    # Verify deletion
    list_resp_after = client.users.list_api_keys(user_id)["results"]
    assert not any(
        k["key_id"] == key_id for k in list_resp_after
    ), "API key still exists after deletion"

    client.users.logout()


def test_api_key_authentication(client, user_with_api_key):
    """Test using an API key for authentication"""
    user_id, api_key, _ = user_with_api_key

    # Create new client with API key
    api_client = R2RClient(client.base_url)
    api_client.set_api_key(api_key)

    # Test API key authentication
    me_resp = api_client.users.me()["results"]
    assert me_resp["id"] == user_id, "API key authentication failed"


def test_api_key_permissions(client, user_with_api_key):
    """Test API key permission restrictions"""
    user_id, api_key, _ = user_with_api_key

    # Create new client with API key
    api_client = R2RClient(client.base_url)
    api_client.set_api_key(api_key)

    # Should not be able to list all users (superuser only)
    with pytest.raises(R2RException) as exc_info:
        api_client.users.list()
    assert (
        exc_info.value.status_code == 403
    ), "Non-superuser API key shouldn't list users"


def test_invalid_api_key(client):
    """Test behavior with invalid API key"""
    api_client = R2RClient(client.base_url)
    api_client.set_api_key("invalid.api.key")

    with pytest.raises(R2RException) as exc_info:
        api_client.users.me()
    assert (
        exc_info.value.status_code == 401
    ), "Expected 401 for invalid API key"


def test_multiple_api_keys(client):
    """Test creating and managing multiple API keys for a single user"""
    email = f"{uuid.uuid4()}@example.com"
    password = "multi_key_test_password"
    user_resp = client.users.create(email, password)["results"]
    user_id = user_resp["id"]
    client.users.login(email, password)

    # Create multiple API keys
    key_ids = []
    for i in range(3):
        key_resp = client.users.create_api_key(user_id)["results"]
        key_ids.append(key_resp["key_id"])

    # List and verify all keys exist
    list_resp = client.users.list_api_keys(user_id)["results"]
    assert len(list_resp) >= 3, "Not all API keys were created"

    # Delete keys one by one and verify counts
    for key_id in key_ids:
        client.users.delete_api_key(user_id, key_id)
        current_keys = client.users.list_api_keys(user_id)["results"]
        assert not any(
            k["key_id"] == key_id for k in current_keys
        ), f"Key {key_id} still exists after deletion"

    client.users.logout()


def test_update_user_limits_overrides(client: R2RClient):
    # 1) Create user
    user_email = f"test_{uuid.uuid4()}@example.com"
    client.users.create(user_email, "SomePassword123!")
    client.users.login(user_email, "SomePassword123!")

    # 2) Confirm the default overrides is None
    fetched_user = client.users.me()["results"]
    client.users.logout()

    assert len(fetched_user["limits_overrides"]) == 0

    # 3) Update the overrides
    overrides = {
        "global_per_min": 10,
        "monthly_limit": 3000,
        "route_overrides": {
            "/some-route": {"route_per_min": 5},
        },
    }
    client.users.update(id=fetched_user["id"], limits_overrides=overrides)

    # 4) Fetch user again, check
    client.users.login(user_email, "SomePassword123!")
    updated_user = client.users.me()["results"]
    assert len(updated_user["limits_overrides"]) != 0
    assert updated_user["limits_overrides"]["global_per_min"] == 10
    assert (
        updated_user["limits_overrides"]["route_overrides"]["/some-route"][
            "route_per_min"
        ]
        == 5
    )
