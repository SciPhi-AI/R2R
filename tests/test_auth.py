import random
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from r2r import (
    AuthConfig,
    BCryptConfig,
    BCryptProvider,
    DatabaseConfig,
    PostgresDBProvider,
    R2RAuthProvider,
    R2RException,
    UserCreate,
)
from r2r.main.services import AuthService


# Fixture for PostgresDBProvider
@pytest.fixture
def pg_vector_db():
    random_collection_name = (
        f"test_collection_{random.randint(0, 1_000_000_000)}"
    )
    config = DatabaseConfig.create(
        provider="postgres", vecs_collection=random_collection_name
    )
    db = PostgresDBProvider(
        config, crypto_provider=BCryptProvider(BCryptConfig()), dimension=3
    )
    yield db
    # Teardown
    db.vx.delete_collection(
        db.config.extra_fields.get("vecs_collection", None)
    )


@pytest.fixture
def auth_config():
    return AuthConfig(
        secret_key="wNFbczH3QhUVcPALwtWZCPi0lrDlGV3P1DPRVEQCPbM",
        access_token_lifetime_in_minutes=30,
        refresh_token_lifetime_in_days=7,
        require_email_verification=True,
    )


@pytest.fixture
def auth_provider(auth_config, pg_vector_db):
    return R2RAuthProvider(
        auth_config,
        crypto_provider=BCryptProvider(BCryptConfig()),
        db_provider=pg_vector_db,
    )


@pytest.fixture
def mock_email_provider():
    mock_email = Mock()
    mock_email.send_verification_email = Mock()
    return mock_email


@pytest.fixture
def auth_service(auth_provider, auth_config, pg_vector_db):
    # Mock other necessary components for AuthService
    mock_providers = Mock()
    mock_providers.auth = auth_provider
    mock_providers.database = pg_vector_db
    mock_providers.email = mock_email_provider
    mock_pipelines = Mock()
    mock_run_manager = Mock()
    mock_logging_connection = Mock()
    mock_assistants = Mock()

    return AuthService(
        config=Mock(auth=auth_config),
        providers=mock_providers,
        pipelines=mock_pipelines,
        run_manager=mock_run_manager,
        agents=mock_assistants,
        logging_connection=mock_logging_connection,
    )


@pytest.mark.asyncio
async def test_create_user(auth_service, auth_provider):
    # Register a new user
    user = UserCreate(email="create@example.com", password="password123")
    new_user = await auth_service.register(user)
    assert new_user.email == "create@example.com"
    assert not new_user.is_verified
    fetched_user = auth_provider.db_provider.relational.get_user_by_email(
        new_user.email
    )
    assert fetched_user.email == new_user.email
    assert fetched_user.is_verified == new_user.is_verified
    assert fetched_user.hashed_password == new_user.hashed_password
    assert fetched_user.is_active == new_user.is_active


# @pytest.mark.asyncio
# async def test_create_user_twice(auth_service, auth_provider):
#     # Register a new user
#     user = UserCreate(email="create@example.com", password="password123")
#     new_user = await auth_service.register(user)
#     with pytest.raises(R2RException) as exc_info:
#         await auth_service.register(user)


@pytest.mark.asyncio
async def test_verify_user(auth_service, auth_provider):
    # Register a new user
    user = UserCreate(email="verify@example.com", password="password123")
    # Mock the generate_verification_code method to return a known value
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)

        # mock verification
        assert new_user.email == "verify@example.com"
        assert not new_user.is_verified

        # Verify the user using the known verification code
        verification = auth_provider.verify_email("123456")
        assert verification["message"] == "Email verified successfully"

        # Check that the user is now verified
        response = auth_provider.db_provider.relational.get_user_by_email(
            "verify@example.com"
        )
        assert response.is_verified
        assert response.email == "verify@example.com"


@pytest.mark.asyncio
async def test_login_success(auth_service, auth_provider):
    # Register a new user
    user = UserCreate(
        email="login_test@example.com", password="correct_password"
    )
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)

    # Verify the user
    auth_provider.verify_email("123456")

    # Attempt login with correct password
    login_result = await auth_service.login(
        "login_test@example.com", "correct_password"
    )

    assert "access_token" in login_result
    assert "refresh_token" in login_result
    assert login_result["access_token"].token_type == "access"
    assert login_result["refresh_token"].token_type == "refresh"


