import base64
import logging
import os
import string
from datetime import datetime, timezone
from typing import Optional, Tuple

import jwt
import nacl.encoding
import nacl.exceptions
import nacl.pwhash
import nacl.signing
from nacl.exceptions import BadSignatureError
from nacl.pwhash import argon2i

from core.base import CryptoConfig, CryptoProvider

DEFAULT_NACL_SECRET_KEY = "wNFbczH3QhUVcPALwtWZCPi0lrDlGV3P1DPRVEQCPbM"  # Replace or load from env or secrets manager


def encode_bytes_readable(random_bytes: bytes, chars: str) -> str:
    """Convert random bytes to a readable string using the given character
    set."""
    # Each byte gives us 8 bits of randomness
    # We use modulo to map each byte to our character set
    result = []
    for byte in random_bytes:
        # Use modulo to map the byte (0-255) to our character set length
        idx = byte % len(chars)
        result.append(chars[idx])
    return "".join(result)


class NaClCryptoConfig(CryptoConfig):
    provider: str = "nacl"
    # Interactive parameters for password ops (fast)
    ops_limit: int = argon2i.OPSLIMIT_MIN
    mem_limit: int = argon2i.MEMLIMIT_MIN
    # Sensitive parameters for API key generation (slow but more secure)
    api_ops_limit: int = argon2i.OPSLIMIT_INTERACTIVE
    api_mem_limit: int = argon2i.MEMLIMIT_INTERACTIVE
    api_key_bytes: int = 32
    secret_key: Optional[str] = None


class NaClCryptoProvider(CryptoProvider):
    def __init__(self, config: NaClCryptoConfig):
        if not isinstance(config, NaClCryptoConfig):
            raise ValueError(
                "NaClCryptoProvider must be initialized with a NaClCryptoConfig"
            )
        super().__init__(config)
        self.config: NaClCryptoConfig = config
        logging.info("Initializing NaClCryptoProvider")

        # Securely load the secret key for JWT
        # Priority: config.secret_key > environment variable > default
        self.secret_key = (
            config.secret_key
            or os.getenv("R2R_SECRET_KEY")
            or DEFAULT_NACL_SECRET_KEY
        )

    def get_password_hash(self, password: str) -> str:
        password_bytes = password.encode("utf-8")
        hashed = nacl.pwhash.argon2i.str(
            password_bytes,
            opslimit=self.config.ops_limit,
            memlimit=self.config.mem_limit,
        )
        return base64.b64encode(hashed).decode("utf-8")

    def verify_password(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        try:
            stored_hash = base64.b64decode(hashed_password.encode("utf-8"))
            nacl.pwhash.verify(stored_hash, plain_password.encode("utf-8"))
            return True
        except nacl.exceptions.InvalidkeyError:
            return False

    def generate_verification_code(self, length: int = 32) -> str:
        random_bytes = nacl.utils.random(length)
        return base64.urlsafe_b64encode(random_bytes)[:length].decode("utf-8")

    def generate_api_key(self) -> Tuple[str, str]:
        # Define our character set (excluding ambiguous characters)
        chars = string.ascii_letters.replace("l", "").replace("I", "").replace(
            "O", ""
        ) + string.digits.replace("0", "").replace("1", "")

        # Generate a unique key_id
        key_id_bytes = nacl.utils.random(16)  # 16 random bytes
        key_id = f"pk_{encode_bytes_readable(key_id_bytes, chars)}"

        # Generate a high-entropy API key
        raw_api_key = f"sk_{encode_bytes_readable(nacl.utils.random(self.config.api_key_bytes), chars)}"

        # The caller will store the hashed version in the database
        return key_id, raw_api_key

    def hash_api_key(self, raw_api_key: str) -> str:
        hashed = nacl.pwhash.argon2i.str(
            raw_api_key.encode("utf-8"),
            opslimit=self.config.api_ops_limit,
            memlimit=self.config.api_mem_limit,
        )
        return base64.b64encode(hashed).decode("utf-8")

    def verify_api_key(self, raw_api_key: str, hashed_key: str) -> bool:
        try:
            stored_hash = base64.b64decode(hashed_key.encode("utf-8"))
            nacl.pwhash.verify(stored_hash, raw_api_key.encode("utf-8"))
            return True
        except nacl.exceptions.InvalidkeyError:
            return False

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
        except (BadSignatureError, ValueError):
            return False

    def generate_secure_token(self, data: dict, expiry: datetime) -> str:
        """Generate a secure token using JWT with HS256.

        The secret_key is used for symmetrical signing.
        """
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
        """Verify a secure token using the shared secret_key and JWT."""
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

    def generate_signing_keypair(self) -> Tuple[str, str, str]:
        signing_key = nacl.signing.SigningKey.generate()
        private_key_b64 = base64.b64encode(signing_key.encode()).decode()
        public_key_b64 = base64.b64encode(
            signing_key.verify_key.encode()
        ).decode()
        # Generate a unique key_id
        key_id_bytes = nacl.utils.random(16)
        key_id = f"sign_{base64.urlsafe_b64encode(key_id_bytes).decode()}"
        return (key_id, private_key_b64, public_key_b64)
