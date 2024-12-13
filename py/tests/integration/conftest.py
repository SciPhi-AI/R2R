# tests/conftest.py
import asyncio
import uuid
from typing import AsyncGenerator, Generator

import pytest

from r2r import R2RClient


class TestConfig:
    def __init__(self):
        self.base_url = "http://localhost:7272"
        self.index_wait_time = 1.0
        self.chunk_creation_wait_time = 1.0
        self.superuser_email = "admin@example.com"
        self.superuser_password = "change_me_immediately"
        self.test_timeout = 30  # seconds


@pytest.fixture(scope="session")
def config() -> TestConfig:
    return TestConfig()


@pytest.fixture(scope="session")
async def client(config) -> AsyncGenerator[R2RClient, None]:
    """Create a shared client instance for the test session."""
    client = R2RClient(config.base_url)
    yield client
    # Session cleanup if needed


@pytest.fixture
async def superuser_client(
    client: R2RClient, config: TestConfig
) -> AsyncGenerator[R2RClient, None]:
    """Creates a superuser client for tests requiring elevated privileges."""
    await client.users.login(config.superuser_email, config.superuser_password)
    yield client
    await client.users.logout()
