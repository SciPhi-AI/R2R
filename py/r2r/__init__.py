import logging
from importlib import metadata

from sdk.async_client import R2RAsyncClient
from sdk.models import R2RException
from sdk.sync_client import R2RClient

logger = logging.getLogger()

__version__ = metadata.version("r2r")

__all__ = [
    "R2RAsyncClient",
    "R2RClient",
    "__version__",
    "R2RException",
]

try:
    import core
    from core import *

    __all__ += core.__all__
except ImportError as e:
    logger.warning(
        f"Warning: encountered ImportError: `{e}`, likely due to core dependencies not being installed. This will not affect your use of SDK, but use of `r2r serve` may not be available."
    )


# Add a function to get the version
def get_version():
    return __version__
