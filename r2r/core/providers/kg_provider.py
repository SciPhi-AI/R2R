from typing import Optional

from .base_provider import ProviderConfig


class KGConfig(ProviderConfig):
    """A base embedding configuration class"""

    provider: Optional[str] = None
    batch_size: int = 1

    @property
    def supported_providers(self) -> list[str]:
        return ["None", "neo4j"]

    def validate(self) -> None:
        if not self.provider:
            raise ValueError("The 'provider' field must be set for KGConfig.")
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")
