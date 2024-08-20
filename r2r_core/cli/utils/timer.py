"""
A timer context manager to measure the time taken to execute each command in the CLI.
"""

import time
from contextlib import contextmanager

import click


@contextmanager
def timer():
    start = time.time()
    yield
    end = time.time()
    click.echo(f"Time taken: {end - start:.2f} seconds")
