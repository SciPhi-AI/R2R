"""
Tests for the retrieval commands in the CLI.
    - search
    - rag
"""

import json
import tempfile

import pytest
from click.testing import CliRunner

from cli.commands.documents import create as create_document
from cli.commands.retrieval import rag, search
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


async def create_test_document(
    runner: CliRunner, client: R2RAsyncClient
) -> str:
    """Helper function to create a test document and return its ID."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as f:
        f.write(
            "This is a test document about artificial intelligence and machine learning. "
            "AI systems can be trained on large datasets to perform various tasks."
        )
        temp_path = f.name

    create_result = await async_invoke(
        runner, create_document, temp_path, obj=client
    )
    response = extract_json_block(create_result.stdout_bytes.decode())
    return response["results"]["document_id"]


@pytest.mark.asyncio
async def test_basic_search():
    """Test basic search functionality."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    # Create test document first
    document_id = await create_test_document(runner, client)

    try:
        # Test basic search
        search_result = await async_invoke(
            runner,
            search,
            "--query",
            "artificial intelligence",
            "--limit",
            "5",
            obj=client,
        )
        assert search_result.exit_code == 0
        assert "Vector search results:" in search_result.stdout_bytes.decode()

    finally:
        # Cleanup will be handled by document deletion in a real implementation
        pass


@pytest.mark.asyncio
async def test_search_with_filters():
    """Test search with filters."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    document_id = await create_test_document(runner, client)

    try:
        filters = json.dumps({"document_id": {"$in": [document_id]}})
        search_result = await async_invoke(
            runner,
            search,
            "--query",
            "machine learning",
            "--filters",
            filters,
            "--limit",
            "5",
            obj=client,
        )
        assert search_result.exit_code == 0
        output = search_result.stdout_bytes.decode()
        assert "Vector search results:" in output
        assert document_id in output

    finally:
        pass


@pytest.mark.asyncio
async def test_search_with_advanced_options():
    """Test search with advanced options."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    document_id = await create_test_document(runner, client)

    try:
        search_result = await async_invoke(
            runner,
            search,
            "--query",
            "AI systems",
            "--use-hybrid-search",
            "true",
            "--search-strategy",
            "vanilla",
            "--graph-search-enabled",
            "true",
            "--chunk-search-enabled",
            "true",
            obj=client,
        )
        assert search_result.exit_code == 0
        output = search_result.stdout_bytes.decode()
        assert "Vector search results:" in output

    finally:
        pass


@pytest.mark.asyncio
async def test_basic_rag():
    """Test basic RAG functionality."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    document_id = await create_test_document(runner, client)

    try:
        rag_result = await async_invoke(
            runner,
            rag,
            "--query",
            "What is this document about?",
            obj=client,
        )
        assert rag_result.exit_code == 0

    finally:
        pass


@pytest.mark.asyncio
async def test_rag_with_streaming():
    """Test RAG with streaming enabled."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    document_id = await create_test_document(runner, client)

    try:
        rag_result = await async_invoke(
            runner,
            rag,
            "--query",
            "What is this document about?",
            "--stream",
            obj=client,
        )
        assert rag_result.exit_code == 0

    finally:
        pass


@pytest.mark.asyncio
async def test_rag_with_model_specification():
    """Test RAG with specific model."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    document_id = await create_test_document(runner, client)

    try:
        rag_result = await async_invoke(
            runner,
            rag,
            "--query",
            "What is this document about?",
            "--rag-model",
            "azure/gpt-4o-mini",
            obj=client,
        )
        assert rag_result.exit_code == 0

    finally:
        pass
