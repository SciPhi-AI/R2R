from typing import Optional

from .app import R2RApp
from .assembly.config import R2RConfig
from .engine import R2REngine


class R2R:
    engine: R2REngine
    app: R2RApp

    def __init__(
        self,
        engine: Optional[R2REngine] = None,
        app: Optional[R2RApp] = None,
        config: Optional[R2RConfig] = None,
        from_config: Optional[str] = None,
        *args,
        **kwargs
    ):
        if engine and app:
            self.engine = engine
            self.app = app
        elif (config or from_config) or (
            config is None and from_config is None
        ):
            from .assembly.builder import R2RBuilder

            # Handle the case where 'from_config' is None and 'config' is None
            if not config and not from_config:
                from_config = "default"
            builder = R2RBuilder(
                config=config,
                from_config=from_config,
            )
            built = builder.build()
            self.engine = built.engine
            self.app = built.app
        else:
            raise ValueError(
                "Must provide either 'engine' and 'app', or 'config'/'from_config' to build the R2R object."
            )

    def __getattr__(self, name):
        # Check if the attribute name is 'app' and return it directly
        if name == "app":
            return self.app
        elif name == "serve":
            return self.app.serve
        # Otherwise, delegate to the engine
        return getattr(self.engine, name)
