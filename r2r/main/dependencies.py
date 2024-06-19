from typing import Optional

from .assembly.builder import R2RAppBuilder
from .assembly.config import R2RConfig


def get_r2r_config(config_name: Optional[str] = None) -> R2RConfig:
    if config_name:
        config_path = R2RAppBuilder.CONFIG_OPTIONS.get(config_name)
        if not config_path:
            raise ValueError(f"Invalid config name: {config_name}")
        return R2RConfig.from_json(config_path)
    return R2RConfig.from_json()


def get_r2r_app(config_name: Optional[str] = None):
    config = get_r2r_config(config_name)
    builder = R2RAppBuilder(config=config)
    return builder.build()
