import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import Body, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.testclient import TestClient

from r2r import (
    R2RApp,
    R2RAuthProvider,
    R2RBuilder,
    R2RClient,
    R2RConfig,
    R2REngine,
    R2RException,
    Token,
    User,
    UserCreate,
)
from r2r.providers import BCryptConfig, BCryptProvider

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@pytest.fixture(scope="function")
def mock_auth_wrapper():
    def auth_wrapper(token: str = Depends(oauth2_scheme)):
        return User(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            is_active=True,
            hashed_password="xxx",
            is_superuser=False,
        )

    return auth_wrapper


@pytest.fixture(scope="function")
def mock_db():
    db = MagicMock()
    db.relational.get_user_by_email.return_value = (
        None  # Simulate empty database
    )

    def create_user(user_create: UserCreate):
        return User(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            email=user_create.email,
            hashed_password="hashed_" + user_create.password,
            is_active=True,
            is_superuser=False,
            verification_code_expiry=None,
        )

    db.relational.create_user.side_effect = create_user
    return db


async def mock_asearch(*args, **kwargs):
    return {
        "vector_search_results": [
            {
                "id": "doc1",
                "metadata": {"text": "Sample search result"},
                "score": 0.95,
            }
        ]
    }


@pytest.fixture(scope="function")
def app_client(mock_db, mock_auth_wrapper):
    config = R2RBuilder._get_config("auth")
    providers = MagicMock()
    providers.auth.login.return_value = {
        "access_token": Token(token="access_token", token_type="access"),
        "refresh_token": Token(token="refresh_token", token_type="refresh"),
    }
    providers.auth.auth_wrapper = mock_auth_wrapper

    providers.database = mock_db
    pipelines = MagicMock()
    engine = R2REngine(
        config=config,
        providers=providers,
        pipelines=pipelines,
    )
    engine.asearch = mock_asearch
    app = R2RApp(engine)
    return TestClient(app.app)


@pytest.fixture(scope="function")
def r2r_client(app_client):
    print("using regular r2r client")
    return R2RClient(base_url="http://testserver", custom_client=app_client)


@pytest.fixture(scope="function")
def non_auth_app_client(mock_db, mock_auth_wrapper):
    providers = MagicMock()
    providers.database = mock_db
    config = R2RConfig.from_json()
    providers.auth = R2RAuthProvider(
        config.auth, BCryptProvider(BCryptConfig()), providers.database
    )

    pipelines = MagicMock()
    engine = R2REngine(
        config=config,
        providers=providers,
        pipelines=pipelines,
    )
    engine.asearch = mock_asearch
    app = R2RApp(engine)
    return TestClient(app.app)


@pytest.fixture(scope="function")
def non_auth_r2r_client(non_auth_app_client):
    print("using non auth r2r")
    return R2RClient(
        base_url="http://testserver", custom_client=non_auth_app_client
    )


def test_health_check(r2r_client):
    response = r2r_client.health()
    assert response == {"response": "ok"}


def test_register_user(r2r_client, mock_db):
    user_data = {"email": "test@example.com", "password": "testpassword"}
    response = r2r_client.register(**user_data)
    assert "results" in response
    assert response["results"]["email"] == user_data["email"]
    assert "id" in response["results"]
    assert "hashed_password" in response["results"]
    mock_db.relational.create_user.assert_called_once()


def test_register_existing_user(r2r_client, mock_db):
    user_data = {"email": "existing@example.com", "password": "testpassword"}
    mock_db.relational.get_user_by_email.return_value = User(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        email=user_data["email"],
        hashed_password="hashed_password",
        is_active=True,
        is_superuser=False,
        verification_code_expiry=None,
    )

    with pytest.raises(R2RException) as exc_info:
        r2r_client.register(**user_data)

    assert exc_info.value.status_code == 400
    assert "Email already registered" in str(exc_info.value)


def test_login_user(r2r_client, mock_db):
    user_data = {"email": "login_test@example.com", "password": "testpassword"}
    mock_db.relational.get_user_by_email.return_value = None
    response = r2r_client.register(**user_data)

    mock_db.relational.get_user_by_email.return_value = User(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        email=user_data["email"],
        hashed_password="hashed_" + user_data["password"],
        is_active=True,
        is_superuser=False,
        verification_code_expiry=None,
    )
    response = r2r_client.login(**user_data)
    assert "results" in response
    assert "access_token" in response["results"]
    assert "refresh_token" in response["results"]


