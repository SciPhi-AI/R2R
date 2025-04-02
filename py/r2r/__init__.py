"""R2R package."""

from importlib import metadata

# Import from core
from core.utils import scan_directory
from sdk.async_client import R2RAsyncClient
from sdk.sync_client import R2RClient
from shared import *
from shared import __all__ as shared_all

__version__ = metadata.version("r2r")

__all__ = [
    "R2RAsyncClient",
    "R2RClient",
    "__version__",
    "R2RException",
    "scan_directory",
] + shared_all


def get_version():
    return __version__
