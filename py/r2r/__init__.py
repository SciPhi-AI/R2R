import logging
from importlib import metadata

from sdk.async_client import FUSEAsyncClient
from sdk.models import FUSEException
from sdk.sync_client import FUSEClient

logger = logging.getLogger()

__version__ = metadata.version("fuse")

__all__ = [
    "FUSEAsyncClient",
    "FUSEClient",
    "__version__",
    "FUSEException",
]

try:
    import core
    from core import *

    __all__ += core.__all__
except ImportError as e:
    logger.warning(
        f"Warning: encountered ImportError: `{e}`, likely due to core dependencies not being installed. This will not affect your use of SDK, but use of `fuse serve` may not be available."
    )


# Add a function to get the version
def get_version():
    return __version__
