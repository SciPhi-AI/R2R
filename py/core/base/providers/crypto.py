from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Tuple

from .base import Provider, ProviderConfig


class CryptoConfig(ProviderConfig):
    provider: Optional[str] = None

    @property
    def supported_providers(self) -> list[str]:
        return ["bcrypt", "nacl"]

    def validate_config(self) -> None:
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
        """Hash a plaintext password using a secure password hashing algorithm
        (e.g., Argon2i)."""
        pass

    @abstractmethod
    def verify_password(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        """Verify that a plaintext password matches the given hashed
        password."""
        pass

    @abstractmethod
    def generate_verification_code(self, length: int = 32) -> str:
        """Generate a random code for email verification or reset tokens."""
        pass

    @abstractmethod
    def generate_signing_keypair(self) -> Tuple[str, str, str]:
        """Generate a new Ed25519 signing keypair for request signing.

        Returns:
            A tuple of (key_id, private_key, public_key).
            - key_id: A unique identifier for this keypair.
            - private_key: Base64 encoded Ed25519 private key.
            - public_key: Base64 encoded Ed25519 public key.
        """
        pass

    @abstractmethod
    def sign_request(self, private_key: str, data: str) -> str:
        """Sign request data with an Ed25519 private key, returning the
        signature."""
        pass

    @abstractmethod
    def verify_request_signature(
        self, public_key: str, signature: str, data: str
    ) -> bool:
        """Verify a request signature using the corresponding Ed25519 public
        key."""
        pass

    @abstractmethod
    def generate_api_key(self) -> Tuple[str, str]:
        """Generate a new API key for a user.

        Returns:
            A tuple (key_id, raw_api_key):
            - key_id: A unique identifier for the API key.
            - raw_api_key: The plaintext API key to provide to the user.
        """
        pass

    @abstractmethod
    def hash_api_key(self, raw_api_key: str) -> str:
        """Hash a raw API key for secure storage in the database.

        Use strong parameters suitable for long-term secrets.
        """
        pass

    @abstractmethod
    def verify_api_key(self, raw_api_key: str, hashed_key: str) -> bool:
        """Verify that a provided API key matches the stored hashed version."""
        pass

    @abstractmethod
    def generate_secure_token(self, data: dict, expiry: datetime) -> str:
        """Generate a secure, signed token (e.g., JWT) embedding claims.

        Args:
            data: The claims to include in the token.
            expiry: A datetime at which the token expires.

        Returns:
            A JWT string signed with a secret key.
        """
        pass

    @abstractmethod
    def verify_secure_token(self, token: str) -> Optional[dict]:
        """Verify a secure token (e.g., JWT).

        Args:
            token: The token string to verify.

        Returns:
            The token payload if valid, otherwise None.
        """
        pass
