from abc import ABC, abstractmethod
from typing import Optional

from .base import Provider, ProviderConfig


class CryptoConfig(ProviderConfig):
    provider: Optional[str] = None

    @property
    def supported_providers(self) -> list[str]:
        return [None, "bcrypt"]  # Add other crypto providers as needed

    def validate(self) -> None:
        super().validate()
        if self.provider not in self.supported_providers:
            raise ValueError(f"Unsupported crypto provider: {self.provider}")


class CryptoProvider(Provider, ABC):
    def __init__(self, config: CryptoConfig):
        if not isinstance(config, CryptoConfig):
            raise ValueError(
                "CryptoProvider must be initialized with a CryptoConfig"
            )
        super().__init__(config)

    @abstractmethod
    def get_password_hash(self, password: str) -> str:
        pass

    @abstractmethod
    def verify_password(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        pass

    @abstractmethod
    def generate_verification_code(self, length: int = 32) -> str:
        pass
