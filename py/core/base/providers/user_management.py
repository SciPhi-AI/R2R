from typing import Optional
from pydantic import Field, field_validator, BaseModel
from .base import Provider, ProviderConfig
from abc import ABC


Limit = Optional[int]


class RoleLimits(BaseModel):
    max_files: Limit = Field(
        default=None,
        description="Number of files allowed (None for no limit)",
    )
    max_chunks: Limit = Field(
        default=None,
        description="Number of chunks allowed (None for no limit)",
    )
    max_queries: Limit = Field(
        default=None,
        description="Number of queries allowed (None for no limit)",
    )
    max_queries_window: Limit = Field(
        default=None, description="Query window size (None for no limit)"
    )

    @field_validator(
        "max_files",
        "max_chunks",
        "max_queries",
        "max_queries_window",
        mode="before",
    )
    def parse_limit(cls, v):
        return None if v is None or v == "inf" or v == float("inf") else v

    def has_limit(self, field: str) -> bool:
        """Check if a particular field has a numerical limit."""
        return getattr(self, field) is not None

    def get_limit(self, field: str) -> Optional[int]:
        """Get the numerical limit for a field, or None if no limit."""
        return getattr(self, field)


class UserManagementConfig(ProviderConfig):
    default_role: str = "default"
    roles: dict[str, RoleLimits] = {
        "default": RoleLimits(),
    }

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r"]

    def validate_config(self) -> None:
        if self.default_role not in self.roles:
            raise ValueError(
                f"Default role '{self.default_role}' not found in roles configuration"
            )

    def get_role_limits(self, role: str) -> RoleLimits:
        default_limits = self.roles[self.default_role]

        if role == self.default_role:
            return default_limits

        custom_limits = self.roles.get(role, RoleLimits())

        return RoleLimits(
            max_files=(
                custom_limits.max_files
                if custom_limits.has_limit("max_files")
                else default_limits.max_files
            ),
            max_chunks=(
                custom_limits.max_chunks
                if custom_limits.has_limit("max_chunks")
                else default_limits.max_chunks
            ),
            max_queries=(
                custom_limits.max_queries
                if custom_limits.has_limit("max_queries")
                else default_limits.max_queries
            ),
            max_queries_window=(
                custom_limits.max_queries_window
                if custom_limits.has_limit("max_queries_window")
                else default_limits.max_queries_window
            ),
        )


class UserManagementProvider(Provider, ABC):
    def __init__(self, config: UserManagementConfig):
        if not isinstance(config, UserManagementConfig):
            raise ValueError(
                "UserManagementProvider must be initialized with a UserManagementConfig"
            )
        print(f"UserManagementProvider config: {config}")
        super().__init__(config)
        self.config: UserManagementConfig = config

    def check_limit(
        self, role: str, limit_type: str, current_value: int
    ) -> bool:
        """Check if a particular action would exceed the role's limits."""
        limits = self.config.get_role_limits(role)
        limit = limits.get_limit(limit_type)
        return limit is None or current_value < limit