@pytest.mark.asyncio
async def test_login_failure_wrong_password(auth_service, auth_provider):
    # Register a new user
    user = UserCreate(
        email="login_fail@example.com", password="correct_password"
    )
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)

    # Verify the user
    auth_provider.verify_email("123456")

    # Attempt login with incorrect password
    with pytest.raises(R2RException) as exc_info:
        await auth_service.login("login_fail@example.com", "wrong_password")

    assert exc_info.value.status_code == 401
    assert exc_info.value.message == "Incorrect email or password"


@pytest.mark.asyncio
async def test_login_failure_unverified_user(auth_service, auth_provider):
    # Register a new user but don't verify
    user = UserCreate(email="unverified@example.com", password="password123")
    await auth_service.register(user)

    # Attempt login with correct password but unverified account
    with pytest.raises(R2RException) as exc_info:
        await auth_service.login("unverified@example.com", "password123")

    assert exc_info.value.status_code == 401
    assert exc_info.value.message == "Email not verified"


@pytest.mark.asyncio
async def test_login_failure_nonexistent_user(auth_service):
    # Attempt login with non-existent user
    with pytest.raises(R2RException) as exc_info:
        await auth_service.login("nonexistent@example.com", "password123")

    assert exc_info.value.status_code == 401
    assert exc_info.value.message == "Incorrect email or password"


@pytest.mark.asyncio
async def test_login_with_non_existent_user(auth_service):
    with pytest.raises(R2RException) as exc_info:
        await auth_service.login("nonexistent@example.com", "password123")
    assert "Incorrect email or password" in str(exc_info.value)


@pytest.mark.asyncio
async def test_verify_email_with_expired_code(auth_service, auth_provider):
    user = UserCreate(
        email="verify_expired@example.com", password="password123"
    )
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)

        # Get the verification code

        # Manually expire the verification code
        auth_provider.db_provider.relational.expire_verification_code(
            new_user.id
        )

        with pytest.raises(R2RException) as exc_info:
            await auth_service.verify_email("123456")
        assert "Invalid or expired verification code" in str(exc_info.value)


@pytest.mark.asyncio
async def test_refresh_token_flow(auth_service, auth_provider):
    # Register and verify a user
    user = UserCreate(email="refresh@example.com", password="password123")
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)

    await auth_service.verify_email("123456")

    # Login to get initial tokens
    tokens = await auth_service.login("refresh@example.com", "password123")
    initial_access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Use refresh token to get new access token
    new_tokens = await auth_service.refresh_access_token(
        "refresh@example.com", refresh_token.token
    )
    assert "access_token" in new_tokens
    assert new_tokens["access_token"].token != initial_access_token.token


@pytest.mark.asyncio
async def test_refresh_token_with_wrong_user(auth_service, auth_provider):
    # Register and verify two users
    user1 = UserCreate(email="user1@example.com", password="password123")
    user2 = UserCreate(email="user2@example.com", password="password123")

    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user1 = await auth_service.register(user1)
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="1234567",
    ):
        new_user2 = await auth_service.register(user2)

    await auth_service.verify_email("123456")
    await auth_service.verify_email("1234567")

    # Login as user1
    tokens = await auth_service.login("user1@example.com", "password123")
    refresh_token = tokens["refresh_token"]

    # Try to use user1's refresh token for user2
    with pytest.raises(R2RException) as exc_info:
        await auth_service.refresh_access_token(
            "user2@example.com", refresh_token.token
        )
    assert "Invalid email address attached to token" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_current_user_with_expired_token(
    auth_service, auth_provider
):
    user = UserCreate(
        email="expired_token@example.com", password="password123"
    )
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)

    await auth_service.verify_email("123456")

    # Manually expire the token
    auth_provider.access_token_lifetime_in_minutes = (
        -1
    )  # This will create an expired token
    auth_provider.refresh_token_lifetime_in_days = (
        -1
    )  # This will create an expired token

    tokens = await auth_service.login(
        "expired_token@example.com", "password123"
    )
    access_token = tokens["refresh_token"]

    with pytest.raises(R2RException) as exc_info:
        result = await auth_service.user(access_token.token)
    assert "Token has expired" in str(exc_info.value)

    # Reset the token lifetime
    auth_provider.access_token_lifetime_in_minutes = 30


@pytest.mark.asyncio
async def test_change_password(auth_service, auth_provider):
    # Register and verify a user
    user = UserCreate(
        email="change_password@example.com", password="old_password"
    )
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)
    await auth_service.verify_email("123456")

    # Change password
    await auth_service.change_password(
        new_user, "old_password", "new_password"
    )

    # Try logging in with old password
    with pytest.raises(R2RException) as exc_info:
        await auth_service.login("change_password@example.com", "old_password")
    assert exc_info.value.status_code == 401

    # Login with new password
    login_result = await auth_service.login(
        "change_password@example.com", "new_password"
    )
    assert "access_token" in login_result


