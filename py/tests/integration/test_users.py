import uuid

import pytest

from r2r import R2RClient, R2RException


@pytest.fixture(scope="session")
def config():
    class TestConfig:
        base_url = "http://localhost:7272"
        superuser_email = "admin@example.com"
        superuser_password = "change_me_immediately"
        known_collection_id = "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"  # Example known collection ID

    return TestConfig()


@pytest.fixture(scope="session")
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
    user_resp = client.users.register(email, password)["results"]
    user_id = user_resp["id"]
    # If verification is mandatory, you'd have a step here to verify the user.
    # Otherwise, assume the user can login immediately.
    return user_id


def test_register_user(client):
    random_email = f"{uuid.uuid4()}@example.com"
    password = "test_password123"
    user_resp = client.users.register(random_email, password)
    user = user_resp["results"]
    assert "id" in user, "No user ID returned after registration."


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


def test_users_list(client, superuser_login):
    users_list = client.users.list()["results"]
    assert isinstance(users_list, list), "Listing users failed."


def test_get_current_user(client, superuser_login):
    me = client.users.me()["results"]
    assert "id" in me, "Failed to get current user."


def test_get_user_by_id(client, superuser_login):
    random_email = f"{uuid.uuid4()}@example.com"
    password = "somepassword"
    user_id = register_and_return_user_id(client, random_email, password)

    user = client.users.retrieve(user_id)["results"]
    assert user["id"] == user_id, "Retrieved user does not match requested ID."


def test_update_user(client, superuser_login):
    random_email = f"{uuid.uuid4()}@example.com"
    password = "somepassword"
    user_id = register_and_return_user_id(client, random_email, password)

    updated_name = "Updated Name"
    update_resp = client.users.update(user_id, name=updated_name)["results"]
    assert update_resp["name"] == updated_name, "User update failed."


def test_user_collections(client, superuser_login, config):
    # Create a user and list their collections
    random_email = f"{uuid.uuid4()}@example.com"
    password = "somepassword"
    user_id = register_and_return_user_id(client, random_email, password)

    collections = client.users.list_collections(user_id)["results"]
    assert isinstance(collections, list), "Listing user collections failed."


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


def test_delete_user(client):
    # Create and then delete user
    random_email = f"{uuid.uuid4()}@example.com"
    password = "somepassword"
    user_id = register_and_return_user_id(client, random_email, password)
    client.users.login(random_email, password)

    del_resp = client.users.delete(user_id, password)["results"]
    assert del_resp["success"], "User deletion failed."

    with pytest.raises(R2RException) as exc_info:
        result = client.users.retrieve(user_id)
        print("result = ", result)
    assert (
        exc_info.value.status_code == 404
    ), "User still exists after deletion."


def test_non_superuser_restrict_access(client):
    # Create user
    random_email = f"{uuid.uuid4()}@example.com"
    password = "somepassword"
    user_id = register_and_return_user_id(client, random_email, password)
    client.users.login(random_email, password)

    # Non-superuser listing users should fail
    with pytest.raises(R2RException) as exc_info:
        client.users.list()
    assert (
        exc_info.value.status_code == 403
    ), "Non-superuser listed users without error."

    # Create another user
    another_email = f"{uuid.uuid4()}@example.com"
    another_password = "anotherpassword"
    another_user_id = register_and_return_user_id(
        client, another_email, another_password
    )

    # Non-superuser updating another user should fail
    with pytest.raises(R2RException) as exc_info:
        client.users.update(another_user_id, name="Nope")
    assert (
        exc_info.value.status_code == 403
    ), "Non-superuser updated another user."


def test_superuser_downgrade_permissions(client, superuser_login, config):
    # Create a user and upgrade to superuser
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
