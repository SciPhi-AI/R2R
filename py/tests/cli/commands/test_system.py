"""
Tests for the system commands in the CLI.
    - health
    - settings
    - status
    x serve
    x image exists
    x docker down
    x generate report
    x update
    - version

"""

import json
import pytest
from click.testing import CliRunner
from cli.commands.system import health, settings, status, version
from tests.cli.async_invoke import async_invoke
from r2r import R2RAsyncClient
from importlib.metadata import version as get_version


@pytest.mark.asyncio
async def test_health_against_server():
    """Test health check against a real server."""
    # Create real client
    client = R2RAsyncClient(base_url="http://localhost:7272")

    # Run command
    runner = CliRunner(mix_stderr=False)
    result = await async_invoke(runner, health, obj=client)

    # Extract just the JSON part (everything after the "Time taken" line)
    output = result.stdout_bytes.decode()
    json_str = output.split("\n", 1)[1]

    # Basic validation
    response_data = json.loads(json_str)
    assert "results" in response_data
    assert "message" in response_data["results"]
    assert response_data["results"]["message"] == "ok"
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_health_server_down():
    """Test health check when server is unreachable."""
    client = R2RAsyncClient(base_url="http://localhost:54321")  # Invalid port
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, health, obj=client)
    assert result.exit_code != 0
    assert (
        "Request failed: All connection attempts failed"
        in result.stderr_bytes.decode()
    )


@pytest.mark.asyncio
async def test_health_invalid_url():
    """Test health check with invalid URL."""
    client = R2RAsyncClient(base_url="http://invalid.localhost")
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, health, obj=client)
    assert result.exit_code != 0
    assert "Request failed" in result.stderr_bytes.decode()


@pytest.mark.asyncio
async def test_settings_against_server():
    """Test settings retrieval against a real server."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, settings, obj=client)

    # Extract JSON part after "Time taken" line
    output = result.stdout_bytes.decode()
    json_str = output.split("\n", 1)[1]

    # Validate response structure
    response_data = json.loads(json_str)
    assert "results" in response_data
    assert "config" in response_data["results"]
    assert "prompts" in response_data["results"]

    # Validate key configuration sections
    config = response_data["results"]["config"]
    assert "completion" in config
    assert "database" in config
    assert "embedding" in config
    assert "ingestion" in config

    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_settings_server_down():
    """Test settings retrieval when server is unreachable."""
    client = R2RAsyncClient(base_url="http://localhost:54321")  # Invalid port
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, settings, obj=client)
    assert result.exit_code != 0
    assert (
        "Request failed: All connection attempts failed"
        in result.stderr_bytes.decode()
    )


@pytest.mark.asyncio
async def test_settings_invalid_url():
    """Test settings retrieval with invalid URL."""
    client = R2RAsyncClient(base_url="http://invalid.localhost")
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, settings, obj=client)
    assert result.exit_code != 0
    assert "Request failed" in result.stderr_bytes.decode()


@pytest.mark.asyncio
async def test_settings_response_structure():
    """Test detailed structure of settings response."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, settings, obj=client)
    output = result.stdout_bytes.decode()
    json_str = output.split("\n", 1)[1]
    response_data = json.loads(json_str)

    # Validate prompts structure
    prompts = response_data["results"]["prompts"]
    assert "results" in prompts
    assert "total_entries" in prompts
    assert isinstance(prompts["results"], list)

    # Validate prompt entries
    for prompt in prompts["results"]:
        assert "name" in prompt
        assert "id" in prompt
        assert "template" in prompt
        assert "input_types" in prompt
        assert "created_at" in prompt
        assert "updated_at" in prompt

    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_settings_config_validation():
    """Test specific configuration values in settings response."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, settings, obj=client)
    output = result.stdout_bytes.decode()
    json_str = output.split("\n", 1)[1]
    response_data = json.loads(json_str)

    config = response_data["results"]["config"]

    # Validate completion config
    completion = config["completion"]
    assert "provider" in completion
    assert "concurrent_request_limit" in completion
    assert "generation_config" in completion

    # Validate database config
    database = config["database"]
    assert "provider" in database
    assert "default_collection_name" in database
    assert "limits" in database

    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_status_against_server():
    """Test status check against a real server."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, status, obj=client)

    # Extract JSON part after "Time taken" line
    output = result.stdout_bytes.decode()
    json_str = output.split("\n", 1)[1]

    # Validate response structure
    response_data = json.loads(json_str)
    assert "results" in response_data

    # Validate specific fields
    results = response_data["results"]
    assert "start_time" in results
    assert "uptime_seconds" in results
    assert "cpu_usage" in results
    assert "memory_usage" in results

    # Validate data types
    assert isinstance(results["uptime_seconds"], (int, float))
    assert isinstance(results["cpu_usage"], (int, float))
    assert isinstance(results["memory_usage"], (int, float))

    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_status_server_down():
    """Test status check when server is unreachable."""
    client = R2RAsyncClient(base_url="http://localhost:54321")  # Invalid port
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, status, obj=client)
    assert result.exit_code != 0
    assert (
        "Request failed: All connection attempts failed"
        in result.stderr_bytes.decode()
    )


