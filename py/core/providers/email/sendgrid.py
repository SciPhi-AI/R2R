import logging
import os
from typing import Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, From, Mail

from core.base import EmailConfig, EmailProvider

logger = logging.getLogger(__name__)


class SendGridEmailProvider(EmailProvider):
    """Email provider implementation using SendGrid API"""

    def __init__(self, config: EmailConfig):
        super().__init__(config)
        self.api_key = config.sendgrid_api_key or os.getenv("SENDGRID_API_KEY")
        if not self.api_key or not isinstance(self.api_key, str):
            raise ValueError("A valid SendGrid API key is required.")

        self.from_email = config.from_email or os.getenv("R2R_FROM_EMAIL")
        if not self.from_email or not isinstance(self.from_email, str):
            raise ValueError("A valid from email is required.")
        self.frontend_url = config.frontend_url or os.getenv(
            "R2R_FRONTEND_URL"
        )
        if not self.frontend_url or not isinstance(self.frontend_url, str):
            raise ValueError("A valid frontend URL is required.")
        self.verify_email_template_id = config.verify_email_template_id
        self.reset_password_template_id = config.reset_password_template_id
        self.client = SendGridAPIClient(api_key=self.api_key)
        self.sender_name = config.sender_name

    async def send_email(
        self,
        to_email: str,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        html_body: Optional[str] = None,
        template_id: Optional[str] = None,
        dynamic_template_data: Optional[dict] = None,
    ) -> None:
        try:
            logger.info("Preparing SendGrid message...")
            message = Mail(
                from_email=From(self.from_email, self.sender_name),
                to_emails=to_email,
            )

            if template_id:
                logger.info(f"Using dynamic template with ID: {template_id}")
                message.template_id = template_id
                message.dynamic_template_data = dynamic_template_data or {}
            else:
                if not subject:
                    raise ValueError(
                        "Subject is required when not using a template"
                    )
                message.subject = subject

                # Add plain text content
                message.add_content(Content("text/plain", body or ""))

                # Add HTML content if provided
                if html_body:
                    message.add_content(Content("text/html", html_body))

            # Send email
            import asyncio

            response = await asyncio.to_thread(self.client.send, message)

            if response.status_code >= 400:
                raise RuntimeError(
                    f"Failed to send email: {response.status_code}"
                )

            if response.status_code == 202:
                logger.info("Message sent successfully!")
            else:
                error_msg = f"Failed to send email. Status code: {response.status_code}, Body: {response.body}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    async def send_verification_email(
        self,
        to_email: str,
        verification_code: str,
        dynamic_template_data: Optional[dict] = None,
    ) -> None:
        try:
            if self.verify_email_template_id:
                # Use dynamic template
                dynamic_data = {
                    "url": f"{self.frontend_url}/verify-email?token={verification_code}&email={to_email}",
                }

                if dynamic_template_data:
                    dynamic_data |= dynamic_template_data

                await self.send_email(
                    to_email=to_email,
                    template_id=self.verify_email_template_id,
                    dynamic_template_data=dynamic_data,
                )
            else:
                # Fallback to default content
                subject = "Please verify your email address"
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
                    subject=subject,
                    body=body,
                    html_body=html_body,
                )
        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    async def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        dynamic_template_data: Optional[dict] = None,
    ) -> None:
        try:
            if self.reset_password_template_id:
                # Use dynamic template
                dynamic_data = {
                    "url": f"{self.frontend_url}/reset-password?token={reset_token}",
                }

                if dynamic_template_data:
                    dynamic_data |= dynamic_template_data

                await self.send_email(
                    to_email=to_email,
                    template_id=self.reset_password_template_id,
                    dynamic_template_data=dynamic_data,
                )
            else:
                # Fallback to default content
                subject = "Password Reset Request"
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
                    subject=subject,
                    body=body,
                    html_body=html_body,
                )
        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
