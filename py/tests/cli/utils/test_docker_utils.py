import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli.utils.docker_utils import (
    bring_down_docker_compose,
    build_docker_command,
    check_llm_reqs,
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
        8000,
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
