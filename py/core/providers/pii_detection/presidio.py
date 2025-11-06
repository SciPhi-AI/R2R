import hashlib
import logging
from typing import Optional

from core.base import (
    AnonymizationResult,
    AnonymizationStrategy,
    PIIDetectionConfig,
    PIIDetectionProvider,
    PIIEntity,
)

logger = logging.getLogger(__name__)


class PresidioPIIDetectionConfig(PIIDetectionConfig):
    """Configuration for Presidio PII detection provider."""

    provider: str = "presidio"
    analyzer_model: Optional[str] = None  # Custom NLP model path
    use_faker: bool = True  # Use Faker for replace strategy

    @property
    def supported_providers(self) -> list[str]:
        return ["presidio"]

    def validate_config(self) -> None:
        super().validate_config()
        if self.provider not in self.supported_providers:
            raise ValueError(
                f"Unsupported PII detection provider: {self.provider}"
            )


class PresidioPIIDetectionProvider(PIIDetectionProvider):
    """Presidio-based PII detection and anonymization provider."""

    def __init__(self, config: PresidioPIIDetectionConfig):
        if not isinstance(config, PresidioPIIDetectionConfig):
            raise ValueError(
                "PresidioPIIDetectionProvider must be initialized with a PresidioPIIDetectionConfig"
            )
        super().__init__(config)
        self.config: PresidioPIIDetectionConfig = config

        logger.info("Initializing PresidioPIIDetectionProvider")

        # Lazy import to avoid dependency issues if not installed
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            from presidio_anonymizer.entities import OperatorConfig

            self.AnalyzerEngine = AnalyzerEngine
            self.AnonymizerEngine = AnonymizerEngine
            self.OperatorConfig = OperatorConfig
        except ImportError as e:
            raise ImportError(
                "Presidio libraries not installed. Install with: "
                "pip install presidio-analyzer presidio-anonymizer spacy"
            ) from e

        # Initialize Presidio engines
        self._analyzer = None
        self._anonymizer = None
        self._faker = None

        # Initialize on first use (lazy loading)
        self._ensure_initialized()

    def _ensure_initialized(self):
        """Ensure Presidio engines are initialized."""
        if self._analyzer is None:
            logger.info("Initializing Presidio AnalyzerEngine...")
            self._analyzer = self.AnalyzerEngine()
            logger.info("Presidio AnalyzerEngine initialized")

        if self._anonymizer is None:
            logger.info("Initializing Presidio AnonymizerEngine...")
            self._anonymizer = self.AnonymizerEngine()
            logger.info("Presidio AnonymizerEngine initialized")

        if self._faker is None and self.config.use_faker:
            try:
                from faker import Faker

                self._faker = Faker(self.config.language)
                logger.info("Faker initialized for replace strategy")
            except ImportError:
                logger.warning(
                    "Faker not installed. Replace strategy will fall back to redaction."
                )
                self._faker = None

    def _convert_to_pii_entity(self, result) -> PIIEntity:
        """Convert Presidio RecognizerResult to PIIEntity."""
        return PIIEntity(
            entity_type=result.entity_type,
            start=result.start,
            end=result.end,
            score=result.score,
            text="",  # Will be filled in by caller
        )

    async def detect_pii(self, text: str) -> list[PIIEntity]:
        """
        Detect PII entities in the given text using Presidio.

        Args:
            text: The text to analyze for PII

        Returns:
            List of detected PII entities
        """
        self._ensure_initialized()

        if not text or not text.strip():
            return []

        # Analyze text with Presidio
        results = self._analyzer.analyze(
            text=text,
            language=self.config.language,
            entities=self.config.supported_entities or None,
            score_threshold=self.config.score_threshold,
        )

        # Convert to PIIEntity objects
        pii_entities = []
        for result in results:
            entity = self._convert_to_pii_entity(result)
            entity.text = text[result.start : result.end]
            pii_entities.append(entity)

        logger.debug(f"Detected {len(pii_entities)} PII entities in text")
        return pii_entities

    def _get_anonymization_operator(
        self, strategy: AnonymizationStrategy
    ) -> dict:
        """Get Presidio operator configuration for the given strategy."""
        from presidio_anonymizer.entities import OperatorConfig

        if strategy == AnonymizationStrategy.MASK:
            return {"DEFAULT": OperatorConfig("mask", {"chars_to_mask": 100, "masking_char": "*", "from_end": False})}
        elif strategy == AnonymizationStrategy.REDACT:
            return {"DEFAULT": OperatorConfig("redact", {})}
        elif strategy == AnonymizationStrategy.HASH:
            return {"DEFAULT": OperatorConfig("hash", {"hash_type": "sha256"})}
        elif strategy == AnonymizationStrategy.REPLACE:
            # Use entity-specific replacement strategies
            operators = {}
            replacement_map = {
                "PERSON": "replace",
                "EMAIL_ADDRESS": "replace",
                "PHONE_NUMBER": "replace",
                "LOCATION": "replace",
                "DATE_TIME": "replace",
            }
            for entity_type in self.config.supported_entities:
                if entity_type in replacement_map:
                    operators[entity_type] = OperatorConfig("replace", {})
                else:
                    # Fall back to redaction for entities without good replacements
                    operators[entity_type] = OperatorConfig("redact", {})
            return operators
        else:
            # Default to redaction
            return {"DEFAULT": OperatorConfig("redact", {})}

    def _generate_deterministic_hash(self, text: str) -> str:
        """Generate a deterministic hash for PII text."""
        # Use SHA256 for deterministic hashing
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    async def anonymize_text(
        self,
        text: str,
        strategy: Optional[AnonymizationStrategy] = None,
    ) -> AnonymizationResult:
        """
        Anonymize PII in the given text using Presidio.

        Args:
            text: The text to anonymize
            strategy: Anonymization strategy to use (defaults to config strategy)

        Returns:
            AnonymizationResult containing anonymized text and metadata
        """
        self._ensure_initialized()

        if not text or not text.strip():
            return AnonymizationResult(
                anonymized_text=text,
                entities=[],
                anonymization_applied=False,
                mappings={},
            )

        # Use provided strategy or fall back to config
        strategy = strategy or self.config.anonymization_strategy

        # First, detect PII entities
        entities = await self.detect_pii(text)

        if not entities:
            return AnonymizationResult(
                anonymized_text=text,
                entities=[],
                anonymization_applied=False,
                mappings={},
            )

        # Prepare analyzer results for anonymizer
        from presidio_analyzer import RecognizerResult

        analyzer_results = [
            RecognizerResult(
                entity_type=entity.entity_type,
                start=entity.start,
                end=entity.end,
                score=entity.score,
            )
            for entity in entities
        ]

        # Get operator configuration
        operators = self._get_anonymization_operator(strategy)

        # Anonymize using Presidio
        anonymized_result = self._anonymizer.anonymize(
            text=text, analyzer_results=analyzer_results, operators=operators
        )

        # Build mappings for hash strategy
        mappings = {}
        if self.config.store_mappings and strategy == AnonymizationStrategy.HASH:
            for entity in entities:
                original_hash = self._generate_deterministic_hash(entity.text)
                mappings[original_hash] = entity.text

        return AnonymizationResult(
            anonymized_text=anonymized_result.text,
            entities=entities,
            anonymization_applied=True,
            mappings=mappings,
        )

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
        results = []
        for text in texts:
            result = await self.anonymize_text(text)
            results.append(result)
        return results
