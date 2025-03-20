from importlib import metadata

from sdk.async_client import R2RAsyncClient
from sdk.sync_client import R2RClient
from shared import *

__version__ = metadata.version("r2r")

__all__ = [
    "R2RAsyncClient",
    "R2RClient",
    "__version__",
    "R2RException",
]


def get_version():
    return __version__
