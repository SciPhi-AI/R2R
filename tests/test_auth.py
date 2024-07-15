import random
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

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

    return AuthService(
        config=Mock(auth=auth_config),
        providers=mock_providers,
        pipelines=mock_pipelines,
        run_manager=mock_run_manager,
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


@pytest.mark.asyncio
async def test_create_user_twice(auth_service, auth_provider):
    # Register a new user
    user = UserCreate(email="create@example.com", password="password123")
    new_user = await auth_service.register(user)
    with pytest.raises(R2RException) as exc_info:
        await auth_service.register(user)


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
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("login_fail@example.com", "wrong_password")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Incorrect email or password"


@pytest.mark.asyncio
async def test_login_failure_unverified_user(auth_service, auth_provider):
    # Register a new user but don't verify
    user = UserCreate(email="unverified@example.com", password="password123")
    await auth_service.register(user)

    # Attempt login with correct password but unverified account
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("unverified@example.com", "password123")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Email not verified"


@pytest.mark.asyncio
async def test_login_failure_nonexistent_user(auth_service):
    # Attempt login with non-existent user
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("nonexistent@example.com", "password123")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Incorrect email or password"


@pytest.mark.asyncio
async def test_login_with_non_existent_user(auth_service):
    with pytest.raises(HTTPException) as exc_info:
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
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.refresh_access_token(
            "user2@example.com", refresh_token
        )
    assert "401: Invalid token" in str(exc_info.value)


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

    with pytest.raises(HTTPException) as exc_info:
        result = await auth_service.user_info(access_token.token)
    assert "Token has expired" in str(exc_info.value)

    # Reset the token lifetime
    auth_provider.access_token_lifetime_in_minutes = 30
