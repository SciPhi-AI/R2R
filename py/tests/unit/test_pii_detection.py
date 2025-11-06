"""Unit tests for PII detection provider."""
import pytest

from core.base import (
    AnonymizationStrategy,
    PIIDetectionConfig,
)
from core.providers import (
    PresidioPIIDetectionConfig,
    PresidioPIIDetectionProvider,
)


@pytest.fixture
def pii_config():
    """Create a test PII detection configuration."""
    return PresidioPIIDetectionConfig(
        provider="presidio",
        enabled=True,
        anonymization_strategy=AnonymizationStrategy.HASH,
        language="en",
        score_threshold=0.5,
    )


@pytest.fixture
def pii_provider(pii_config):
    """Create a test PII detection provider."""
    return PresidioPIIDetectionProvider(pii_config)


class TestPIIDetectionConfig:
    """Test PII detection configuration."""

    def test_config_creation(self):
        """Test creating a PII detection config."""
        config = PresidioPIIDetectionConfig(
            provider="presidio",
            enabled=True,
            anonymization_strategy=AnonymizationStrategy.MASK,
        )
        assert config.provider == "presidio"
        assert config.enabled is True
        assert config.anonymization_strategy == AnonymizationStrategy.MASK

    def test_config_validation(self):
        """Test config validation."""
        config = PresidioPIIDetectionConfig(provider="presidio")
        config.validate_config()  # Should not raise

        # Test invalid provider
        config.provider = "invalid"
        with pytest.raises(ValueError, match="Unsupported PII detection provider"):
            config.validate_config()

    def test_default_entities(self):
        """Test default supported entities."""
        config = PresidioPIIDetectionConfig(provider="presidio")
        assert "PERSON" in config.supported_entities
        assert "EMAIL_ADDRESS" in config.supported_entities
        assert "PHONE_NUMBER" in config.supported_entities


class TestPresidioPIIDetectionProvider:
    """Test Presidio PII detection provider."""

    @pytest.mark.asyncio
    async def test_detect_pii_with_email(self, pii_provider):
        """Test detecting email addresses."""
        text = "Contact me at john.doe@example.com for more information."
        entities = await pii_provider.detect_pii(text)

        # Should detect at least the email
        assert len(entities) > 0
        assert any(entity.entity_type == "EMAIL_ADDRESS" for entity in entities)

    @pytest.mark.asyncio
    async def test_detect_pii_with_person(self, pii_provider):
        """Test detecting person names."""
        text = "John Smith is a software engineer."
        entities = await pii_provider.detect_pii(text)

        # Should detect the person name
        assert len(entities) > 0
        assert any(entity.entity_type == "PERSON" for entity in entities)

    @pytest.mark.asyncio
    async def test_anonymize_text_hash(self, pii_provider):
        """Test anonymizing text with hash strategy."""
        text = "Contact John Smith at john.smith@example.com"
        result = await pii_provider.anonymize_text(text)

        # Should have anonymized text
        assert result.anonymized_text != text
        assert result.anonymization_applied is True
        assert len(result.entities) > 0

    @pytest.mark.asyncio
    async def test_anonymize_text_mask(self):
        """Test anonymizing text with mask strategy."""
        config = PresidioPIIDetectionConfig(
            provider="presidio",
            enabled=True,
            anonymization_strategy=AnonymizationStrategy.MASK,
        )
        provider = PresidioPIIDetectionProvider(config)

        text = "Contact me at john@example.com"
        result = await provider.anonymize_text(text)

        # Should contain masked characters
        assert "*" in result.anonymized_text
        assert result.anonymization_applied is True

    @pytest.mark.asyncio
    async def test_anonymize_empty_text(self, pii_provider):
        """Test anonymizing empty text."""
        result = await pii_provider.anonymize_text("")

        assert result.anonymized_text == ""
        assert result.anonymization_applied is False
        assert len(result.entities) == 0

    @pytest.mark.asyncio
    async def test_anonymize_text_no_pii(self, pii_provider):
        """Test anonymizing text with no PII."""
        text = "This is a simple sentence without any personal information."
        result = await pii_provider.anonymize_text(text)

        # Should return original text
        assert result.anonymized_text == text
        assert result.anonymization_applied is False
        assert len(result.entities) == 0

    @pytest.mark.asyncio
    async def test_analyze_batch(self, pii_provider):
        """Test analyzing multiple texts in batch."""
        texts = [
            "Contact me at john@example.com",
            "Call Jane Doe at 555-1234",
            "No PII here",
        ]
        results = await pii_provider.analyze_batch(texts)

        assert len(results) == 3
        assert results[0].anonymization_applied is True
        assert results[1].anonymization_applied is True
        assert results[2].anonymization_applied is False
