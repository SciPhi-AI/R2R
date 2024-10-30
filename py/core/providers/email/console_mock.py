import logging
from typing import Optional

from core.base import EmailProvider

logger = logging.getLogger()


class ConsoleMockEmailProvider(EmailProvider):
    """A simple email provider that logs emails to console, useful for testing"""

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> None:
        logger.info(
            f"""
        -------- Email Message --------
        To: {to_email}
        Subject: {subject}
        Body:
        {body}
        -----------------------------
        """
        )

    async def send_verification_email(
        self, to_email: str, verification_code: str
    ) -> None:
        logger.info(
            f"""
        -------- Email Message --------
        To: {to_email}
        Subject: Please verify your email address
        Body:
        Verification code: {verification_code}
        -----------------------------
        """
        )

    async def send_password_reset_email(
        self, to_email: str, reset_token: str
    ) -> None:
        logger.info(
            f"""
        -------- Email Message --------
        To: {to_email}
        Subject: Password Reset Request
        Body:
        Reset token: {reset_token}
        -----------------------------
        """
        )
