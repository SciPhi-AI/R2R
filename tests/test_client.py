import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import Body, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
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
            is_verified=False,
            name="Test User",
            bio="Test Bio",
            profile_picture="http://example.com/pic.jpg",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
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
    providers.auth.register.side_effect = mock_db.relational.create_user

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
