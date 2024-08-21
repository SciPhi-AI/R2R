import time
from unittest.mock import patch

import pytest
from cli.utils.timer import timer


def test_timer_measures_time():
    with patch("time.time") as mock_time:
        mock_time.side_effect = [0, 0.1]

        @timer()
        def dummy_function():
            time.sleep(0.1)

        with patch("click.echo") as mock_echo:
            dummy_function()
            mock_echo.assert_called_once_with("Time taken: 0.10 seconds")


def test_timer_handles_exceptions():
    @timer()
    def error_function():
        raise ValueError("Test exception")

    with patch("time.time") as mock_time:
        mock_time.side_effect = [0, 0.1]

        with pytest.raises(ValueError, match="Test exception"):
            error_function()


def test_timer_nested():
    with patch("time.time") as mock_time:
        mock_time.side_effect = [0, 0.1, 0.2, 0.3]

        @timer()
        def outer_function():
            time.sleep(0.1)

            @timer()
            def inner_function():
                time.sleep(0.1)

            inner_function()

        with patch("click.echo") as mock_echo:
            outer_function()
            assert mock_echo.call_count == 2
            mock_echo.assert_any_call("Time taken: 0.10 seconds")
            mock_echo.assert_any_call("Time taken: 0.30 seconds")


def test_timer_zero_duration():
    with patch("time.time") as mock_time:
        mock_time.side_effect = [0, 0]

        @timer()
        def quick_function():
            pass

        with patch("click.echo") as mock_echo:
            quick_function()
            mock_echo.assert_called_once_with("Time taken: 0.00 seconds")


def test_timer_as_context_manager():
    with patch("time.time") as mock_time:
        mock_time.side_effect = [0, 0.1]

        def function_with_context():
            with timer():
                time.sleep(0.1)

        with patch("click.echo") as mock_echo:
            function_with_context()
            mock_echo.assert_called_once_with("Time taken: 0.10 seconds")
