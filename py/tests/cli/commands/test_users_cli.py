"""
Tests for the user commands in the CLI.
    - create
    - list
    - retrieve
    - me
    x list-collections
    x add-to-collection
    x remove-from-collection
"""

import json
import pytest
import uuid
from click.testing import CliRunner
from cli.commands.users import (
    create,
    list,
    retrieve,
    me,
    list_collections,
    add_to_collection,
    remove_from_collection,
)
from tests.cli.async_invoke import async_invoke
from r2r import R2RAsyncClient


def extract_json_block(output: str) -> dict:
    """Extract and parse the first valid JSON object found in the output."""
    start = output.find("{")
    if start == -1:
        raise ValueError("No JSON object start found in output")

    brace_count = 0
    for i, char in enumerate(output[start:], start=start):
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1

            if brace_count == 0:
                json_str = output[start : i + 1].strip()
                return json.loads(json_str)
    raise ValueError("No complete JSON object found in output")


@pytest.mark.asyncio
async def test_user_lifecycle():
    """Test the complete lifecycle of a user: create, retrieve, list, collections."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    # Create test user with random email
    test_email = f"test_{uuid.uuid4()}@example.com"
    test_password = "TestPassword123!"

    # Create user
    create_result = await async_invoke(
        runner, create, test_email, test_password, obj=client
    )
    assert create_result.exit_code == 0, create_result.stdout_bytes.decode()

    output = create_result.stdout_bytes.decode()
    create_response = extract_json_block(output)
    user_id = create_response["results"]["id"]

    try:
        # List users and verify our new user is included
        list_result = await async_invoke(runner, list, obj=client)
        assert list_result.exit_code == 0, list_result.stdout_bytes.decode()
        list_output = list_result.stdout_bytes.decode()
        assert test_email in list_output

        # Retrieve specific user
        retrieve_result = await async_invoke(
            runner, retrieve, user_id, obj=client
        )
        assert (
            retrieve_result.exit_code == 0
        ), retrieve_result.stdout_bytes.decode()
        retrieve_output = retrieve_result.stdout_bytes.decode()
        retrieve_response = extract_json_block(retrieve_output)
        assert retrieve_response["results"]["email"] == test_email

        # Test me endpoint
        me_result = await async_invoke(runner, me, obj=client)
        assert me_result.exit_code == 0, me_result.stdout_bytes.decode()

        # List collections for user
        collections_result = await async_invoke(
            runner, list_collections, user_id, obj=client
        )
        assert (
            collections_result.exit_code == 0
        ), collections_result.stdout_bytes.decode()

    finally:
        # We don't delete the user since there's no delete command
        pass


# FIXME: This should be returning 'User not found' but returns an empty list instead.
# @pytest.mark.asyncio
# async def test_retrieve_nonexistent_user():
#     """Test retrieving a user that doesn't exist."""
#     client = R2RAsyncClient(base_url="http://localhost:7272")
#     runner = CliRunner(mix_stderr=False)

#     nonexistent_id = str(uuid.uuid4())
#     result = await async_invoke(runner, retrieve, nonexistent_id, obj=client)

#     assert result.exit_code != 0
#     error_output = result.stderr_bytes.decode()
#     assert "User not found" in error_output


# FIXME: This is returning with a status of 0 but has a 400 on the server side?
# @pytest.mark.asyncio
# async def test_create_duplicate_user():
#     """Test creating a user with an email that already exists."""
#     client = R2RAsyncClient(base_url="http://localhost:7272")
#     runner = CliRunner(mix_stderr=False)

#     test_email = f"test_{uuid.uuid4()}@example.com"
#     test_password = "TestPassword123!"

#     # Create first user
#     first_result = await async_invoke(
#         runner, create, test_email, test_password, obj=client
#     )
#     assert first_result.exit_code == 0

#     # Try to create second user with same email
#     second_result = await async_invoke(
#         runner, create, test_email, test_password, obj=client
#     )
#     print(f"SECOND RESULT: {second_result}")
#     assert second_result.exit_code != 0
#     error_output = second_result.stderr_bytes.decode()
#     assert "already exists" in error_output.lower()
