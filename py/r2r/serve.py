import asyncio
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from core import R2RApp, R2RBuilder, R2RConfig
    from core.utils.logging_config import configure_logging
except ImportError as e:
    logger.error(
        f"Failed to start server: core dependencies not installed: {e}"
    )
    logger.error("To run the server, install the required dependencies:")
    logger.error("pip install 'r2r[core]'")
    sys.exit(1)


async def create_app(
    config_name: Optional[str] = None,
    config_path: Optional[str] = None,
    full: bool = False,
) -> "R2RApp":
    config_name = config_name or os.getenv("R2R_CONFIG_NAME")
    config_path = config_path or os.getenv("R2R_CONFIG_PATH")

    if config_path and config_name:
        raise ValueError("Cannot specify both config_path and config_name")
    if not config_path and not config_name:
        config_name = "full" if full else "default"

    try:
        r2r_instance = await R2RBuilder(
            config=R2RConfig.load(config_name, config_path)
        ).build()

        await r2r_instance.orchestration_provider.start_worker()
        return r2r_instance
    except ImportError as e:
        logger.error(f"Failed to initialize R2R: {e}")
        logger.error(
            "Please check your configuration and installed dependencies"
        )
        sys.exit(1)


def run_server(
    host: str = "0.0.0.0",
    port: int = 7272,
    config_name: Optional[str] = None,
    config_path: Optional[str] = None,
    full: bool = False,
):
    try:
        configure_logging()
    except Exception as e:
        logger.error(f"Failed to configure logging: {e}")

    try:
        port = int(os.getenv("R2R_PORT", port))
        host = os.getenv("R2R_HOST", host)

        async def start():
            app = await create_app(config_name, config_path, full)
            await app.serve(host, port)

        asyncio.run(start())
    except Exception as e:
        logger.error(f"Failed to start R2R server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_server()
