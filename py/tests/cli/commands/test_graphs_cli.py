"""
Tests for the graphs commands in the CLI.
    - list
    - retrieve
    - reset
    - update
    - list-entities
    - get-entity
    x remove-entity
    - list-relationships
    - get-relationship
    x remove-relationship
    - build
    - list-communities
    - get-community
    x update-community
    x delete-community
    - pull
    - remove-document
"""

import json
import uuid

import pytest
from click.testing import CliRunner

from cli.commands.collections import create as create_collection
from cli.commands.graphs import (
    build,
    delete_community,
    get_community,
    get_entity,
    get_relationship,
    list,
    list_communities,
    list_entities,
    list_relationships,
    pull,
    remove_document,
    remove_entity,
    remove_relationship,
    reset,
    retrieve,
    update,
    update_community,
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


async def create_test_collection(
    runner: CliRunner, client: R2RAsyncClient
) -> str:
    """Helper function to create a test collection and return its ID."""
    collection_name = f"test-collection-{uuid.uuid4()}"
    create_result = await async_invoke(
        runner, create_collection, collection_name, obj=client
    )
    response = extract_json_block(create_result.stdout_bytes.decode())
    return response["results"]["id"]


@pytest.mark.asyncio
async def test_graph_basic_operations():
    """Test basic graph operations: retrieve, reset, update."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    collection_id = await create_test_collection(runner, client)

    try:
        # Retrieve graph
        retrieve_result = await async_invoke(
            runner, retrieve, collection_id, obj=client
        )
        assert retrieve_result.exit_code == 0
        assert collection_id in retrieve_result.stdout_bytes.decode()

        # Update graph
        new_name = "Updated Graph Name"
        new_description = "Updated description"
        update_result = await async_invoke(
            runner,
            update,
            collection_id,
            "--name",
            new_name,
            "--description",
            new_description,
            obj=client,
        )
        assert update_result.exit_code == 0

        # Reset graph
        reset_result = await async_invoke(
            runner, reset, collection_id, obj=client
        )
        assert reset_result.exit_code == 0

    finally:
        # Cleanup will be handled by collection deletion
        pass


@pytest.mark.asyncio
async def test_graph_entity_operations():
    """Test entity-related operations in a graph."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    collection_id = await create_test_collection(runner, client)

    try:
        # List entities (empty initially)
        list_entities_result = await async_invoke(
            runner, list_entities, collection_id, obj=client
        )
        assert list_entities_result.exit_code == 0

        # Test with pagination
        paginated_result = await async_invoke(
            runner,
            list_entities,
            collection_id,
            "--offset",
            "0",
            "--limit",
            "2",
            obj=client,
        )
        assert paginated_result.exit_code == 0

        # Test nonexistent entity operations
        nonexistent_entity_id = str(uuid.uuid4())
        get_entity_result = await async_invoke(
            runner,
            get_entity,
            collection_id,
            nonexistent_entity_id,
            obj=client,
        )
        assert "not found" in get_entity_result.stderr_bytes.decode().lower()

    finally:
        # Cleanup will be handled by collection deletion
        pass


@pytest.mark.asyncio
async def test_graph_relationship_operations():
    """Test relationship-related operations in a graph."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    collection_id = await create_test_collection(runner, client)

    try:
        # List relationships
        list_rel_result = await async_invoke(
            runner, list_relationships, collection_id, obj=client
        )
        assert list_rel_result.exit_code == 0

        # Test with pagination
        paginated_result = await async_invoke(
            runner,
            list_relationships,
            collection_id,
            "--offset",
            "0",
            "--limit",
            "2",
            obj=client,
        )
        assert paginated_result.exit_code == 0

        # Test nonexistent relationship operations
        nonexistent_rel_id = str(uuid.uuid4())
        get_rel_result = await async_invoke(
            runner,
            get_relationship,
            collection_id,
            nonexistent_rel_id,
            obj=client,
        )
        assert "not found" in get_rel_result.stderr_bytes.decode().lower()

    finally:
        # Cleanup will be handled by collection deletion
        pass


@pytest.mark.asyncio
async def test_graph_community_operations():
    """Test community-related operations in a graph."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    collection_id = await create_test_collection(runner, client)

    try:
        # List communities
        list_comm_result = await async_invoke(
            runner, list_communities, collection_id, obj=client
        )
        assert list_comm_result.exit_code == 0

        # Test with pagination
        paginated_result = await async_invoke(
            runner,
            list_communities,
            collection_id,
            "--offset",
            "0",
            "--limit",
            "2",
            obj=client,
        )
        assert paginated_result.exit_code == 0

        # Test nonexistent community operations
        nonexistent_comm_id = str(uuid.uuid4())
        get_comm_result = await async_invoke(
            runner,
            get_community,
            collection_id,
            nonexistent_comm_id,
            obj=client,
        )
        assert "not found" in get_comm_result.stderr_bytes.decode().lower()

    finally:
        # Cleanup will be handled by collection deletion
        pass


@pytest.mark.asyncio
async def test_graph_build_and_pull():
    """Test graph building and document pull operations."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    collection_id = await create_test_collection(runner, client)

    try:
        # Test build with minimal settings
        settings = {"some_setting": "value"}
        build_result = await async_invoke(
            runner,
            build,
            collection_id,
            "--settings",
            json.dumps(settings),
            obj=client,
        )
        assert build_result.exit_code == 0

        # Test pull documents
        pull_result = await async_invoke(
            runner, pull, collection_id, obj=client
        )
        assert pull_result.exit_code == 0

        # Test remove document (with nonexistent document)
        nonexistent_doc_id = str(uuid.uuid4())
        remove_doc_result = await async_invoke(
            runner,
            remove_document,
            collection_id,
            nonexistent_doc_id,
            obj=client,
        )
        assert "not found" in remove_doc_result.stderr_bytes.decode().lower()

    finally:
        # Cleanup will be handled by collection deletion
        pass


@pytest.mark.asyncio
async def test_list_graphs():
    """Test listing graphs."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    try:
        # Test basic list
        list_result = await async_invoke(runner, list, obj=client)
        assert list_result.exit_code == 0

    finally:
        # Cleanup will be handled by collection deletion
        pass
