import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import Body, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient

from r2r import (
    R2RApp,
    R2RBuilder,
    R2RClient,
    R2REngine,
    R2RException,
    Token,
    User,
    UserCreate,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_user(user_create: UserCreate):
    return User(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        email=user_create.email,
        hashed_password="hashed_" + user_create.password,
        is_active=True,
        is_superuser=False,
        is_verified=False,
        name="Test User",
        bio="Test Bio",
        profile_picture="http://example.com/pic.jpg",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


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

    db.relational.create_user.side_effect = create_user
    db.relational.get_user_by_id.return_value = create_user(
        UserCreate(email="test@example.com", password="password")
    )

    def update_user(user):
        updated_user = create_user(
            UserCreate(email=user.email, password="password")
        )
        updated_user.name = user.name
        updated_user.bio = user.bio
        updated_user.profile_picture = user.profile_picture
        return updated_user

    db.relational.update_user.side_effect = update_user

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
    providers.auth.register.side_effect = mock_db.relational.create_user
    providers.auth.verify_email.return_value = {
        "message": "Email verified successfully"
    }
    providers.auth.change_password.return_value = {
        "message": "Password changed successfully"
    }
    providers.auth.request_password_reset.return_value = {
        "message": "If the email exists, a reset link has been sent"
    }
    providers.auth.confirm_password_reset.return_value = {
        "message": "Password reset successfully"
    }
    providers.auth.logout.return_value = {"message": "Logged out successfully"}

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
    return R2RClient(base_url="http://testserver", custom_client=app_client)


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


# def test_register_existing_user(r2r_client, mock_db):
#     user_data = {"email": "existing@example.com", "password": "testpassword"}

#     mock_db.relational.get_user_by_email.return_value = User(
#         id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
#         email=user_data["email"],
#         hashed_password="hashed_password",
#         is_active=True,
#         is_superuser=False,
#         verification_code_expiry=None,
#     )

#     with pytest.raises(R2RException) as exc_info:
#         r2r_client.register(**user_data)

#     assert exc_info.value.status_code == 400
#     assert "Email already registered" in str(exc_info.value)


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


@pytest.mark.asyncio
async def test_change_password(r2r_client, mock_db):
    # Register and login
    user_data = {
        "email": "change_pass@example.com",
        "password": "old_password",
    }
    r2r_client.register(**user_data)
    r2r_client.login(**user_data)

    # Change password
    response = r2r_client.change_password("old_password", "new_password")
    print("response = ", response)
    assert response["results"]["message"] == "Password changed successfully"

    # Try logging in with new password
    login_response = r2r_client.login(
        email="change_pass@example.com", password="new_password"
    )
    assert "access_token" in login_response["results"]


@pytest.mark.asyncio
async def test_password_reset_flow(r2r_client, mock_db):
    # Register a user
    user_data = {"email": "reset_pass@example.com", "password": "old_password"}
    r2r_client.register(**user_data)

    # Request password reset
    reset_response = r2r_client.request_password_reset(
        "reset_pass@example.com"
    )
    assert "message" in reset_response["results"]

    # Confirm password reset (we'll need to mock the reset token)
    mock_reset_token = "mock_reset_token"
    confirm_response = r2r_client.confirm_password_reset(
        mock_reset_token, "new_password"
    )
    assert (
        confirm_response["results"]["message"] == "Password reset successfully"
    )

    # Try logging in with new password
    login_response = r2r_client.login(
        email="reset_pass@example.com", password="new_password"
    )
    assert "access_token" in login_response["results"]


@pytest.mark.asyncio
async def test_logout(r2r_client, mock_db):
    # Register and login
    user_data = {"email": "logout@example.com", "password": "password123"}
    r2r_client.register(**user_data)
    r2r_client.login(**user_data)

    # Logout
    logout_response = r2r_client.logout()
    assert logout_response["results"]["message"] == "Logged out successfully"

    # Ensure client's tokens are cleared
    assert r2r_client.access_token is None
    assert r2r_client._refresh_token is None


@pytest.mark.asyncio
async def test_user_profile(r2r_client, mock_db):
    # Register and login
    user_data = {"email": "profile@example.com", "password": "password123"}
    r2r_client.register(**user_data)
    r2r_client.login(**user_data)

    # Get user profile
    mock_db.relational.get_user_by_id.return_value = create_user(
        UserCreate(email="profile@example.com", password="password")
    )
    profile = r2r_client.get_user_profile()

    assert profile["results"]["email"] == "profile@example.com"

    # Update user profile
    updated_profile = r2r_client.update_user_profile(
        {"name": "John Doe", "bio": "Test bio"}
    )
    assert updated_profile["results"]["name"] == "John Doe"
    assert updated_profile["results"]["bio"] == "Test bio"


# TODO - Fix this test
# @pytest.mark.asyncio
# async def test_delete_user(r2r_client, mock_db):
#     # Register and login
#     user_data = {"email": "delete@example.com", "password": "password123"}
#     r2r_client.register(**user_data)
#     r2r_client.login(**user_data)

#     # Delete account
#     delete_response = r2r_client.delete_user("password123")
#     assert "message" in delete_response["results"]

#     # Ensure client's tokens are cleared
#     assert r2r_client.access_token is None
#     assert r2r_client._refresh_token is None

#     # Try to login with deleted account (should fail)
#     with pytest.raises(R2RException):
#         r2r_client.login(**user_data)