def test_authenticated_search(r2r_client, mock_db):
    # Register and login
    user_data = {
        "email": "search_test@example.com",
        "password": "testpassword",
    }
    r2r_client.register(**user_data)
    login_response = r2r_client.login(**user_data)

    # Perform search
    search_query = "test query"
    search_response = r2r_client.search(search_query)
    results = search_response["results"]
    assert "vector_search_results" in results
    assert len(results["vector_search_results"]) > 0
    assert results["vector_search_results"][0]["id"] == "doc1"
    assert (
        results["vector_search_results"][0]["metadata"]["text"]
        == "Sample search result"
    )
    assert results["vector_search_results"][0]["score"] == 0.95


def test_non_auth_get_current_user(non_auth_r2r_client):
    print("calling user info....")
    response = non_auth_r2r_client.user_info()
    user = response["results"]

    assert user["email"] == "admin@example.com"
    assert user["is_superuser"] is True
    assert user["is_active"] is True
    assert user["is_verified"] is True
    assert "id" in user
    assert "hashed_password" in user
    assert "created_at" in user
    assert "updated_at" in user


def test_non_auth_search(non_auth_r2r_client):
    search_query = "test query"
    search_response = non_auth_r2r_client.search(search_query)
    results = search_response["results"]

    assert "vector_search_results" in results
    assert len(results["vector_search_results"]) > 0
    assert results["vector_search_results"][0]["id"] == "doc1"
    assert (
        results["vector_search_results"][0]["metadata"]["text"]
        == "Sample search result"
    )
    assert results["vector_search_results"][0]["score"] == 0.95


from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException

# ... (existing imports and fixtures) ...


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
        new_user.id, "old_password", "new_password"
    )

    # Try logging in with old password
    with pytest.raises(HTTPException) as exc_info:
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
    mock_email_provider.send_reset_email.assert_called_once()

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
    with pytest.raises(HTTPException) as exc_info:
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
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.user_info(access_token)
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
    assert profile["email"] == "profile@example.com"
    assert "name" in profile
    assert "bio" in profile


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
    updated_profile = await auth_service.update_user_profile(
        new_user.id,
        {
            "name": "John Doe",
            "bio": "Test bio",
            "profile_picture": "http://example.com/pic.jpg",
        },
    )
    assert updated_profile["name"] == "John Doe"
    assert updated_profile["bio"] == "Test bio"
    assert updated_profile["profile_picture"] == "http://example.com/pic.jpg"

    # Verify that the profile was updated
    profile = await auth_service.get_user_profile(new_user.id)
    assert profile["name"] == "John Doe"
    assert profile["bio"] == "Test bio"
    assert profile["profile_picture"] == "http://example.com/pic.jpg"


@pytest.mark.asyncio
async def test_delete_user_account(auth_service, auth_provider):
    # Register and verify a user
    user = UserCreate(
        email="delete_account@example.com", password="password123"
    )
    with patch.object(
        auth_provider.crypto_provider,
        "generate_verification_code",
        return_value="123456",
    ):
        new_user = await auth_service.register(user)
    await auth_service.verify_email("123456")

    # Delete user account
    await auth_service.delete_user_account(new_user.id, "password123")

    # Try to get the deleted user's profile
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.get_user_profile(new_user.id)
    assert exc_info.value.status_code == 404

    # Try to login with deleted account
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("delete_account@example.com", "password123")
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
        new_user = await auth_service.register(user)
    await auth_service.verify_email("123456")

    # Login and logout to create a blacklisted token
    tokens = await auth_service.login("cleanup@example.com", "password123")
    access_token = tokens["access_token"].token
    await auth_service.logout(access_token)

    # Manually insert an expired blacklisted token
    expired_token = "expired_token"
    auth_provider.db_provider.relational.blacklist_token(
        expired_token, datetime.utcnow() - timedelta(days=1)
    )

    # Run cleanup
    await auth_service.clean_expired_blacklisted_tokens()

    # Check that the expired token was removed and the valid one remains
    assert not auth_provider.db_provider.relational.is_token_blacklisted(
        expired_token
    )
    assert auth_provider.db_provider.relational.is_token_blacklisted(
        access_token
    )
