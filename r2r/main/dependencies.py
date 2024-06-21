from typing import Optional

from .assembly.builder import R2RAppBuilder
from .assembly.config import R2RConfig

# Global variable to store the R2RApp instance
r2r_app_instance = None


def get_r2r_config(config_name: Optional[str] = None) -> R2RConfig:
    if config_name:
        config_path = R2RAppBuilder.CONFIG_OPTIONS.get(config_name)
        if not config_path:
            raise ValueError(f"Invalid config name: {config_name}")
        return R2RConfig.from_json(config_path)
    return R2RConfig.from_json()


def get_r2r_app(config_name: Optional[str] = None):
    global r2r_app_instance
    if r2r_app_instance is None:
        config = get_r2r_config(config_name)
        builder = R2RAppBuilder(config=config)
        r2r_app_instance = builder.build()
    return r2r_app_instance
