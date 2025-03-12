import asyncio
import os
import sys
from dotenv import load_dotenv
import logging

# Add the project root to the Python path
sys.path.append(".")

from core.base import EmailConfig, AppConfig
from core.providers.email import MailerSendEmailProvider
from mailersend import emails

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_mailersend_direct():
    """Test MailerSend directly without the provider abstraction to diagnose issues."""
    api_key = os.getenv("MAILERSEND_API_KEY")
    from_email = os.getenv("R2R_FROM_EMAIL")
    test_email = os.getenv("TEST_EMAIL", "test@example.com")
    
    mailer = emails.NewEmail(api_key)
    
    mail_body = {
        "from": {
            "email": from_email,
            "name": "R2R Test",
        },
        "to": [{"email": test_email}],
        "subject": "Direct Test Email",
        "text": "This is a direct test email.",
        "html": "<h1>Direct Test</h1><p>This is a direct test email.</p>"
    }
    
    print(f"Sending direct test email to {test_email}...")
    response = mailer.send(mail_body)
    print(f"Direct MailerSend response: {response}, type: {type(response)}")
    print("Direct email test complete!")

    
    
async def test_mailersend():
    """Test the MailerSend provider implementation."""
    # Create email config
    config = EmailConfig(
        app=AppConfig(name="your_app_name"),
        provider="mailersend",
        mailersend_api_key=os.getenv("MAILERSEND_API_KEY"),
        verify_email_template_id=os.getenv("MAILERSEND_VERIFY_EMAIL_TEMPLATE_ID"),
        reset_password_template_id=os.getenv("MAILERSEND_RESET_PASSWORD_TEMPLATE_ID"),
        password_changed_template_id=os.getenv("MAILERSEND_PASSWORD_CHANGED_TEMPLATE_ID"),
        from_email=os.getenv("R2R_FROM_EMAIL"),
        frontend_url=os.getenv("R2R_FRONTEND_URL", "https://example.com"),
        sender_name="R2R Test"
    )
    print(config)
    
    # Create MailerSend provider
    provider = MailerSendEmailProvider(config)
    
    # Test email address (replace with your own)
    test_email = os.getenv("TEST_EMAIL", "test@example.com")
    
    # Test sending a simple email
    print(f"Sending test email to {test_email}...")
    try:
        await provider.send_email(
            to_email=test_email,
            subject="Test Email from MailerSend Provider",
            body="This is a test email from the MailerSend provider.",
            html_body="<h1>Test Email</h1><p>This is a test email from the <strong>MailerSend</strong> provider.</p>"
        )
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")
    
    
async def test_verify_email():
    config = EmailConfig(
        app=AppConfig(name="your_app_name"),
        provider="mailersend",
        mailersend_api_key=os.getenv("MAILERSEND_API_KEY"),
        verify_email_template_id=os.getenv("MAILERSEND_VERIFY_EMAIL_TEMPLATE_ID"),
        reset_password_template_id=os.getenv("MAILERSEND_RESET_PASSWORD_TEMPLATE_ID"),
        password_changed_template_id=os.getenv("MAILERSEND_PASSWORD_CHANGED_TEMPLATE_ID"),
        from_email=os.getenv("R2R_FROM_EMAIL"),
        frontend_url=os.getenv("R2R_FRONTEND_URL", "https://example.com"),
        sender_name="R2R Test"
    )
    provider = MailerSendEmailProvider(config)
    # Test email address (replace with your own)
    test_email = os.getenv("TEST_EMAIL", "test@example.com")
    print("template id: "+config.verify_email_template_id)
    
    try:
        await provider.send_verification_email(
            to_email=test_email,
            verification_code="123456",
            dynamic_template_data={"firstname": "John"}
        )
        print("Verification email sent successfully!")
    except Exception as e:
        print(f"Error sending verification email: {e}")
    
if __name__ == "__main__":
    # First test direct mailersend usage
    # asyncio.run(test_mailersend_direct())
    
    # Then test our provider implementation
    # asyncio.run(test_mailersend()) 
    asyncio.run(test_verify_email())