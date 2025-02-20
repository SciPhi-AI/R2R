from importlib import metadata

from sdk.async_client import R2RAsyncClient
from sdk.models import (
    CitationEvent,
    FinalAnswerEvent,
    MessageEvent,
    R2RException,
    SearchResultsEvent,
)
from sdk.sync_client import R2RClient

__version__ = metadata.version("r2r")

__all__ = [
    "R2RAsyncClient",
    "R2RClient",
    "__version__",
    "R2RException",
    "CitationEvent",
    "FinalAnswerEvent",
    "MessageEvent",
    "SearchResultsEvent",
]


def get_version():
    return __version__
