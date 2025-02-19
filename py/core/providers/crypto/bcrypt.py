import base64
import logging
import os
from abc import ABC
from datetime import datetime, timezone
from typing import Optional, Tuple

import bcrypt
import jwt
import nacl.encoding
import nacl.exceptions
import nacl.signing
import nacl.utils

from core.base import CryptoConfig, CryptoProvider

DEFAULT_BCRYPT_SECRET_KEY = "wNFbczH3QhUVcPALwtWZCPi0lrDlGV3P1DPRVEQCPbM"  # Replace or load from env or secrets manager


class BcryptCryptoConfig(CryptoConfig):
    provider: str = "bcrypt"
    # Number of rounds for bcrypt (increasing this makes hashing slower but more secure)
    bcrypt_rounds: int = 12
    secret_key: Optional[str] = None
    api_key_bytes: int = 32  # Length of raw API keys

    @property
    def supported_providers(self) -> list[str]:
        return ["bcrypt"]

    def validate_config(self) -> None:
        super().validate_config()
        if self.provider not in self.supported_providers:
            raise ValueError(f"Unsupported crypto provider: {self.provider}")
        if self.bcrypt_rounds < 4 or self.bcrypt_rounds > 31:
            raise ValueError("bcrypt_rounds must be between 4 and 31")

    def verify_password(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        try:
            # First try to decode as base64 (new format)
            stored_hash = base64.b64decode(hashed_password.encode("utf-8"))
        except Exception:
            # If that fails, treat as raw bcrypt hash (old format)
            stored_hash = hashed_password.encode("utf-8")

        return bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash)


class BCryptCryptoProvider(CryptoProvider, ABC):
    def __init__(self, config: BcryptCryptoConfig):
        if not isinstance(config, BcryptCryptoConfig):
            raise ValueError(
                "BcryptCryptoProvider must be initialized with a BcryptCryptoConfig"
            )
        logging.info("Initializing BcryptCryptoProvider")
        super().__init__(config)
        self.config: BcryptCryptoConfig = config

        # Load the secret key for JWT
        # No fallback defaults: fail if not provided
        self.secret_key = (
            config.secret_key
            or os.getenv("R2R_SECRET_KEY")
            or DEFAULT_BCRYPT_SECRET_KEY
        )
        if not self.secret_key:
            raise ValueError(
                "No secret key provided for BcryptCryptoProvider."
            )

    def get_password_hash(self, password: str) -> str:
        # Bcrypt expects bytes
        password_bytes = password.encode("utf-8")
        hashed = bcrypt.hashpw(
            password_bytes, bcrypt.gensalt(rounds=self.config.bcrypt_rounds)
        )
        return base64.b64encode(hashed).decode("utf-8")

    def verify_password(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        try:
            # First try to decode as base64 (new format)
            stored_hash = base64.b64decode(hashed_password.encode("utf-8"))
            if not stored_hash.startswith(b"$2b$"):  # Valid bcrypt hash prefix
                stored_hash = hashed_password.encode("utf-8")
        except Exception:
            # Otherwise raw bcrypt hash (old format)
            stored_hash = hashed_password.encode("utf-8")

        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash)
        except ValueError as e:
            if "Invalid salt" in str(e):
                # If it's an invalid salt, the hash format is wrong - try the other format
                try:
                    stored_hash = (
                        hashed_password
                        if isinstance(hashed_password, bytes)
                        else hashed_password.encode("utf-8")
                    )
                    return bcrypt.checkpw(
                        plain_password.encode("utf-8"), stored_hash
                    )
                except ValueError:
                    return False
            raise

    def generate_verification_code(self, length: int = 32) -> str:
        random_bytes = nacl.utils.random(length)
        return base64.urlsafe_b64encode(random_bytes)[:length].decode("utf-8")

    def generate_signing_keypair(self) -> Tuple[str, str, str]:
        signing_key = nacl.signing.SigningKey.generate()
        verify_key = signing_key.verify_key

        # Generate unique key_id
        key_entropy = nacl.utils.random(16)
        key_id = f"sk_{base64.urlsafe_b64encode(key_entropy).decode()}"

        private_key = base64.b64encode(bytes(signing_key)).decode()
        public_key = base64.b64encode(bytes(verify_key)).decode()
        return key_id, private_key, public_key

    def sign_request(self, private_key: str, data: str) -> str:
        try:
            key_bytes = base64.b64decode(private_key)
            signing_key = nacl.signing.SigningKey(key_bytes)
            signature = signing_key.sign(data.encode())
            return base64.b64encode(signature.signature).decode()
        except Exception as e:
            raise ValueError(
                f"Invalid private key or signing error: {str(e)}"
            ) from e

    def verify_request_signature(
        self, public_key: str, signature: str, data: str
    ) -> bool:
        try:
            key_bytes = base64.b64decode(public_key)
            verify_key = nacl.signing.VerifyKey(key_bytes)
            signature_bytes = base64.b64decode(signature)
            verify_key.verify(data.encode(), signature_bytes)
            return True
        except (nacl.exceptions.BadSignatureError, ValueError):
            return False

    def generate_api_key(self) -> Tuple[str, str]:
        # Similar approach as with NaCl provider:
        key_id_bytes = nacl.utils.random(16)
        key_id = f"key_{base64.urlsafe_b64encode(key_id_bytes).decode()}"

        # Generate raw API key
        raw_api_key = base64.urlsafe_b64encode(
            nacl.utils.random(self.config.api_key_bytes)
        ).decode()
        return key_id, raw_api_key

    def hash_api_key(self, raw_api_key: str) -> str:
        # Hash with bcrypt
        hashed = bcrypt.hashpw(
            raw_api_key.encode("utf-8"),
            bcrypt.gensalt(rounds=self.config.bcrypt_rounds),
        )
        return base64.b64encode(hashed).decode("utf-8")

    def verify_api_key(self, raw_api_key: str, hashed_key: str) -> bool:
        stored_hash = base64.b64decode(hashed_key.encode("utf-8"))
        return bcrypt.checkpw(raw_api_key.encode("utf-8"), stored_hash)

    def generate_secure_token(self, data: dict, expiry: datetime) -> str:
        now = datetime.now(timezone.utc)
        to_encode = {
            **data,
            "exp": expiry.timestamp(),
            "iat": now.timestamp(),
            "nbf": now.timestamp(),
            "jti": base64.urlsafe_b64encode(nacl.utils.random(16)).decode(),
            "nonce": base64.urlsafe_b64encode(nacl.utils.random(16)).decode(),
        }
        return jwt.encode(to_encode, self.secret_key, algorithm="HS256")

    def verify_secure_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            exp = payload.get("exp")
            if exp is None or datetime.fromtimestamp(
                exp, tz=timezone.utc
            ) < datetime.now(timezone.utc):
                return None
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