@pytest.mark.asyncio
async def test_reset_password_flow(
    auth_service, auth_provider, mock_email_provider
):
    # Register and verify a user
    user = UserCreate(
        email="reset_password@example.com", password="old_password"
    )
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)
    await auth_service.verify_email("123456")

    # Request password reset
    await auth_service.request_password_reset("reset_password@example.com")

    # Verify that an email was "sent"
    # mock_email_provider.send_reset_email.assert_called_once()

    # Mock getting the reset token from the email
    reset_token = "mocked_reset_token"
    with patch.object(
        auth_provider.db_provider.relational,
        "get_user_id_by_reset_token",
        return_value=new_user.id,
    ):
        # Confirm password reset
        await auth_service.confirm_password_reset(reset_token, "new_password")

    # Try logging in with old password
    with pytest.raises(R2RException) as exc_info:
        await auth_service.login("reset_password@example.com", "old_password")
    assert exc_info.value.status_code == 401

    # Login with new password
    login_result = await auth_service.login(
        "reset_password@example.com", "new_password"
    )
    assert "access_token" in login_result


@pytest.mark.asyncio
async def test_logout(auth_service, auth_provider):
    # Register and verify a user
    user = UserCreate(email="logout@example.com", password="password123")
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)
    await auth_service.verify_email("123456")

    # Login to get tokens
    tokens = await auth_service.login("logout@example.com", "password123")
    access_token = tokens["access_token"].token

    # Logout
    await auth_service.logout(access_token)

    # Try to use the logged out token
    with pytest.raises(R2RException) as exc_info:
        await auth_service.user(access_token)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_user_profile(auth_service, auth_provider):
    # Register and verify a user
    user = UserCreate(email="profile@example.com", password="password123")
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)
    await auth_service.verify_email("123456")

    # Get user profile
    profile = await auth_service.get_user_profile(new_user.id)
    assert profile.email == "profile@example.com"
    assert profile.name is None
    assert profile.bio is None


@pytest.mark.asyncio
async def test_update_user_profile(auth_service, auth_provider):
    # Register and verify a user
    user = UserCreate(
        email="update_profile@example.com", password="password123"
    )
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)
    await auth_service.verify_email("123456")

    # Update user profile
    updated_profile = await auth_service.update_user(
        new_user.id,
        {
            "name": "John Doe",
            "bio": "Test bio",
            "profile_picture": "http://example.com/pic.jpg",
        },
    )
    assert updated_profile.name == "John Doe"
    assert updated_profile.bio == "Test bio"
    assert updated_profile.profile_picture == "http://example.com/pic.jpg"

    # Verify that the profile was updated
    profile = await auth_service.get_user_profile(new_user.id)
    assert profile.name == "John Doe"
    assert profile.bio == "Test bio"
    assert profile.profile_picture == "http://example.com/pic.jpg"


@pytest.mark.asyncio
async def test_delete_user_account(auth_service, auth_provider):
    # Register and verify a user
    user = UserCreate(email="delete_user@example.com", password="password123")
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)
    await auth_service.verify_email("123456")

    # Delete user account
    await auth_service.delete_user(new_user.id, "password123")

    # Try to get the deleted user's profile
    with pytest.raises(R2RException) as exc_info:
        await auth_service.get_user_profile(new_user.id)
    assert exc_info.value.status_code == 404

    # Try to login with deleted account
    with pytest.raises(R2RException) as exc_info:
        await auth_service.login("delete_user@example.com", "password123")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_token_blacklist_cleanup(auth_service, auth_provider):
    # Register and verify a user
    user = UserCreate(email="cleanup@example.com", password="password123")
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        await auth_service.register(user)
    await auth_service.verify_email("123456")

    # Login and logout to create a blacklisted token
    tokens = await auth_service.login("cleanup@example.com", "password123")
    access_token = tokens["access_token"].token
    await auth_service.logout(access_token)

    # Manually insert an "old" blacklisted token
    old_token = "old_token"
    # with patch('datetime.datetime') as mock_datetime:
    # mock_datetime.utcnow.return_value = datetime.utcnow() - timedelta(hours=7*25)
    auth_provider.db_provider.relational.blacklist_token(
        old_token, datetime.now(timezone.utc) - timedelta(hours=7 * 25)
    )

    # Verify both tokens are in the blacklist before cleanup
    assert auth_provider.db_provider.relational.is_token_blacklisted(old_token)
    assert auth_provider.db_provider.relational.is_token_blacklisted(
        access_token
    )

    # Run cleanup (tokens older than 24 hours will be removed)
    await auth_service.clean_expired_blacklisted_tokens()

    # Check that the old token was removed and the newer one remains
    assert not auth_provider.db_provider.relational.is_token_blacklisted(
        old_token
    )
    assert auth_provider.db_provider.relational.is_token_blacklisted(
        access_token
    )


