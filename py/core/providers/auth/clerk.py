import logging
import os
from datetime import datetime

from core.base import (
    AuthConfig,
    CryptoProvider,
    EmailProvider,
    R2RException,
    TokenData,
)

from ..database import PostgresDatabaseProvider
from .jwt import JwtAuthProvider

logger = logging.getLogger(__name__)


class ClerkAuthProvider(JwtAuthProvider):
    """
    ClerkAuthProvider extends JwtAuthProvider to support token verification with Clerk.
    It uses Clerk's SDK to verify the JWT token and extract user information.
    """

    def __init__(
        self,
        config: AuthConfig,
        crypto_provider: CryptoProvider,
        database_provider: PostgresDatabaseProvider,
        email_provider: EmailProvider,
    ):
        super().__init__(
            config=config,
            crypto_provider=crypto_provider,
            database_provider=database_provider,
            email_provider=email_provider,
        )
        try:
            from clerk_backend_api.jwks_helpers.verifytoken import (
                VerifyTokenOptions,
                verify_token,
            )

            self.verify_token = verify_token
            self.VerifyTokenOptions = VerifyTokenOptions
        except ImportError as e:
            raise R2RException(
                status_code=500,
                message="Clerk SDK is not installed. Run `pip install clerk-backend-api`",
            ) from e

    async def decode_token(self, token: str) -> TokenData:
        """
        Decode and verify the JWT token using Clerk's verify_token function.

        Args:
            token: The JWT token to decode

        Returns:
            TokenData: The decoded token data with user information

        Raises:
            R2RException: If the token is invalid or verification fails
        """
        clerk_secret_key = os.getenv("CLERK_SECRET_KEY")
        if not clerk_secret_key:
            raise R2RException(
                status_code=500,
                message="CLERK_SECRET_KEY environment variable is not set",
            )

        try:
            # Configure verification options
            options = self.VerifyTokenOptions(
                secret_key=clerk_secret_key,
                # Optional: specify audience if needed
                # audience="your-audience",
                # Optional: specify authorized parties if needed
                # authorized_parties=["https://your-domain.com"]
            )

            # Verify the token using Clerk's SDK
            payload = self.verify_token(token, options)

            # Check for the expected claims in the token payload
            if not payload.get("sub") or not payload.get("email"):
                raise R2RException(
                    status_code=401,
                    message="Invalid token: missing required claims",
                )

            # Create user in database if not exists
            try:
                await self.database_provider.users_handler.get_user_by_email(
                    payload.get("email")
                )
                # TODO do we want to update user info here based on what's in the token?
            except Exception:
                # user doesn't exist, create in db
                logger.debug(f"Creating new user: {payload.get('email')}")
                try:
                    # Construct name from first_name and last_name if available
                    first_name = payload.get("first_name", "")
                    last_name = payload.get("last_name", "")
                    name = payload.get("name")

                    # If name not directly provided, try to build it from first and last names
                    if not name and (first_name or last_name):
                        name = f"{first_name} {last_name}".strip()

                    await self.database_provider.users_handler.create_user(
                        email=payload.get("email"),
                        account_type="external",
                        name=name,
                    )
                except Exception as e:
                    logger.error(f"Error creating user: {e}")
                    raise R2RException(
                        status_code=500, message="Failed to create user"
                    ) from e

            # Return the token data
            return TokenData(
                email=payload.get("email"),
                token_type="bearer",
                exp=datetime.fromtimestamp(payload.get("exp")),
            )

        except Exception as e:
            logger.info(f"Clerk token verification failed: {e}")
            raise R2RException(
                status_code=401, message="Invalid token", detail=str(e)
            ) from e
