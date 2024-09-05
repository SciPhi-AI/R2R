import os
import subprocess
import sys
from io import StringIO
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli.utils.docker_utils import (
    bring_down_docker_compose,
    build_docker_command,
    check_docker_compose_version,
    check_llm_reqs,
    parse_version,
    remove_r2r_network,
)


@pytest.fixture
def runner():
    return CliRunner()


def test_bring_down_docker_compose(runner):
    with patch("os.system") as mock_system:
        mock_system.return_value = 0
        result = bring_down_docker_compose("test_project", True, True)
        assert result == 0
        mock_system.assert_called_once()


@patch("subprocess.check_output")
@patch("os.system")
def test_remove_r2r_network(mock_system, mock_check_output):
    mock_check_output.return_value = b"r2r_test_network\nother_network"
    mock_system.return_value = 0
    remove_r2r_network()
    mock_system.assert_called_once_with("docker network rm r2r_test_network")


@pytest.mark.parametrize(
    "llm_provider,model_provider,env_vars,expected_exit",
    [
        ("openai", "openai", {"OPENAI_API_KEY": "test"}, False),
        ("openai", "openai", {}, True),
    ],
)
def test_check_llm_reqs(llm_provider, model_provider, env_vars, expected_exit):
    with patch.dict(os.environ, env_vars, clear=True):
        with patch("click.confirm", return_value=False):
            with (
                pytest.raises(SystemExit)
                if expected_exit
                else patch("sys.exit")
            ) as mock_exit:
                check_llm_reqs(llm_provider, model_provider)
                if expected_exit:
                    mock_exit.assert_called_once_with(1)


def test_build_docker_command():
    compose_files = {
        "base": "base.yaml",
        "neo4j": "neo4j.yaml",
        "ollama": "ollama.yaml",
        "postgres": "postgres.yaml",
    }
    command = build_docker_command(
        compose_files,
        "localhost",
        7272,
        False,
        False,
        False,
        "test_project",
        "test_image",
        None,
        None,
    )
    assert (
        "docker compose -f base.yaml -f neo4j.yaml -f ollama.yaml -f postgres.yaml"
        in command
    )
    assert "--project-name test_project" in command
    assert "up -d" in command


@pytest.mark.parametrize(
    "version_output,expected_result,expected_message",
    [
        (
            "Docker Compose version v2.29.0",
            True,
            "Docker Compose version 2.29.0 is compatible.",
        ),
        (
            "Docker Compose version v2.24.5",
            True,
            "Warning: Docker Compose version 2.24.5 is outdated. Please upgrade to version 2.25.0 or higher.",
        ),
        (
            "Docker Compose version v3.0.0",
            True,
            "Docker Compose version 3.0.0 is compatible.",
        ),
        (
            "Docker Compose version 2.29.0",
            True,
            "Docker Compose version 2.29.0 is compatible.",
        ),
        (
            "Docker Compose version 2.29.0-desktop.1",
            True,
            "Docker Compose version 2.29.0 is compatible.",
        ),
    ],
)
def test_check_docker_compose_version_success(
    version_output, expected_result, expected_message
):
    with patch(
        "subprocess.check_output", return_value=version_output.encode()
    ):
        captured_output = StringIO()
        sys.stdout = captured_output
        result = check_docker_compose_version()
        sys.stdout = sys.__stdout__
        assert result == expected_result
        assert expected_message in captured_output.getvalue()


@pytest.mark.parametrize(
    "version_output,expected_message",
    [
        (
            "Docker Compose version unknown",
            "Unexpected version format: Docker Compose version unknown",
        ),
        (
            "Not a valid output",
            "Unexpected version format: Not a valid output",
        ),
    ],
)
def test_check_docker_compose_version_invalid_format(
    version_output, expected_message
):
    with patch(
        "subprocess.check_output", return_value=version_output.encode()
    ):
        captured_output = StringIO()
        sys.stdout = captured_output
        result = check_docker_compose_version()
        sys.stdout = sys.__stdout__
        assert result == False
        assert (
            "Error checking Docker Compose version"
            in captured_output.getvalue()
        )
        assert expected_message in captured_output.getvalue()


def test_check_docker_compose_version_not_installed():
    error_message = "docker: command not found"
    mock_error = subprocess.CalledProcessError(
        1, "docker compose version", error_message.encode()
    )
    with patch("subprocess.check_output", side_effect=mock_error):
        captured_output = StringIO()
        sys.stdout = captured_output
        result = check_docker_compose_version()
        sys.stdout = sys.__stdout__
        assert result == False
        assert (
            "Error: Docker Compose is not installed or not working properly."
            in captured_output.getvalue()
        )
        assert error_message in captured_output.getvalue()


def test_check_docker_compose_version_unexpected_error():
    with patch(
        "subprocess.check_output", side_effect=Exception("Unexpected error")
    ):
        captured_output = StringIO()
        sys.stdout = captured_output
        result = check_docker_compose_version()
        sys.stdout = sys.__stdout__
        assert result == False
        assert (
            "Error checking Docker Compose version: Unexpected error"
            in captured_output.getvalue()
        )
