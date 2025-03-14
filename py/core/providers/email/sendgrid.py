import logging
import os
from typing import Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, From, Mail

from core.base import EmailConfig, EmailProvider

logger = logging.getLogger(__name__)


class SendGridEmailProvider(EmailProvider):
    """Email provider implementation using SendGrid API."""

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

        self.verify_email_template_id = (
            config.verify_email_template_id
            or os.getenv("SENDGRID_EMAIL_TEMPLATE_ID")
        )
        self.reset_password_template_id = (
            config.reset_password_template_id
            or os.getenv("SENDGRID_RESET_TEMPLATE_ID")
        )
        self.password_changed_template_id = (
            config.password_changed_template_id
            or os.getenv("SENDGRID_PASSWORD_CHANGED_TEMPLATE_ID")
        )
        self.client = SendGridAPIClient(api_key=self.api_key)
        self.sender_name = config.sender_name

        # Logo and documentation URLs
        self.docs_base_url = f"{self.frontend_url}/documentation"

    def _get_base_template_data(self, to_email: str) -> dict:
        """Get base template data used across all email templates."""
        return {
            "user_email": to_email,
            "docs_url": self.docs_base_url,
            "quickstart_url": f"{self.docs_base_url}/quickstart",
            "frontend_url": self.frontend_url,
        }

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
                base_data = self._get_base_template_data(to_email)
                message.dynamic_template_data = {
                    **base_data,
                    **(dynamic_template_data or {}),
                }
            else:
                if not subject:
                    raise ValueError(
                        "Subject is required when not using a template"
                    )
                message.subject = subject
                message.add_content(Content("text/plain", body or ""))
                if html_body:
                    message.add_content(Content("text/html", html_body))

            import asyncio

            response = await asyncio.to_thread(self.client.send, message)

            if response.status_code >= 400:
                raise RuntimeError(
                    f"Failed to send email: {response.status_code}"
                )
            elif response.status_code == 202:
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
                verification_data = {
                    "verification_link": f"{self.frontend_url}/verify-email?verification_code={verification_code}&email={to_email}",
                    "verification_code": verification_code,  # Include code separately for flexible template usage
                }

                # Merge with any additional template data
                template_data = {
                    **(dynamic_template_data or {}),
                    **verification_data,
                }

                await self.send_email(
                    to_email=to_email,
                    template_id=self.verify_email_template_id,
                    dynamic_template_data=template_data,
                )
            else:
                # Fallback to basic email if no template ID is configured
                subject = "Verify Your R2R Account"
                html_body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1>Welcome to R2R!</h1>
                    <p>Please verify your email address to get started with R2R - the most advanced AI retrieval system.</p>
                    <p>Click the link below to verify your email:</p>
                    <p><a href="{self.frontend_url}/verify-email?token={verification_code}&email={to_email}"
                          style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                        Verify Email
                    </a></p>
                    <p>Or enter this verification code: <strong>{verification_code}</strong></p>
                    <p>If you didn't create an account with R2R, please ignore this email.</p>
                </div>
                """

                await self.send_email(
                    to_email=to_email,
                    subject=subject,
                    html_body=html_body,
                    body=f"Welcome to R2R! Please verify your email using this code: {verification_code}",
                )
        except Exception as e:
            error_msg = (
                f"Failed to send verification email to {to_email}: {str(e)}"
            )
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
                reset_data = {
                    "reset_link": f"{self.frontend_url}/reset-password?token={reset_token}",
                    "reset_token": reset_token,
                }

                template_data = {**(dynamic_template_data or {}), **reset_data}

                await self.send_email(
                    to_email=to_email,
                    template_id=self.reset_password_template_id,
                    dynamic_template_data=template_data,
                )
            else:
                subject = "Reset Your R2R Password"
                html_body = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1>Password Reset Request</h1>
                    <p>You've requested to reset your R2R password.</p>
                    <p>Click the link below to reset your password:</p>
                    <p><a href="{self.frontend_url}/reset-password?token={reset_token}"
                          style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                        Reset Password
                    </a></p>
                    <p>Or use this reset token: <strong>{reset_token}</strong></p>
                    <p>If you didn't request a password reset, please ignore this email.</p>
                </div>
                """

                await self.send_email(
                    to_email=to_email,
                    subject=subject,
                    html_body=html_body,
                    body=f"Reset your R2R password using this token: {reset_token}",
                )
        except Exception as e:
            error_msg = (
                f"Failed to send password reset email to {to_email}: {str(e)}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    async def send_password_changed_email(
        self,
        to_email: str,
        dynamic_template_data: Optional[dict] = None,
        *args,
        **kwargs,
    ) -> None:
        try:
            if (
                hasattr(self, "password_changed_template_id")
                and self.password_changed_template_id
            ):
                await self.send_email(
                    to_email=to_email,
                    template_id=self.password_changed_template_id,
                    dynamic_template_data=dynamic_template_data,
                )
            else:
                subject = "Your Password Has Been Changed"
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
                # Move send_email inside the else block
                await self.send_email(
                    to_email=to_email,
                    subject=subject,
                    html_body=html_body,
                    body=body,
                )
        except Exception as e:
            error_msg = f"Failed to send password change notification to {to_email}: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
