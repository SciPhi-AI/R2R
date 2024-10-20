import logging
from pathlib import Path

import toml

from sdk.async_client import R2RAsyncClient
from sdk.models import R2RException
from sdk.sync_client import R2RClient

logger = logging.getLogger()

pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
pyproject_data = toml.load(pyproject_path)
__version__ = pyproject_data["tool"]["poetry"]["version"]

__all__ = [
    "R2RAsyncClient",
    "R2RClient",
    "__version__",
    "R2RException",
]


def get_version():
    return __version__