@pytest.mark.asyncio
async def test_status_invalid_url():
    """Test status check with invalid URL."""
    client = R2RAsyncClient(base_url="http://invalid.localhost")
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, status, obj=client)
    assert result.exit_code != 0
    assert "Request failed" in result.stderr_bytes.decode()


@pytest.mark.asyncio
async def test_status_value_ranges():
    """Test that status values are within expected ranges."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, status, obj=client)
    output = result.stdout_bytes.decode()
    json_str = output.split("\n", 1)[1]
    response_data = json.loads(json_str)

    results = response_data["results"]

    # CPU usage should be between 0 and 100
    assert 0 <= results["cpu_usage"] <= 100

    # Memory usage should be between 0 and 100
    assert 0 <= results["memory_usage"] <= 100

    # Uptime should be positive
    assert results["uptime_seconds"] > 0

    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_status_start_time_format():
    """Test that start_time is in correct ISO format."""
    client = R2RAsyncClient(base_url="http://localhost:7272")
    runner = CliRunner(mix_stderr=False)

    result = await async_invoke(runner, status, obj=client)
    output = result.stdout_bytes.decode()
    json_str = output.split("\n", 1)[1]
    response_data = json.loads(json_str)

    from datetime import datetime

    # Verify start_time is valid ISO format
    start_time = response_data["results"]["start_time"]
    try:
        datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    except ValueError:
        pytest.fail("start_time is not in valid ISO format")

    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_version_command():
    """Test basic version command functionality."""
    runner = CliRunner()
    result = await async_invoke(runner, version)

    # Verify command succeeded
    assert result.exit_code == 0

    # Verify output is valid JSON and matches actual package version
    expected_version = get_version("r2r")
    actual_version = json.loads(result.stdout_bytes.decode())
    assert actual_version == expected_version


@pytest.mark.asyncio
async def test_version_output_format():
    """Test that version output is properly formatted JSON."""
    runner = CliRunner()
    result = await async_invoke(runner, version)

    # Verify output is valid JSON
    try:
        output = result.stdout_bytes.decode()
        parsed = json.loads(output)
        assert isinstance(parsed, str)  # Version should be a string
    except json.JSONDecodeError:
        pytest.fail("Version output is not valid JSON")

    # Should be non-empty output ending with newline
    assert output.strip()
    assert output.endswith("\n")


@pytest.mark.asyncio
async def test_version_error_handling(monkeypatch):
    """Test error handling when version import fails."""

    def mock_version(_):
        raise ImportError("Package not found")

    # Mock the version function to raise an error
    monkeypatch.setattr("importlib.metadata.version", mock_version)

    runner = CliRunner(mix_stderr=False)
    result = await async_invoke(runner, version)

    # Verify command failed with exception
    assert result.exit_code == 1
    error_output = result.stderr_bytes.decode()
    assert "An unexpected error occurred" in error_output
    assert "Package not found" in error_output
