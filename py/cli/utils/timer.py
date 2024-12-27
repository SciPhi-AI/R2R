"""
A timer context manager to measure the time taken to execute each command in the CLI.
"""

import time
from contextlib import contextmanager

import asyncclick as click


@contextmanager
def timer():
    start = time.time()
    yield
    end = time.time()
    duration = max(0, end - start)
    click.echo(f"Time taken: {duration:.2f} seconds")
