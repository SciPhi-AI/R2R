import logging
from pathlib import Path

import toml

from sdk.client import R2RClient
from sdk.client_async import R2RAsyncClient
from sdk.models import R2RException

logger = logging.getLogger(__name__)

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
