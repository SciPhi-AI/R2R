"""
Tests for the prompts commands in the CLI.
    - list
    - retrieve
    x delete
"""

import json
import uuid

import pytest
from click.testing import CliRunner

from cli.commands.prompts import list, retrieve
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
async def test_prompts_list():
    """Test listing prompts."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    # Test basic list
    list_result = await async_invoke(runner, list, obj=client)
    assert list_result.exit_code == 0


@pytest.mark.asyncio
async def test_prompts_retrieve():
    """Test retrieving prompts with various parameters."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    # Test retrieve with just name
    name = "hyde"
    retrieve_result = await async_invoke(runner, retrieve, name, obj=client)
    assert retrieve_result.exit_code == 0


@pytest.mark.asyncio
async def test_nonexistent_prompt():
    """Test operations on a nonexistent prompt."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    nonexistent_name = f"nonexistent-{uuid.uuid4()}"

    # Test retrieve
    retrieve_result = await async_invoke(
        runner, retrieve, nonexistent_name, obj=client
    )
    assert "not found" in retrieve_result.stderr_bytes.decode().lower()


@pytest.mark.asyncio
async def test_prompt_retrieve_with_all_options():
    """Test retrieving a prompt with all options combined."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    name = "example-prompt"
    inputs = "input1,input2"
    override = "custom prompt text"

    retrieve_result = await async_invoke(
        runner,
        retrieve,
        name,
        "--inputs",
        inputs,
        "--prompt-override",
        override,
        obj=client,
    )
    assert retrieve_result.exit_code == 0
