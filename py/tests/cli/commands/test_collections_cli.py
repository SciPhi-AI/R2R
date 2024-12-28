"""
Tests for the collection commands in the CLI.
    - create
    - list
    - retrieve
    - delete
    - list-documents
    - list-users
"""

import json
import uuid

import pytest
from click.testing import CliRunner

from cli.commands.collections import (
    create,
    delete,
    list,
    list_documents,
    list_users,
    retrieve,
)
from r2r import R2RAsyncClient
from tests.cli.async_invoke import async_invoke


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
async def test_collection_lifecycle():
    """Test the complete lifecycle of a collection: create, retrieve, delete."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    collection_name = f"test-collection-{uuid.uuid4()}"
    description = "Test collection description"

    # Create collection
    create_result = await async_invoke(
        runner,
        create,
        collection_name,
        "--description",
        description,
        obj=client,
    )
    assert create_result.exit_code == 0, create_result.stdout_bytes.decode()

    output = create_result.stdout_bytes.decode()
    create_response = extract_json_block(output)
    collection_id = create_response["results"]["id"]

    try:
        # Retrieve collection
        retrieve_result = await async_invoke(
            runner, retrieve, collection_id, obj=client
        )
        assert retrieve_result.exit_code == 0
        retrieve_output = retrieve_result.stdout_bytes.decode()
        assert collection_id in retrieve_output

        # List documents in collection
        list_docs_result = await async_invoke(
            runner, list_documents, collection_id, obj=client
        )
        assert list_docs_result.exit_code == 0

        # List users in collection
        list_users_result = await async_invoke(
            runner, list_users, collection_id, obj=client
        )
        assert list_users_result.exit_code == 0
    finally:
        # Delete collection
        delete_result = await async_invoke(
            runner, delete, collection_id, obj=client
        )
        assert delete_result.exit_code == 0


@pytest.mark.asyncio
async def test_list_collections():
    """Test listing collections with various parameters."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    # Create test collection first
    create_result = await async_invoke(
        runner, create, f"test-collection-{uuid.uuid4()}", obj=client
    )
    response = extract_json_block(create_result.stdout_bytes.decode())
    collection_id = response["results"]["id"]

    try:
        # Test basic list
        list_result = await async_invoke(runner, list, obj=client)
        assert list_result.exit_code == 0

        # Get paginated results just to verify they exist
        list_paginated = await async_invoke(
            runner, list, "--offset", "0", "--limit", "2", obj=client
        )
        assert list_paginated.exit_code == 0

    finally:
        # Cleanup
        await async_invoke(runner, delete, collection_id, obj=client)


@pytest.mark.asyncio
async def test_nonexistent_collection():
    """Test operations on a nonexistent collection."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    nonexistent_id = str(uuid.uuid4())

    # Test retrieve
    retrieve_result = await async_invoke(
        runner, retrieve, nonexistent_id, obj=client
    )
    # Updated assertion to match actual error message
    assert (
        "the specified collection does not exist."
        in retrieve_result.stderr_bytes.decode().lower()
    )

    # Test list_documents
    list_docs_result = await async_invoke(
        runner, list_documents, nonexistent_id, obj=client
    )
    assert (
        "collection not found"
        in list_docs_result.stderr_bytes.decode().lower()
    )

    # Test list_users
    list_users_result = await async_invoke(
        runner, list_users, nonexistent_id, obj=client
    )
    assert (
        "collection not found"
        in list_users_result.stderr_bytes.decode().lower()
    )
