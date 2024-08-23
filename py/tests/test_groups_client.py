import uuid
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient

from core import R2RApp, R2RBuilder, R2REngine, Token, UserResponse
from core.base import GroupResponse
from r2r import R2RClient

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def create_superuser(email: str, password: str):
    return UserResponse(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        email=email,
        hashed_password="hashed_" + password,
        is_active=True,
        is_superuser=True,
        is_verified=True,
        name="Test Superuser",
        bio="Test Superuser Bio",
        profile_picture="http://example.com/superuser_pic.jpg",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture(scope="function")
def mock_auth_wrapper():
    def auth_wrapper(token: str = Depends(oauth2_scheme)):
        return UserResponse(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            email="admin@example.com",
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
    db.relational.create_user.side_effect = create_superuser
    db.relational.get_user_by_id.return_value = create_superuser(
        email="admin@example.com", password="adminpassword"
    )

    def mock_update_user(user):
        return UserResponse(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            email=user.email,
            hashed_password="hashed_password",
            is_active=True,
            is_superuser=True,
            is_verified=True,
            name=user.name,
            bio=user.bio,
            profile_picture=user.profile_picture,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    db.relational.update_user.side_effect = mock_update_user

    def mock_create_group(**kwargs):
        return GroupResponse(
            group_id=uuid.uuid4(),
            name=kwargs.get("name", "Test Group"),
            description=kwargs.get("description", "A test group"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ).dict()

    db.relational.create_group = MagicMock(side_effect=mock_create_group)

    def mock_get_group(group_id):
        return GroupResponse(
            group_id=group_id,
            name="Test Group",
            description="A test group",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ).dict()

    db.relational.get_group = MagicMock(side_effect=mock_get_group)

    def mock_update_group(group_id, name, description):
        return GroupResponse(
            group_id=group_id,
            name=name,
            description=description,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ).dict()

    db.relational.update_group = MagicMock(side_effect=mock_update_group)

    db.relational.delete_group = MagicMock(return_value=True)

    def mock_list_groups(offset=0, limit=100):
        return [
            GroupResponse(
                group_id=uuid.uuid4(),
                name=f"Group {i}",
                description=f"Description {i}",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ).dict()
            for i in range(1, 3)
        ]

    db.relational.list_groups = MagicMock(side_effect=mock_list_groups)

    db.relational.add_user_to_group = MagicMock(return_value=True)
    db.relational.remove_user_from_group = MagicMock(return_value=True)
    db.relational.get_users_in_group = MagicMock(
        return_value=[
            UserResponse(
                id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
                email="test1@gmail.com",
                hashed_password="hashed_password",
                is_active=True,
                is_superuser=True,
                is_verified=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
            UserResponse(
                id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
                email="test2@gmail.com",
                hashed_password="hashed_password",
                is_active=True,
                is_superuser=True,
                is_verified=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
        ]
    )
    db.relational.get_groups_for_user = MagicMock(side_effect=mock_list_groups)

    def mock_groups_overview(group_ids, offset=0, limit=100):
        return [
            {
                "group_id": str(uuid.uuid4()),
                "name": f"Group {i}",
                "description": f"Description {i}",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "user_count": i * 2,
                "document_count": i * 2,
            }
            for i in range(1, 3)
        ]

    db.relational.get_groups_overview = MagicMock(
        side_effect=mock_groups_overview
    )

    return db


@pytest.fixture(scope="function")
def r2r_client(app_client):
    return R2RClient(base_url="http://testserver", custom_client=app_client)


def authenticate_superuser(r2r_client, mock_db):
    user_data = {"email": "admin@example.com", "password": "adminpassword"}
    mock_db.relational.get_user_by_email.return_value = None
    r2r_client.register(**user_data)

    # Create a superuser
    superuser = UserResponse(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        email=user_data["email"],
        hashed_password="hashed_" + user_data["password"],
        is_active=True,
        is_superuser=True,
        verification_code_expiry=None,
    )

    mock_db.relational.get_user_by_email.return_value = superuser
    mock_db.relational.get_user_by_id.return_value = superuser

    # Login as superuser
    response = r2r_client.login(**user_data)
    assert "access_token" in response["results"]


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

    engine.asearch = mock_asearch
    app = R2RApp(engine)
    return TestClient(app.app)


@pytest.fixture
def group_id():
    return uuid.uuid4()


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_user_profile(r2r_client, mock_db):
    r2r_client.register(email="profile@example.com", password="password123")
    r2r_client.login(email="profile@example.com", password="password123")

    updated_profile = r2r_client.update_user(name="John Doe", bio="Test bio")
    assert updated_profile["results"]["name"] == "John Doe"
    assert updated_profile["results"]["bio"] == "Test bio"


# TODO - Revive these tests later.
# def test_create_group(r2r_client, mock_db):
#     authenticate_superuser(r2r_client, mock_db)
#     group_data = {"name": "Test Group", "description": "A test group"}
#     response = r2r_client.create_group(**group_data)
#     assert "results" in response
#     print('response = ', response)
#     assert response["results"]["name"] == group_data["name"]
#     assert response["results"]["description"] == group_data["description"]
#     mock_db.relational.create_group.assert_called_once_with(**group_data)


@pytest.mark.asyncio
async def test_get_group(r2r_client, mock_db, group_id):
    authenticate_superuser(r2r_client, mock_db)
    response = r2r_client.get_group(group_id)
    assert "results" in response
    assert response["results"]["group_id"] == str(group_id)
    assert response["results"]["name"] == "Test Group"
    mock_db.relational.get_group.assert_called_once_with(group_id)


@pytest.mark.asyncio
async def test_update_group(r2r_client, mock_db, group_id):
    authenticate_superuser(r2r_client, mock_db)
    update_data = {
        "name": "Test Group",
        "description": "An updated test group",
    }
    # mock_db.relational.update_group.return_value = True
    response = r2r_client.update_group(group_id, **update_data)
    assert "results" in response
    assert (
        response["results"]["description"] == "An updated test group"
    )  # is True
    mock_db.relational.update_group.assert_called_once_with(
        *(group_id, "Test Group", "An updated test group")
    )


@pytest.mark.asyncio
async def test_list_groups(r2r_client, mock_db):
    authenticate_superuser(r2r_client, mock_db)
    # mock_db.relational.list_groups.return_value = mock_groups
    response = r2r_client.list_groups(0, 100)
    assert "results" in response
    assert len(response["results"]) == 2

    mock_db.relational.list_groups.assert_called_once_with(offset=0, limit=100)


@pytest.mark.asyncio
async def test_get_users_in_group(r2r_client, mock_db, group_id):
    authenticate_superuser(r2r_client, mock_db)
    response = r2r_client.get_users_in_group(group_id)
    assert "results" in response
    assert len(response["results"]) == 2
    mock_db.relational.get_users_in_group.assert_called_once_with(
        group_id, offset=0, limit=100
    )


# @pytest.mark.asyncio
# async def test_get_groups_for_user(r2r_client, mock_db, user_id):
#     authenticate_superuser(r2r_client, mock_db)
#     # mock_groups = [
#     #     {"id": str(uuid.uuid4()), "name": "Group 1"},
#     #     {"id": str(uuid.uuid4()), "name": "Group 2"},
#     # ]
#     # mock_db.relational.get_groups_for_user.return_value = mock_groups
#     response = r2r_client.user_groups(user_id)
#     assert "results" in response
#     assert len(response["results"]) == 2
#     # assert response["results"] == mock_groups
#     mock_db.relational.get_groups_for_user.assert_called_once_with(user_id, offset=0, limit=100)


@pytest.mark.asyncio
async def test_groups_overview(r2r_client, mock_db):
    authenticate_superuser(r2r_client, mock_db)
    # mock_overview = [
    #     {"id": str(uuid.uuid4()), "name": "Group 1", "member_count": 5},
    #     {"id": str(uuid.uuid4()), "name": "Group 2", "member_count": 3},
    # ]
    # mock_db.relational.get_groups_overview.return_value = mock_overview
    response = r2r_client.groups_overview()
    assert "results" in response
    assert len(response["results"]) == 2
    # assert response["results"] == mock_overview
    mock_db.relational.get_groups_overview.assert_called_once_with(
        None, offset=0, limit=100
    )


@pytest.mark.asyncio
async def test_groups_overview_with_ids(r2r_client, mock_db):
    authenticate_superuser(r2r_client, mock_db)
    group_ids = [uuid.uuid4(), uuid.uuid4()]
    # mock_overview = [
    #     {"id": str(group_ids[0]), "name": "Group 1", "member_count": 5},
    #     {"id": str(group_ids[1]), "name": "Group 2", "member_count": 3},
    # ]
    # mock_db.relational.get_groups_overview.return_value = mock_overview
    response = r2r_client.groups_overview(group_ids, 10, 100)
    assert "results" in response
    assert len(response["results"]) == 2
    # assert response["results"] == mock_overview
    mock_db.relational.get_groups_overview.assert_called_once_with(
        [str(gid) for gid in group_ids], offset=10, limit=100
    )
