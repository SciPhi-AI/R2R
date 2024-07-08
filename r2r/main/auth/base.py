import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


class AuthHandler:
    security = HTTPBearer()

    def __init__(
        self, secret: Optional[str] = None, token_lifetime: int = 1440
    ):
        self.secret = (
            os.getenv("R2R_SECRET_KEY", None)
            or secret
            or self.generate_secret_key()
        )
        self.lifetime = int(
            os.getenv("R2R_TOKEN_LIFETIME", None) or token_lifetime
        )

    def get_password_hash(self, password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def verify_password(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    def encode_token(self, user_id: str) -> str:
        payload = {
            "exp": datetime.utcnow() + timedelta(minutes=self.lifetime),
            "iat": datetime.utcnow(),
            "sub": user_id,
        }
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def decode_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self.secret, algorithms=["HS256"])
            return payload["sub"]
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401, detail="Signature has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def auth_wrapper(
        self, auth: HTTPAuthorizationCredentials = Security(security)
    ):
        return self.decode_token(auth.credentials)

    @staticmethod
    def generate_secret_key(length=32):
        import base64
        import secrets

        return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode(
            "utf-8"
        )