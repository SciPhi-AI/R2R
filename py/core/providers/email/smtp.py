import asyncio
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from core.base import EmailConfig, EmailProvider

logger = logging.getLogger(__name__)


class AsyncSMTPEmailProvider(EmailProvider):
    """Email provider implementation using Brevo SMTP relay."""

    def __init__(self, config: EmailConfig):
        super().__init__(config)
        self.smtp_server = config.smtp_server or os.getenv("R2R_SMTP_SERVER")
        if not self.smtp_server:
            raise ValueError("SMTP server is required")

        self.smtp_port = config.smtp_port or os.getenv("R2R_SMTP_PORT")
        if not self.smtp_port:
            raise ValueError("SMTP port is required")

        self.smtp_username = config.smtp_username or os.getenv(
            "R2R_SMTP_USERNAME"
        )
        if not self.smtp_username:
            raise ValueError("SMTP username is required")

        self.smtp_password = config.smtp_password or os.getenv(
            "R2R_SMTP_PASSWORD"
        )
        if not self.smtp_password:
            raise ValueError("SMTP password is required")

        self.from_email: Optional[str] = (
            config.from_email
            or os.getenv("R2R_FROM_EMAIL")
            or self.smtp_username
        )
        self.ssl_context = ssl.create_default_context()

    async def _send_email_sync(self, msg: MIMEMultipart) -> None:
        """Synchronous email sending wrapped in asyncio executor."""
        loop = asyncio.get_running_loop()

        def _send():
            with smtplib.SMTP_SSL(
                self.smtp_server,
                self.smtp_port,
                context=self.ssl_context,
                timeout=30,
            ) as server:
                logger.info("Connected to SMTP server")
                server.login(self.smtp_username, self.smtp_password)
                logger.info("Login successful")
                server.send_message(msg)
                logger.info("Message sent successfully!")

        try:
            await loop.run_in_executor(None, _send)
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        *args,
        **kwargs,
    ) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email  # type: ignore
        msg["To"] = to_email

        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        try:
            logger.info("Initializing SMTP connection...")
            async with asyncio.timeout(30):  # Overall timeout
                await self._send_email_sync(msg)
        except asyncio.TimeoutError as e:
            error_msg = "Operation timed out while trying to send email"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    async def send_verification_email(
        self, to_email: str, verification_code: str, *args, **kwargs
    ) -> None:
        body = f"""
        Please verify your email address by entering the following code:

        Verification code: {verification_code}

        If you did not request this verification, please ignore this email.
        """

        html_body = f"""
        <p>Please verify your email address by entering the following code:</p>
        <p style="font-size: 24px; font-weight: bold; margin: 20px 0;">
            Verification code: {verification_code}
        </p>
        <p>If you did not request this verification, please ignore this email.</p>
        """

        await self.send_email(
            to_email=to_email,
            subject="Please verify your email address",
            body=body,
            html_body=html_body,
        )

    async def send_password_reset_email(
        self, to_email: str, reset_token: str, *args, **kwargs
    ) -> None:
        body = f"""
        You have requested to reset your password.

        Reset token: {reset_token}

        If you did not request a password reset, please ignore this email.
        """

        html_body = f"""
        <p>You have requested to reset your password.</p>
        <p style="font-size: 24px; font-weight: bold; margin: 20px 0;">
            Reset token: {reset_token}
        </p>
        <p>If you did not request a password reset, please ignore this email.</p>
        """

        await self.send_email(
            to_email=to_email,
            subject="Password Reset Request",
            body=body,
            html_body=html_body,
        )

    async def send_password_changed_email(
        self, to_email: str, *args, **kwargs
    ) -> None:
        body = """
        Your password has been successfully changed.

        If you did not make this change, please contact support immediately and secure your account.

        """

        html_body = """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1>Password Changed Successfully</h1>
            <p>Your password has been successfully changed.</p>
        </div>
        """

        await self.send_email(
            to_email=to_email,
            subject="Your Password Has Been Changed",
            body=body,
            html_body=html_body,
        )
