from pathlib import Path

import toml

from sdk import *

pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
pyproject_data = toml.load(pyproject_path)
__version__ = pyproject_data["tool"]["poetry"]["version"]


__all__ = [
    # R2R SDK
    "R2RAsyncClient",
    "R2RClient",
    "__version__",
]

# try:
import core
from core import *

__all__ += core.__all__
# except ImportError:
#     # Core dependencies not installed
#     pass


# Add a function to get the version
def get_version():
    return __version__
