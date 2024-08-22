import logging
from pathlib import Path
from typing import Optional

import toml

from .app import R2RApp
from .assembly.config import R2RConfig
from .engine import R2REngine

logger = logging.getLogger(__name__)


def get_version_from_pyproject():
    try:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "r") as f:
            pyproject_data = toml.load(f)
        return pyproject_data["tool"]["poetry"]["version"]
    except Exception as e:
        logger.warning(f"Failed to read version from pyproject.toml: {e}")
        return "unknown"


class R2R:
    engine: R2REngine
    app: R2RApp

    def __init__(
        self,
        engine: Optional[R2REngine] = None,
        app: Optional[R2RApp] = None,
        config: Optional[R2RConfig] = None,
        config_name: Optional[str] = None,
        config_path: Optional[str] = None,
        *args,
        **kwargs,
    ):
        version = get_version_from_pyproject()
        logger.info(f"Starting R2R with version {version}")
        if engine and app:
            self.engine = engine
            self.app = app
        else:
            from .assembly.builder import R2RBuilder

            builder = R2RBuilder(
                config=config,
                config_name=config_name,
                config_path=config_path,
            )
            built = builder.build()
            self.engine = built.engine
            self.app = built.app

    def __getattr__(self, name):
        # Check if the attribute name is 'app' and return it directly
        if name == "app":
            return self.app
        elif name == "serve":
            return self.app.serve
        elif name == "fapp":
            return self.app.app
        # Otherwise, delegate to the engine
        return getattr(self.engine, name)
