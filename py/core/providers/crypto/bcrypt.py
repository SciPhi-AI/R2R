import secrets
import string

from core.base import CryptoConfig, CryptoProvider


class BCryptConfig(CryptoConfig):
    salt_rounds: int = 12

    def validate(self) -> None:
        super().validate()
        if self.salt_rounds < 4 or self.salt_rounds > 31:
            raise ValueError("salt_rounds must be between 4 and 31")


class BCryptProvider(CryptoProvider):
    def __init__(self, config: BCryptConfig):
        try:
            import bcrypt

            self.bcrypt = bcrypt
        except ImportError:
            raise ImportError("bcrypt must be installed to use BCryptProvider")

        if not isinstance(config, BCryptConfig):
            raise ValueError(
                "BCryptProvider must be initialized with a BCryptConfig"
            )
        super().__init__(config)

    def get_password_hash(self, password: str) -> str:
        return self.bcrypt.hashpw(
            password.encode("utf-8"),
            self.bcrypt.gensalt(rounds=self.config.salt_rounds),
        ).decode("utf-8")

    def verify_password(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        return self.bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    def generate_verification_code(self, length: int = 32) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))
