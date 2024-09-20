# tests/providers/auth/test_r2r_auth_provider.py
import pytest

from core.base import R2RException


@pytest.mark.asyncio
async def test_register_and_login(r2r_auth_provider):
    email = "test@example.com"
    password = "password123"
    user = await r2r_auth_provider.register(email, password)
    assert user.email == email
    tokens = await r2r_auth_provider.login(email, password)
    assert "access_token" in tokens
    assert "refresh_token" in tokens


@pytest.mark.asyncio
async def test_invalid_login(r2r_auth_provider):
    email = "test@example.com"
    password = "password123"
    await r2r_auth_provider.register(email, password)
    with pytest.raises(R2RException):
        await r2r_auth_provider.login(email, "wrong_password")


@pytest.mark.asyncio
async def test_refresh_access_token(r2r_auth_provider):
    email = "test@example.com"
    password = "password123"
    await r2r_auth_provider.register(email, password)
    tokens = await r2r_auth_provider.login(email, password)
    new_tokens = await r2r_auth_provider.refresh_access_token(
        tokens["refresh_token"].token
    )
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens


@pytest.mark.asyncio
async def test_change_password(r2r_auth_provider):
    email = "test@example.com"
    password = "password123"
    new_password = "new_password456"
    user = await r2r_auth_provider.register(email, password)
    await r2r_auth_provider.change_password(user, password, new_password)
    tokens = await r2r_auth_provider.login(email, new_password)
    assert "access_token" in tokens
    assert "refresh_token" in tokens


@pytest.mark.asyncio
async def test_logout(r2r_auth_provider):
    email = "test@example.com"
    password = "password123"
    await r2r_auth_provider.register(email, password)
    tokens = await r2r_auth_provider.login(email, password)
    await r2r_auth_provider.logout(tokens["access_token"].token)
    with pytest.raises(R2RException):
        await r2r_auth_provider.decode_token(tokens["access_token"].token)
