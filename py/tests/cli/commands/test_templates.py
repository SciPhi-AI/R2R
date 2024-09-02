import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_get_templates():
    with patch("cli.commands.templates.get_templates") as mock:
        mock.return_value = ["template1", "template2"]
        yield mock


@pytest.fixture
def mock_clone_operation():
    with patch("cli.commands.templates.clone_template") as mock:
        yield mock


def test_list_templates(runner, mock_get_templates):
    result = runner.invoke(cli, ["list-templates"])
    assert result.exit_code == 0
    assert "Available templates:" in result.output
    assert "template1" in result.output
    assert "template2" in result.output


def test_list_templates_error(runner, mock_get_templates):
    mock_get_templates.side_effect = Exception("Failed to fetch templates")
    result = runner.invoke(cli, ["list-templates"])
    assert result.exit_code != 0
    assert "Error: Failed to fetch templates" in result.output


def test_clone_success(runner, mock_clone_operation):
    result = runner.invoke(cli, ["clone", "template1"])
    assert result.exit_code == 0
    assert "Successfully cloned template 'template1'" in result.output
    mock_clone_operation.assert_called_once_with("template1", None)


def test_clone_with_location(runner, mock_clone_operation):
    result = runner.invoke(cli, ["clone", "template1", "custom_location"])
    assert result.exit_code == 0
    assert (
        "Successfully cloned template 'template1' to custom_location"
        in result.output
    )
    mock_clone_operation.assert_called_once_with(
        "template1", "custom_location"
    )


def test_clone_template_not_found(runner, mock_clone_operation):
    mock_clone_operation.side_effect = ValueError("Template not found")
    result = runner.invoke(cli, ["clone", "non_existent_template"])
    assert result.exit_code != 0
    assert "Error: Template not found" in result.output


def test_clone_unexpected_error(runner, mock_clone_operation):
    mock_clone_operation.side_effect = Exception("Unexpected error")
    result = runner.invoke(cli, ["clone", "template1"])
    assert result.exit_code != 0
    assert "Error: An unexpected error occurred" in result.output
