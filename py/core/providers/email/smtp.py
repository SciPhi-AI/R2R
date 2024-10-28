import logging
import os
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from aiosmtplib import SMTP

from core.base import EmailConfig, EmailProvider

logger = logging.getLogger()


class AsyncSMTPEmailProvider(EmailProvider):
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

        self.from_email: Optional[str] = config.from_email or os.getenv(
            "R2R_FROM_EMAIL"
        )
        if not self.from_email:
            raise ValueError("From email is required")

        self.use_tls = (
            config.use_tls
            or os.getenv("R2R_SMTP_USE_TLS", "true").lower() == "true"
        )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject  # type: ignore
        msg["From"] = self.from_email  # type: ignore
        msg["To"] = to_email

        msg.attach(MIMEText(body, "plain"))
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        try:
            smtp = SMTP(
                hostname=self.smtp_server,
                port=int(self.smtp_port) if self.smtp_port else None,
                use_tls=self.use_tls,
            )

            await smtp.connect()
            if self.smtp_username and self.smtp_password:
                await smtp.login(self.smtp_username, self.smtp_password)

            await smtp.send_message(msg)
            await smtp.quit()

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            raise

    async def send_verification_email(
        self, to_email: str, verification_code: str
    ) -> None:
        subject = "Verify Your Email Address"
        body = f"""
        Thank you for registering! Please verify your email address by entering the following code:

        {verification_code}

        This code will expire in 24 hours.
        """
        html_body = f"""
        <h2>Email Verification</h2>
        <p>Thank you for registering! Please verify your email address by entering the following code:</p>
        <h3>{verification_code}</h3>
        <p>This code will expire in 24 hours.</p>
        """
        await self.send_email(to_email, subject, body, html_body)

    async def send_password_reset_email(
        self, to_email: str, reset_token: str
    ) -> None:
        subject = "Password Reset Request"
        body = f"""
        We received a request to reset your password. Use the following code to reset your password:

        {reset_token}

        This code will expire in 1 hour. If you didn't request this reset, please ignore this email.
        """
        html_body = f"""
        <h2>Password Reset Request</h2>
        <p>We received a request to reset your password. Use the following code to reset your password:</p>
        <h3>{reset_token}</h3>
        <p>This code will expire in 1 hour.</p>
        <p>If you didn't request this reset, please ignore this email.</p>
        """
        await self.send_email(to_email, subject, body, html_body)
