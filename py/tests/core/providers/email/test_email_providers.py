import pytest

from core.base.providers.email import EmailConfig
from core.providers.email import SendGridEmailProvider


@pytest.fixture(scope="function")
def sendgrid_config(app_config):
    return EmailConfig(
        provider="sendgrid",
        sendgrid_api_key="your_sendgrid_api_key",
        from_email="support@example.com",  # Ensure this email is verified in your SendGrid account
        app=app_config,
    )


@pytest.fixture
def sendgrid_provider(sendgrid_config):
    return SendGridEmailProvider(sendgrid_config)


class TestSendGridEmailProvider:
    @pytest.mark.asyncio
    async def test_send_email_basic(self, sendgrid_provider):
        await sendgrid_provider.send_email(
            to_email="example@example.com",  # Replace with your email address
            subject="Test Email",
            body="This is a test email sent from the test_send_email_basic test case.",
        )
        # If your send_email method returns a response, you can add assertions here

    @pytest.mark.asyncio
    async def test_send_email_with_template(self, sendgrid_provider):
        await sendgrid_provider.send_email(
            to_email="example@example.com",  # Replace with your email address
            template_id="template_id",  # Replace with your SendGrid template ID
            dynamic_template_data={"first_name": "Example"},
        )
        # Add assertions if applicable

    @pytest.mark.asyncio
    async def test_send_verification_email(self, sendgrid_provider):
        await sendgrid_provider.send_verification_email(
            to_email="example@example.com",  # Replace with your email address
            verification_code="123456",
        )
        # Add assertions if applicable

    @pytest.mark.asyncio
    async def test_send_verification_email_with_template(
        self, sendgrid_provider
    ):
        await sendgrid_provider.send_verification_email(
            to_email="example@example.com",  # Replace with your email address
            verification_code="123456",
        )
        # Add assertions if applicable

    @pytest.mark.asyncio
    async def test_send_verification_email_with_template_and_dynamic_data(
        self, sendgrid_provider
    ):
        await sendgrid_provider.send_verification_email(
            to_email="example@example.com",  # Replace with your email address
            verification_code="123456",
            dynamic_template_data={"name": "User"},
            frontend_url="http://localhost:3000/auth",
        )
        # Add assertions if applicable

    @pytest.mark.asyncio
    async def test_send_email_failure(self, sendgrid_provider):
        # Intentionally use an invalid email to simulate a failure
        with pytest.raises(RuntimeError):
            await sendgrid_provider.send_email(
                to_email="invalid-email-address",  # Invalid email address
                subject="Test Email",
                body="This should fail.",
            )
