from datetime import datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from r2r.main.auth.base import AuthHandler


@pytest.fixture
def auth_handler():
    return AuthHandler(secret="test_secret", token_lifetime=30)


def test_password_hashing_and_verification(auth_handler):
    password = "secure_password123"
    hashed_password = auth_handler.get_password_hash(password)

    assert auth_handler.verify_password(password, hashed_password)
    assert not auth_handler.verify_password("wrong_password", hashed_password)


def test_token_encoding_and_decoding(auth_handler):
    user_id = "test_user"
    token = auth_handler.encode_token(user_id)

    decoded_user_id = auth_handler.decode_token(token)
    assert decoded_user_id == user_id


def test_token_expiration(auth_handler):
    user_id = "test_user"
    token = auth_handler.encode_token(user_id)

    # Fast-forward time by modifying the token's exp claim
    payload = jwt.decode(token, options={"verify_signature": False})
    payload["exp"] = datetime.utcnow() - timedelta(seconds=1)
    expired_token = jwt.encode(payload, auth_handler.secret, algorithm="HS256")

    with pytest.raises(HTTPException) as exc_info:
        auth_handler.decode_token(expired_token)

    assert exc_info.value.status_code == 401
    assert "Signature has expired" in str(exc_info.value.detail)


def test_invalid_token(auth_handler):
    with pytest.raises(HTTPException) as exc_info:
        auth_handler.decode_token("invalid_token")

    assert exc_info.value.status_code == 401
    assert "Invalid token" in str(exc_info.value.detail)


def test_generate_secret_key():
    secret_key = AuthHandler.generate_secret_key()
    assert isinstance(secret_key, str)
    assert len(secret_key) > 0


def test_auth_wrapper(auth_handler):
    user_id = "test_user"
    token = auth_handler.encode_token(user_id)

    # Create a mock HTTPAuthorizationCredentials object
    class MockCredentials:
        def __init__(self, token):
            self.credentials = token

    credentials = MockCredentials(token)

    result = auth_handler.auth_wrapper(credentials)
    assert result == user_id


def test_auth_wrapper_invalid_token(auth_handler):
    # Create a mock HTTPAuthorizationCredentials object with an invalid token
    class MockCredentials:
        def __init__(self, token):
            self.credentials = token

    credentials = MockCredentials("invalid_token")

    with pytest.raises(HTTPException) as exc_info:
        auth_handler.auth_wrapper(credentials)

    assert exc_info.value.status_code == 401
    assert "Invalid token" in str(exc_info.value.detail)


# Test environment variable usage
def test_env_variable_usage(monkeypatch):
    monkeypatch.setenv("R2R_SECRET_KEY", "env_secret")
    monkeypatch.setenv("R2R_TOKEN_LIFETIME", "60")

    auth_handler = AuthHandler()
    assert auth_handler.secret == "env_secret"
    assert auth_handler.lifetime == 60  # Changed from '60' to 60


# Test fallback to generated secret if not provided
def test_fallback_to_generated_secret():
    auth_handler = AuthHandler()
    assert isinstance(auth_handler.secret, str)
    assert len(auth_handler.secret) > 0
