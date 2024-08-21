import pytest
from cli.commands.auth import generate_private_key
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


def test_generate_private_key(runner):
    result = runner.invoke(generate_private_key)
    assert result.exit_code == 0
    assert "Generated Private Key:" in result.output
    assert (
        "Keep this key secure and use it as your R2R_SECRET_KEY."
        in result.output
    )


def test_generate_private_key_output_format(runner):
    result = runner.invoke(generate_private_key)
    key_line = [
        line
        for line in result.output.split("\n")
        if "Generated Private Key:" in line
    ][0]
    key = key_line.split(":")[1].strip()
    assert len(key) > 32  # The key should be reasonably long
    assert (
        key.isalnum() or "-" in key or "_" in key
    )  # The key should be URL-safe
