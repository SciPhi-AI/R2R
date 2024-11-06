from abc import ABC, abstractmethod
from typing import Dict, Optional
from pydantic import BaseModel

from .base import Provider, ProviderConfig


class RoleLimits(BaseModel):
    max_files: Optional[int] = None
    max_chunks: Optional[int] = None
    max_queries: Optional[int] = None
    max_queries_window: Optional[int] = None


class UserManagementConfig(ProviderConfig):
    default_role: str = "default"
    roles: Dict[str, RoleLimits] = {
        "default": RoleLimits(),
        "basic": RoleLimits(
            max_files=1000,
            max_chunks=10000,
            max_queries=1000,
            max_queries_window=1440,
        ),
    }

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r"]

    def validate_config(self) -> None:
        if not self.default_role in self.roles:
            raise ValueError(
                f"Default role '{self.default_role}' not found in roles configuration"
            )

    def get_role_limits(self, role: str) -> RoleLimits:
        if role not in self.roles:
            return self.roles[self.default_role]
        return self.roles[role]


class UserManagementProvider(Provider, ABC):
    def __init__(self, config: UserManagementConfig):
        if not isinstance(config, UserManagementConfig):
            raise ValueError(
                "UserManagementProvider must be initialized with a UserManagementConfig"
            )
        print(f"UserManagementProvider config: {config}")
        super().__init__(config)
        self.config: UserManagementConfig = config
