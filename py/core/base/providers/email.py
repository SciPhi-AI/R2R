# email_provider.py
import logging
from abc import ABC, abstractmethod
from typing import Optional

from .base import Provider, ProviderConfig


class EmailConfig(ProviderConfig):
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: Optional[str] = None
    use_tls: bool = True

    @property
    def supported_providers(self) -> list[str]:
        return [
            "smtp",
            "console",
        ]  # Could add more providers like AWS SES, SendGrid etc.

    def validate_config(self) -> None:
        if self.provider == "smtp":
            if not all(
                [
                    self.smtp_server,
                    self.smtp_port,
                    self.smtp_username,
                    self.smtp_password,
                    self.from_email,
                ]
            ):
                raise ValueError("SMTP configuration is incomplete")


logger = logging.getLogger(__name__)


class EmailProvider(Provider, ABC):
    def __init__(self, config: EmailConfig):
        if not isinstance(config, EmailConfig):
            raise ValueError(
                "EmailProvider must be initialized with an EmailConfig"
            )
        super().__init__(config)
        self.config: EmailConfig = config  # for type hinting

    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> None:
        pass

    @abstractmethod
    async def send_verification_email(
        self, to_email: str, verification_code: str
    ) -> None:
        pass

    @abstractmethod
    async def send_password_reset_email(
        self, to_email: str, reset_token: str
    ) -> None:
        pass
