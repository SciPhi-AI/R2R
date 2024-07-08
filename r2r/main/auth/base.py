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

    # import os


# from typing import Optional
# from fastapi import HTTPException, Security
# from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
# from passlib.context import CryptContext
# from datetime import datetime, timedelta
# import jwt as pyjwt  # Import PyJWT as pyjwt

# class AuthHandler:
#     security = HTTPBearer()
#     pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#     def __init__(self, secret: Optional[str] = None, token_lifetime: int = 1440):
#         self.secret = os.getenv('R2R_SECRET_KEY', None) or secret or self.generate_secret_key()
#         self.lifetime = os.getenv('R2R_TOKEN_LIFETIME', None) or token_lifetime

#     def get_password_hash(self, password):
#         return self.pwd_context.hash(password)

#     def verify_password(self, plain_password, hashed_password):
#         return self.pwd_context.verify(plain_password, hashed_password)

#     def encode_token(self, user_id):
#         payload = {
#             'exp': datetime.utcnow() + timedelta(minutes=self.lifetime),
#             'iat': datetime.utcnow(),
#             'sub': user_id
#         }
#         return pyjwt.encode(payload, self.secret, algorithm='HS256')

#     def decode_token(self, token):
#         try:
#             payload = pyjwt.decode(token, self.secret, algorithms=['HS256'])
#             return payload['sub']
#         except pyjwt.ExpiredSignatureError:
#             raise HTTPException(status_code=401, detail='Signature has expired')
#         except pyjwt.InvalidTokenError:
#             raise HTTPException(status_code=401, detail='Invalid token')

#     def auth_wrapper(self, auth: HTTPAuthorizationCredentials = Security(security)):
#         return self.decode_token(auth.credentials)

#     @staticmethod
#     def generate_secret_key(length=32):
#         import secrets
#         import base64
#         return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode('utf-8')
# # # auth.py
# # import os
# # from typing import Optional
# # from fastapi import HTTPException, Security
# # from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
# # from passlib.context import CryptContext
# # from datetime import datetime, timedelta
# # import jwt

# # class AuthHandler:
# #     security = HTTPBearer()
# #     pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# #     def __init__(self, secret: Optional[str] = None, token_lifetime: int = 1440):
# #         self.secret = os.getenv('R2R_SECRET_KEY', None) or secret or self.generate_secret_key()
# #         self.lifetime = os.getenv('R2R_TOKEN_LIFETIME', None) or token_lifetime

# #     def get_password_hash(self, password):
# #         return self.pwd_context.hash(password)

# #     def verify_password(self, plain_password, hashed_password):
# #         return self.pwd_context.verify(plain_password, hashed_password)

# #     def encode_token(self, user_id):
# #         payload = {
# #             'exp': datetime.utcnow() + timedelta(days=0, minutes=30),
# #             'iat': datetime.utcnow(),
# #             'sub': user_id
# #         }
# #         return jwt.encode(payload, self.secret, algorithm='HS256')

# #     def decode_token(self, token):
# #         try:
# #             payload = jwt.decode(token, self.secret, algorithms=['HS256'])
# #             return payload['sub']
# #         except jwt.ExpiredSignatureError:
# #             raise HTTPException(status_code=401, detail='Signature has expired')
# #         except jwt.InvalidTokenError:
# #             raise HTTPException(status_code=401, detail='Invalid token')

# #     def auth_wrapper(self, auth: HTTPAuthorizationCredentials = Security(security)):
# #         return self.decode_token(auth.credentials)


# #     @staticmethod
# #     def generate_secret_key(length=32):
# #         import secrets
# #         import base64
# #         """
# #         Generate a secure random secret key.

# #         :param length: The length of the secret key in bytes (default is 32)
# #         :return: A URL-safe base64-encoded string
# #         """
# #         return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode('utf-8')
