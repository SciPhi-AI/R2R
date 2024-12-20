import asyncio
import time
from unittest.mock import patch

import pytest
import asyncclick as click
from click.testing import CliRunner

from cli.utils.timer import timer
from tests.cli.async_invoke import async_invoke


@click.command()
async def test_command():
    with timer():
        time.sleep(0.1)


@pytest.mark.asyncio
async def test_timer_measures_time():
    runner = CliRunner()
    result = await async_invoke(runner, test_command)
    output = result.stdout_bytes.decode()
    assert "Time taken:" in output
    assert "seconds" in output
    measured_time = float(output.split(":")[1].split()[0])
    assert 0.1 <= measured_time <= 0.2


@click.command()
async def zero_duration_command():
    with timer():
        pass


@pytest.mark.asyncio
async def test_timer_zero_duration():
    runner = CliRunner()
    result = await async_invoke(runner, zero_duration_command)
    output = result.stdout_bytes.decode()
    measured_time = float(output.split(":")[1].split()[0])
    assert measured_time >= 0
    assert measured_time < 0.1


@click.command()
async def exception_command():
    with timer():
        raise ValueError("Test exception")


@pytest.mark.asyncio
async def test_timer_with_exception():
    runner = CliRunner()
    result = await async_invoke(runner, exception_command)
    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)


@click.command()
async def async_command():
    with timer():
        await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_timer_with_async_code():
    runner = CliRunner()
    result = await async_invoke(runner, async_command)
    output = result.stdout_bytes.decode()
    measured_time = float(output.split(":")[1].split()[0])
    assert 0.1 <= measured_time <= 0.2


@click.command()
async def nested_command():
    with timer():
        time.sleep(0.1)
        with timer():
            time.sleep(0.1)


@pytest.mark.asyncio
async def test_timer_multiple_nested():
    runner = CliRunner()
    result = await async_invoke(runner, nested_command)
    output = result.stdout_bytes.decode()
    assert output.count("Time taken:") == 2


@click.command()
async def mock_time_command():
    with timer():
        pass


@pytest.mark.asyncio
@patch("time.time")
async def test_timer_with_mock_time(mock_time):
    mock_time.side_effect = [0, 1]  # Start and end times
    runner = CliRunner()
    result = await async_invoke(runner, mock_time_command)
    output = result.stdout_bytes.decode()
    assert "Time taken: 1.00 seconds" in output


@click.command()
async def precision_command():
    with timer():
        time.sleep(0.1)


@pytest.mark.asyncio
async def test_timer_precision():
    runner = CliRunner()
    result = await async_invoke(runner, precision_command)
    output = result.stdout_bytes.decode()
    assert len(output.split(":")[1].split()[0].split(".")[1]) == 2