@pytest.mark.asyncio
async def test_register_and_verify(auth_service, auth_provider):
    user = UserCreate(email="newuser@example.com", password="password123")
    new_user = await auth_service.register(user)
    assert new_user.email == "newuser@example.com"
    assert not new_user.is_verified

    # Mock verification code generation
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        await auth_service.register(user)
        verified = await auth_service.verify_email("123456")
        assert verified


@pytest.mark.asyncio
async def test_login_logout(auth_service, auth_provider):
    user = UserCreate(email="loginuser@example.com", password="password123")
    # Mock reset token generation
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        await auth_service.register(user)
        await auth_service.verify_email("123456")

    tokens = await auth_service.login("loginuser@example.com", "password123")
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    logout_result = await auth_service.logout(tokens["access_token"].token)
    assert logout_result["message"] == "Logged out successfully"


@pytest.mark.asyncio
async def test_refresh_token(auth_service, auth_provider):
    user = UserCreate(email="refreshuser@example.com", password="password123")
    # Mock reset token generation
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        await auth_service.register(user)
        await auth_service.verify_email("123456")

    tokens = await auth_service.login("refreshuser@example.com", "password123")
    new_tokens = await auth_service.refresh_access_token(
        "refreshuser@example.com", tokens["refresh_token"].token
    )
    assert new_tokens["access_token"].token != tokens["access_token"].token


@pytest.mark.asyncio
async def test_change_password(auth_service, auth_provider):
    user = UserCreate(email="changepass@example.com", password="oldpassword")
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)
    await auth_service.verify_email("123456")

    result = await auth_service.change_password(
        new_user, "oldpassword", "newpassword"
    )
    assert result["message"] == "Password changed successfully"

    with pytest.raises(R2RException):
        await auth_service.login("changepass@example.com", "oldpassword")

    tokens = await auth_service.login("changepass@example.com", "newpassword")
    assert "access_token" in tokens


@pytest.mark.asyncio
async def test_request_reset_password(auth_service):
    user = UserCreate(email="resetpass@example.com", password="password123")
    await auth_service.register(user)

    result = await auth_service.request_password_reset("resetpass@example.com")
    assert (
        result["message"] == "If the email exists, a reset link has been sent"
    )


@pytest.mark.asyncio
async def test_confirm_reset_password(auth_service, auth_provider):
    user = UserCreate(email="confirmreset@example.com", password="oldpassword")

    # Mock reset token generation
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        await auth_service.register(user)
        await auth_service.verify_email("123456")
        await auth_service.request_password_reset("confirmreset@example.com")
        result = await auth_service.confirm_password_reset(
            "123456", "newpassword"
        )
        assert result["message"] == "Password reset successfully"

    tokens = await auth_service.login(
        "confirmreset@example.com", "newpassword"
    )
    assert "access_token" in tokens


@pytest.mark.asyncio
async def test_get_user_profile(auth_service):
    user = UserCreate(email="profile@example.com", password="password123")
    new_user = await auth_service.register(user)

    profile = await auth_service.get_user_profile(new_user.id)
    assert profile.email == "profile@example.com"


@pytest.mark.asyncio
async def test_update_user_profile(auth_service):
    user = UserCreate(
        email="updateprofile@example.com", password="password123"
    )
    new_user = await auth_service.register(user)

    updated_user = await auth_service.update_user(
        new_user.id, {"name": "John Doe"}
    )
    assert updated_user.name == "John Doe"


@pytest.mark.asyncio
async def test_delete_user_account(auth_service):
    user = UserCreate(email="deleteuser@example.com", password="password123")
    new_user = await auth_service.register(user)

    result = await auth_service.delete_user(new_user.id, "password123")
    assert result["message"] == "User account deleted successfully"

    with pytest.raises(R2RException):
        await auth_service.login("deleteuser@example.com", "password123")
