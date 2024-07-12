import uuid
from datetime import datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from r2r import AuthConfig, DatabaseConfig, DatabaseProvider, User, UserCreate
from r2r.providers import R2RAuthProvider


class MockRelationalDB:
    def __init__(self):
        self.users = {}
        self.verification_codes = {}

    def get_user_by_email(self, email):
        return self.users.get(email)

    def create_user(self, user):
        self.users[user.email] = user
        return user

    def store_verification_code(self, user_id, verification_code, expiry):
        self.verification_codes[verification_code] = (user_id, expiry)

    def get_user_id_by_verification_code(self, verification_code):
        return self.verification_codes.get(verification_code, (None, None))[0]

    def mark_user_as_verified(self, user_id):
        for user in self.users.values():
            if user.id == user_id:
                user.is_verified = True
                break

    def remove_verification_code(self, verification_code):
        self.verification_codes.pop(verification_code, None)


class MockVectorDB:
    def __init__(self):
        pass  # Add vector-specific methods if needed


class MockDatabaseProvider(DatabaseProvider):
    def __init__(self, config):
        self.relational = MockRelationalDB()
        self.vector = MockVectorDB()
        super().__init__(config)

    def _initialize_vector_db(self):
        return self.vector

    def _initialize_relational_db(self):
        return self.relational


@pytest.fixture
def auth_config():
    return AuthConfig(
        secret_key="wNFbczH3QhUVcPALwtWZCPi0lrDlGV3P1DPRVEQCPbM",
        token_lifetime=30,
    )


@pytest.fixture
def mock_db_provider():
    config = DatabaseConfig(provider="postgres", extra_fields={})
    return MockDatabaseProvider(config)


@pytest.fixture
def auth_handler(auth_config, mock_db_provider):
    return R2RAuthProvider(auth_config, mock_db_provider)


def test_password_hashing_and_verification(auth_handler):
    password = "secure_password123"
    hashed_password = auth_handler.get_password_hash(password)

    assert auth_handler.verify_password(password, hashed_password)
    assert not auth_handler.verify_password("wrong_password", hashed_password)


def test_token_encoding_and_decoding(auth_handler):
    email = "test@example.com"
    token = auth_handler.create_access_token({"sub": email})

    token_data = auth_handler.decode_token(token)
    assert token_data.email == email


def test_token_expiration(auth_handler):
    email = "test@example.com"
    token = auth_handler.create_access_token({"sub": email})

    # Fast-forward time by modifying the token's exp claim
    payload = jwt.decode(token, options={"verify_signature": False})
    payload["exp"] = datetime.utcnow() - timedelta(seconds=1)
    expired_token = jwt.encode(
        payload, auth_handler.secret_key, algorithm="HS256"
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_handler.decode_token(expired_token)

    assert exc_info.value.status_code == 401
    assert "Token has expired" in str(exc_info.value.detail)


def test_invalid_token(auth_handler):
    with pytest.raises(HTTPException) as exc_info:
        auth_handler.decode_token("invalid_token")

    assert exc_info.value.status_code == 401
    assert "Invalid token" in str(exc_info.value.detail)


def test_generate_secret_key():
    secret_key = R2RAuthProvider.generate_secret_key()
    assert isinstance(secret_key, str)
    assert len(secret_key) > 0


def test_auth_wrapper(auth_handler):
    email = "test@example.com"
    token = auth_handler.create_access_token({"sub": email})

    class MockCredentials:
        def __init__(self, token):
            self.credentials = token

    credentials = MockCredentials(token)

    result = auth_handler.auth_wrapper(credentials)
    assert result.email == email


def test_auth_wrapper_invalid_token(auth_handler):
    class MockCredentials:
        def __init__(self, token):
            self.credentials = token

    credentials = MockCredentials("invalid_token")

    with pytest.raises(HTTPException) as exc_info:
        auth_handler.auth_wrapper(credentials)

    assert exc_info.value.status_code == 401
    assert "Invalid token" in str(exc_info.value.detail)


def test_env_variable_usage(monkeypatch, mock_db_provider):
    monkeypatch.setenv("R2R_SECRET_KEY", "env_secret")
    monkeypatch.setenv("R2R_TOKEN_LIFETIME", "60")

    config = AuthConfig()
    auth_handler = R2RAuthProvider(config, mock_db_provider)
    assert auth_handler.secret_key == "env_secret"
    assert auth_handler.token_lifetime == 60


def test_fallback_to_config_secret(mock_db_provider, auth_config):
    auth_handler = R2RAuthProvider(auth_config, mock_db_provider)
    assert auth_handler.secret_key == "wNFbczH3QhUVcPALwtWZCPi0lrDlGV3P1DPRVEQCPbM"
    assert auth_handler.token_lifetime == 30



def test_user_registration(auth_handler, mock_db_provider):
    user = UserCreate(email="test@example.com", password="password123")
    result = auth_handler.register_user(user)
    assert "User created" in result["message"]
    assert (
        mock_db_provider.relational.get_user_by_email("test@example.com")
        is not None
    )


def test_user_login(auth_handler, mock_db_provider):
    user = UserCreate(email="test@example.com", password="password123")
    auth_handler.register_user(user)

    # Simulate email verification
    db_user = mock_db_provider.relational.get_user_by_email("test@example.com")
    db_user.is_verified = True

    token_data = auth_handler.login("test@example.com", "password123")
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    with pytest.raises(HTTPException):
        auth_handler.login("test@example.com", "wrong_password")


def test_get_current_user(auth_handler, mock_db_provider):
    user = UserCreate(email="test@example.com", password="password123")
    auth_handler.register_user(user)

    # Simulate email verification
    db_user = mock_db_provider.relational.get_user_by_email("test@example.com")
    db_user.is_verified = True

    token_data = auth_handler.login("test@example.com", "password123")
    token = token_data["access_token"]

    current_user = auth_handler.get_current_user(token)
    assert current_user.email == "test@example.com"


def test_get_current_active_user(auth_handler, mock_db_provider):
    user = UserCreate(email="test@example.com", password="password123")
    created_user = auth_handler.register_user(user)

    # Simulate email verification
    db_user = mock_db_provider.relational.get_user_by_email("test@example.com")
    db_user.is_verified = True
    db_user.is_active = True

    active_user = auth_handler.get_current_active_user(db_user)
    assert active_user.email == "test@example.com"

    # Test with an inactive user
    inactive_user = User(
        id=str(uuid.uuid4()),
        email="inactive@example.com",
        hashed_password="hashed",
        is_active=False,
        is_verified=True,
    )
    with pytest.raises(HTTPException):
        auth_handler.get_current_active_user(inactive_user)


def test_verify_email(auth_handler, mock_db_provider):
    user = UserCreate(email="test@example.com", password="password123")
    auth_handler.register_user(user)

    # Get the verification code
    verification_code = next(
        iter(mock_db_provider.relational.verification_codes.keys())
    )

    result = auth_handler.verify_email(verification_code)
    assert "Email verified successfully" in result["message"]

    updated_user = mock_db_provider.relational.get_user_by_email(
        "test@example.com"
    )
    assert updated_user.is_verified
    assert (
        verification_code not in mock_db_provider.relational.verification_codes
    )


def test_verify_email_invalid_code(auth_handler):
    with pytest.raises(HTTPException) as exc_info:
        auth_handler.verify_email("invalid_code")

    assert exc_info.value.status_code == 400
    assert "Invalid or expired verification code" in str(exc_info.value.detail)
