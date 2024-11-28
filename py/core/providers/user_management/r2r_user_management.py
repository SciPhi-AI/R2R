from core.base.providers.user_management import (
    UserManagementProvider,
    UserManagementConfig,
    RoleLimits,
)


class R2RUserManagementProvider(UserManagementProvider):
    def __init__(self, config: UserManagementConfig):
        super().__init__(config)
        self.roles = config.roles
        self.default_role = config.default_role
        print(
            f"Initialized R2RUserManagementProvider with roles: {self.roles}"
        )

    def get_role_limits(self, role: str) -> RoleLimits:
        return self.config.get_role_limits(role)
