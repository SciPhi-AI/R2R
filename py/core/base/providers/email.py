import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

from .base import Provider, ProviderConfig


class EmailConfig(ProviderConfig):
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: Optional[str] = None
    use_tls: Optional[bool] = True
    sendgrid_api_key: Optional[str] = None
    mailersend_api_key: Optional[str] = None
    verify_email_template_id: Optional[str] = None
    reset_password_template_id: Optional[str] = None
    password_changed_template_id: Optional[str] = None
    frontend_url: Optional[str] = None
    sender_name: Optional[str] = None

    @property
    def supported_providers(self) -> list[str]:
        return [
            "smtp",
            "console",
            "sendgrid",
            "mailersend",
        ]  # Could add more providers like AWS SES, SendGrid etc.

    def validate_config(self) -> None:
        if (
            self.provider == "sendgrid"
            and not self.sendgrid_api_key
            and not os.getenv("SENDGRID_API_KEY")
        ):
            raise ValueError(
                "SendGrid API key is required when using SendGrid provider"
            )

        if (
            self.provider == "mailersend"
            and not self.mailersend_api_key
            and not os.getenv("MAILERSEND_API_KEY")
        ):
            raise ValueError(
                "MailerSend API key is required when using MailerSend provider"
            )


logger = logging.getLogger(__name__)


class EmailProvider(Provider, ABC):
    def __init__(self, config: EmailConfig):
        if not isinstance(config, EmailConfig):
            raise ValueError(
                "EmailProvider must be initialized with an EmailConfig"
            )
        super().__init__(config)
        self.config: EmailConfig = config

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        *args,
        **kwargs,
    ) -> None:
        pass

    @abstractmethod
    async def send_verification_email(
        self, to_email: str, verification_code: str, *args, **kwargs
    ) -> None:
        pass

    @abstractmethod
    async def send_password_reset_email(
        self, to_email: str, reset_token: str, *args, **kwargs
    ) -> None:
        pass

    @abstractmethod
    async def send_password_changed_email(
        self,
        to_email: str,
        *args,
        **kwargs,
    ) -> None:
        pass
