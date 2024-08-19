import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import Body, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient
from r2r_python_sdk import R2RClient

from r2r import (
    DocumentInfo,
    R2RApp,
    R2RBuilder,
    R2REngine,
    R2RException,
    Token,
    UserResponse,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_user(email: str, password: str):
    return UserResponse(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        email=email,
        hashed_password="hashed_" + password,
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
        return UserResponse(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            is_active=True,
            hashed_password="xxx",
            is_superuser=False,
        )

    return auth_wrapper


@pytest.fixture(scope="function")
def mock_auth_wrapper():
    def auth_wrapper(token: str = Depends(oauth2_scheme)):
        return UserResponse(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            is_active=True,
            hashed_password="xxx",
            is_superuser=True,
        )

    return auth_wrapper


@pytest.fixture(scope="function")
def mock_super_auth_wrapper():
    def auth_wrapper(token: str = Depends(oauth2_scheme)):
        return UserResponse(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            is_active=True,
            hashed_password="xxx",
            is_superuser=True,
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
        email="test@example.com", password="password"
    )

    def update_user(user):
        updated_user = create_user(email=user.email, password="password")
        updated_user.name = user.name
        updated_user.bio = user.bio
        updated_user.profile_picture = user.profile_picture
        return updated_user

    db.relational.update_user.side_effect = update_user
    db.relational.get_documents_in_group.return_value = [
        DocumentInfo(
            user_id=uuid.uuid4(),
            id=uuid.uuid4(),
            title=f"Document {i}",
            type="txt",
            group_ids=[uuid.uuid4()],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            version="1",
            metadata={},
            size_in_bytes=1000,
        )
        for i in range(100)
    ]

    return db


async def mock_asearch(*args, **kwargs):
    return {
        "vector_search_results": [
            {
                "fragment_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
                "extraction_id": "3f3d47f3-8baf-58eb-8bc2-0171fb1c6e09",
                "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
                "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
                "group_ids": [],
                "score": 0.23943702876567796,
                "text": "Alternate Base Rate means, for any day, a rate per annum  equal to the greatest of (i) the Prime Rate in effect on such day, (ii) the Federal Funds Effective Rate in effect on such day \nplus  \u00bd of 1% and (iii) the sum of (a) the Adjusted LIBO Rate that would be payable onsuch day for a Eurodollar Borrowing with a one-month interest period",
                "metadata": {
                    "title": "uber_2021.pdf",
                    "associatedQuery": "What is the capital of France?",
                },
            },
            {
                "fragment_id": "f0b40c99-e200-507b-a4b9-e931e0b5f321",
                "extraction_id": "0348ae71-bccb-58d1-8b5f-36810e46245a",
                "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
                "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
                "group_ids": [],
                "score": 0.22033508121967305,
                "text": "s, could also restrict our future access to the capital markets.ITEM 1B. UNRESOLVED STAFF\n COMMENTSNot applicable.\nITEM 2. PROPERTIES\nAs\n of December 31, 2021, we leased and owned office facilities around the world totaling 10.6 million square feet, including 2.6 million square feet for ourcorporate headquarte\nrs in the San Francisco Bay Area, California.We",
                "metadata": {
                    "title": "uber_2021.pdf",
                    "associatedQuery": "What is the capital of France?",
                },
            },
            {
                "fragment_id": "967c4291-0629-55b6-9323-e2291de8730d",
                "extraction_id": "7595cdf2-d1b0-5f13-b853-8ce6857ca5f5",
                "document_id": "3e157b3a-8469-51db-90d9-52e7d896b49b",
                "user_id": "2acb499e-8428-543b-bd85-0d9098718220",
                "group_ids": [],
                "score": 0.21763332188129403,
                "text": "RFR means, for any RFR Loan denominated in (a) British Pounds, SONIA and (b) Swiss Francs, SARON. \nRFR Borrowing means, as to any Borrowing, the RFR Loans comprising such Borrowing. \nRFR Business Day means, for any Loan denominated in (a) British Pounds, any day except for (i) a Saturday, (ii) a Sunday or (iii) a day on which banks are closed for general business in London and (b) Swiss Francs, any day except for (i) a Saturday, (ii) a Sunday or",
                "metadata": {
                    "title": "uber_2021.pdf",
                    "associatedQuery": "What is the capital of France?",
                },
            },
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
    agents = MagicMock()
    engine = R2REngine(
        config=config,
        providers=providers,
        pipelines=pipelines,
        agents=agents,
    )
    engine.asearch = mock_asearch
    app = R2RApp(engine)
    return TestClient(app.app)


@pytest.fixture(scope="function")
def r2r_client(app_client):
    return R2RClient(base_url="http://testserver", custom_client=app_client)


def test_health_check(r2r_client):
    response = r2r_client.health()
    assert response["results"] == {"response": "ok"}


def test_register_user(r2r_client, mock_db):
    user_data = {"email": "test@example.com", "password": "testpassword"}
    response = r2r_client.register(**user_data)
    assert "results" in response
    assert response["results"]["email"] == user_data["email"]
    assert "id" in response["results"]
    assert "hashed_password" in response["results"]
    mock_db.relational.create_user.assert_called_once()


def test_login_user(r2r_client, mock_db):
    user_data = {"email": "login_test@example.com", "password": "testpassword"}
    mock_db.relational.get_user_by_email.return_value = None
    response = r2r_client.register(**user_data)

    mock_db.relational.get_user_by_email.return_value = UserResponse(
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
    assert (
        results["vector_search_results"][0]["fragment_id"]
        == "c68dc72e-fc23-5452-8f49-d7bd46088a96"
    )
    assert (
        results["vector_search_results"][0]["text"]
        == "Alternate Base Rate means, for any day, a rate per annum  equal to the greatest of (i) the Prime Rate in effect on such day, (ii) the Federal Funds Effective Rate in effect on such day \nplus  \u00bd of 1% and (iii) the sum of (a) the Adjusted LIBO Rate that would be payable onsuch day for a Eurodollar Borrowing with a one-month interest period"
    )
    assert results["vector_search_results"][0]["score"] == 0.23943702876567796


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
    print("reset_response = ", reset_response)
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
    # mock_db.relational.get_user_by_id.return_value = create_user(
    #     UserCreate(email="profile@example.com", password="password")
    # )
    # profile = r2r_client.user()

    # assert profile["results"]["email"] == "profile@example.com"

    # Update user profile
    updated_profile = r2r_client.update_user(name="John Doe", bio="Test bio")
    assert updated_profile["results"]["name"] == "John Doe"
    assert updated_profile["results"]["bio"] == "Test bio"


@pytest.mark.asyncio
async def test_get_documents_in_group(r2r_client, mock_db):
    # Register and login as a superuser
    user_data = {"email": "superuser@example.com", "password": "password123"}
    r2r_client.register(**user_data)

    # Set the mock user as a superuser
    # mock_db.relational.get_user_by_email.return_value.is_superuser = True

    r2r_client.login(**user_data)

    # Get documents in group
    group_id = uuid.uuid4()
    response = r2r_client.get_documents_in_group(group_id)

    assert "results" in response
    assert len(response["results"]) == 100  # Default limit
    assert response["results"][0]["title"] == "Document 0"
    assert response["results"][0]["type"] == "txt"
