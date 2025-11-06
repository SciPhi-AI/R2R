from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from pydantic import Field

from .base import Provider, ProviderConfig


class AnonymizationStrategy(str, Enum):
    """Anonymization strategies for PII."""

    MASK = "mask"  # Replace with ***
    HASH = "hash"  # Deterministic hashing (same PII → same hash)
    REPLACE = "replace"  # Replace with fake data (via Faker)
    REDACT = "redact"  # Complete removal


@dataclass
class PIIEntity:
    """Represents a detected PII entity."""

    entity_type: str  # e.g., "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"
    start: int  # Start position in text
    end: int  # End position in text
    score: float  # Confidence score (0.0 - 1.0)
    text: str  # Original text


@dataclass
class AnonymizationResult:
    """Result of anonymizing text."""

    anonymized_text: str  # Text with PII replaced
    entities: list[PIIEntity]  # Detected entities
    anonymization_applied: bool  # Whether any anonymization was performed
    mappings: dict[str, str] = None  # Optional: original hash -> anonymized value

    def __post_init__(self):
        if self.mappings is None:
            self.mappings = {}


class PIIDetectionConfig(ProviderConfig):
    """Configuration for PII detection provider."""

    provider: Optional[str] = None
    enabled: bool = False  # Disabled by default (opt-in)
    anonymization_strategy: AnonymizationStrategy = AnonymizationStrategy.HASH
    supported_entities: list[str] = Field(
        default_factory=lambda: [
            "PERSON",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "CREDIT_CARD",
            "US_SSN",
            "IBAN_CODE",
            "IP_ADDRESS",
            "LOCATION",
            "DATE_TIME",
        ]
    )
    language: str = "en"
    score_threshold: float = 0.5  # Minimum confidence score to consider
    store_mappings: bool = True  # Store PII mappings for re-identification
    custom_models: list[str] = Field(default_factory=list)

    @property
    def supported_providers(self) -> list[str]:
        return ["presidio"]

    def validate_config(self) -> None:
        if self.provider and self.provider not in self.supported_providers:
            raise ValueError(
                f"Unsupported PII detection provider: {self.provider}"
            )
        if not 0.0 <= self.score_threshold <= 1.0:
            raise ValueError("score_threshold must be between 0.0 and 1.0")
        if not self.language:
            raise ValueError("language must be specified")


class PIIDetectionProvider(Provider, ABC):
    """Abstract base class for PII detection providers."""

    def __init__(self, config: PIIDetectionConfig):
        if not isinstance(config, PIIDetectionConfig):
            raise ValueError(
                "PIIDetectionProvider must be initialized with a PIIDetectionConfig"
            )
        super().__init__(config)
        self.config: PIIDetectionConfig = config

    @abstractmethod
    async def detect_pii(self, text: str) -> list[PIIEntity]:
        """
        Detect PII entities in the given text.

        Args:
            text: The text to analyze for PII

        Returns:
            List of detected PII entities
        """
        pass

    @abstractmethod
    async def anonymize_text(
        self,
        text: str,
        strategy: Optional[AnonymizationStrategy] = None,
    ) -> AnonymizationResult:
        """
        Anonymize PII in the given text.

        Args:
            text: The text to anonymize
            strategy: Anonymization strategy to use (defaults to config strategy)

        Returns:
            AnonymizationResult containing anonymized text and metadata
        """
        pass

    @abstractmethod
    async def analyze_batch(
        self, texts: list[str]
    ) -> list[AnonymizationResult]:
        """
        Analyze and anonymize multiple texts in batch.

        Args:
            texts: List of texts to analyze

        Returns:
            List of AnonymizationResult for each text
        """
        pass
