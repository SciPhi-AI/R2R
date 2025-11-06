# PII Detection and Pseudonymization

R2R supports automatic detection and anonymization of Personally Identifiable Information (PII) using Microsoft Presidio during document ingestion.

## Overview

When enabled, PII detection:
- Automatically detects PII in document chunks during ingestion
- Anonymizes detected PII before storing in the database
- Stores metadata about detected PII for audit purposes
- Supports multiple anonymization strategies

## Quick Start

### 1. Install Dependencies

```bash
cd py
pip install -e ".[core]"
```

### 2. Download spaCy Language Model

**REQUIRED:** Presidio uses spaCy for Natural Language Processing. You must download a language model:

```bash
# For English (recommended for production - 560 MB)
python -m spacy download en_core_web_lg

# Alternative: Smaller model for testing (13 MB, lower accuracy)
python -m spacy download en_core_web_sm
```

Verify installation:
```bash
python -c "import spacy; nlp = spacy.load('en_core_web_lg'); print('✓ Model loaded successfully')"
```

### 3. Enable PII Detection

Edit `py/r2r/r2r.toml`:

```toml
[pii_detection]
provider = "presidio"
enabled = true  # Change from false to true
anonymization_strategy = "hash"
```

### 4. Restart R2R

```bash
# Restart your R2R server to apply changes
```

## Configuration

### Anonymization Strategies

Choose from four strategies in `r2r.toml`:

#### 1. Hash (Default)
Deterministic SHA256 hashing - same PII always produces same hash.

```toml
anonymization_strategy = "hash"
```

**Example:**
- Input: `"Contact john.smith@email.com"`
- Output: `"Contact 3f7b8a9c2d1e5f6a"`

**Use case:** When you need consistent anonymization (same email always becomes same hash)

#### 2. Mask
Replace PII with asterisks.

```toml
anonymization_strategy = "mask"
```

**Example:**
- Input: `"Contact john.smith@email.com"`
- Output: `"Contact *******************"`

**Use case:** Visual obfuscation while preserving text structure

#### 3. Replace
Replace with fake but realistic data using Faker.

```toml
anonymization_strategy = "replace"
```

**Example:**
- Input: `"Contact John Smith at john.smith@email.com"`
- Output: `"Contact Jane Doe at jane.doe@example.com"`

**Use case:** Maintaining realistic-looking data for testing/demos

#### 4. Redact
Complete removal of PII.

```toml
anonymization_strategy = "redact"
```

**Example:**
- Input: `"Contact john.smith@email.com for details"`
- Output: `"Contact  for details"`

**Use case:** Maximum privacy, accept text structure changes

### Supported PII Entity Types

Default entity types detected:

```toml
supported_entities = [
    "PERSON",           # Names of people
    "EMAIL_ADDRESS",    # Email addresses
    "PHONE_NUMBER",     # Phone numbers
    "CREDIT_CARD",      # Credit card numbers
    "US_SSN",          # US Social Security Numbers
    "IBAN_CODE",       # International Bank Account Numbers
    "IP_ADDRESS",      # IP addresses
    "LOCATION",        # Geographic locations
    "DATE_TIME",       # Dates and times
]
```

Customize by modifying the list in `r2r.toml`.

### Advanced Configuration

```toml
[pii_detection]
provider = "presidio"
enabled = true
anonymization_strategy = "hash"

# Minimum confidence score (0.0 - 1.0)
# Higher = fewer false positives, may miss some PII
# Lower = catch more PII, more false positives
score_threshold = 0.5

# Language support
language = "en"  # "es" for Spanish, "de" for German, etc.

# Store PII mappings (for hash strategy)
store_mappings = true

# Custom entity types (if needed)
# supported_entities = ["PERSON", "EMAIL_ADDRESS"]
```

## Usage

### Document Ingestion

PII detection runs automatically during ingestion:

```python
# Upload a document with PII
await r2r.ingest_files(
    files=["document_with_pii.pdf"],
    metadata={"source": "customer_data"}
)

# PII is automatically detected and anonymized
# Before: "Contact John Smith at john.smith@email.com"
# After:  "Contact <HASH> at <HASH>"
```

### Check PII Metadata

Retrieved chunks include PII detection metadata:

```python
results = await r2r.search(query="contact information")

for chunk in results:
    if chunk.metadata.get("pii_detected"):
        print(f"PII found in chunk {chunk.id}")
        print(f"Entity types: {chunk.metadata['pii_entity_types']}")
        print(f"Count: {chunk.metadata['pii_entity_count']}")
```

**Example metadata:**
```json
{
  "pii_detected": true,
  "pii_entity_types": ["PERSON", "EMAIL_ADDRESS"],
  "pii_entity_count": 2
}
```

## Troubleshooting

### Error: "Can't find model 'en_core_web_lg'"

**Problem:** spaCy language model not installed.

**Solution:**
```bash
python -m spacy download en_core_web_lg
```

### Error: "No module named 'presidio_analyzer'"

**Problem:** Presidio dependencies not installed.

**Solution:**
```bash
cd py
pip install -e ".[core]"
```

### Error: "Faker not installed"

**Problem:** Faker library missing (only needed for `replace` strategy).

**Solution:**
```bash
pip install faker
```

Or change to a different strategy:
```toml
anonymization_strategy = "hash"  # or "mask" or "redact"
```

### Slow Ingestion Performance

**Problem:** PII detection adds processing time.

**Solutions:**
1. Use smaller spaCy model: `en_core_web_sm` instead of `en_core_web_lg`
2. Increase `score_threshold` to reduce processing
3. Reduce `supported_entities` to only what you need
4. Consider disabling for non-sensitive documents

## Multi-Language Support

For non-English languages, install appropriate spaCy models:

### Spanish
```bash
python -m spacy download es_core_news_lg
```

```toml
language = "es"
```

### German
```bash
python -m spacy download de_core_news_lg
```

```toml
language = "de"
```

### French
```bash
python -m spacy download fr_core_news_lg
```

```toml
language = "fr"
```

See [spaCy models](https://spacy.io/models) for all available languages.

## Performance Considerations

### Model Size vs Accuracy

| Model | Size | Accuracy | Recommendation |
|-------|------|----------|----------------|
| `en_core_web_sm` | 13 MB | Good | Development/testing |
| `en_core_web_md` | 40 MB | Better | Moderate accuracy needs |
| `en_core_web_lg` | 560 MB | Best | Production (recommended) |
| `en_core_web_trf` | 438 MB | Excellent | Maximum accuracy |

### Optimization Tips

1. **Batch processing:** PII detection processes chunks individually. For large documents, ingestion may be slower.

2. **Confidence threshold:** Increase `score_threshold` to reduce false positives:
   ```toml
   score_threshold = 0.7  # Higher = stricter (fewer false positives)
   ```

3. **Entity selection:** Only detect entities you care about:
   ```toml
   supported_entities = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"]
   ```

4. **Selective enabling:** Enable PII detection only for sensitive collections.

## Security Considerations

### What Gets Stored

- **With PII detection enabled:** Anonymized text only
- **Without PII detection:** Original text with PII

### PII Mappings

When `store_mappings = true` (hash strategy only):
- Original PII hashes are stored in memory during processing
- Mappings are NOT persisted to database (future feature)
- No way to reverse the anonymization currently

### Audit Trail

All chunks with detected PII include metadata:
```json
{
  "pii_detected": true,
  "pii_entity_types": ["PERSON", "EMAIL_ADDRESS"],
  "pii_entity_count": 2
}
```

This allows you to:
- Identify which chunks contained PII
- Track what types of PII were found
- Audit PII handling for compliance

## API Reference

### Configuration Schema

```python
class PIIDetectionConfig(ProviderConfig):
    provider: str = "presidio"
    enabled: bool = False
    anonymization_strategy: AnonymizationStrategy = "hash"
    supported_entities: list[str] = [...]
    language: str = "en"
    score_threshold: float = 0.5
    store_mappings: bool = True
    custom_models: list[str] = []
```

### Provider Interface

```python
class PIIDetectionProvider:
    async def detect_pii(text: str) -> list[PIIEntity]
    async def anonymize_text(text: str, strategy: AnonymizationStrategy) -> AnonymizationResult
    async def analyze_batch(texts: list[str]) -> list[AnonymizationResult]
```

## Examples

### Example 1: Enable PII Detection for All Documents

```toml
# r2r.toml
[pii_detection]
enabled = true
anonymization_strategy = "hash"
```

### Example 2: Strict PII Detection

```toml
# r2r.toml
[pii_detection]
enabled = true
anonymization_strategy = "redact"  # Complete removal
score_threshold = 0.8  # High confidence only
supported_entities = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN"]
```

### Example 3: Development/Testing

```toml
# r2r.toml
[pii_detection]
enabled = true
anonymization_strategy = "replace"  # Fake realistic data
score_threshold = 0.5
```

After configuring, download the small model for faster testing:
```bash
python -m spacy download en_core_web_sm
```

## Compliance

PII detection helps with:

- **GDPR:** Minimize PII storage
- **CCPA:** Reduce consumer data retention
- **HIPAA:** Protect health information
- **PCI DSS:** Secure cardholder data

**Note:** This feature helps reduce PII exposure but does not guarantee complete PII removal. Always conduct your own security audits and compliance reviews.

## Limitations

1. **No database persistence:** PII mappings are not stored in database (future feature)
2. **No re-identification:** Cannot reverse anonymization currently
3. **Language-specific:** Accuracy varies by language
4. **False positives/negatives:** No PII detection is 100% accurate
5. **Performance impact:** Adds processing time during ingestion

## Future Enhancements

Planned features:
- Database persistence for PII mappings
- API endpoints to manage PII mappings
- Re-identification for authorized users
- Batch optimization for better performance
- UI for viewing PII detection results
- Real-time PII detection metrics

## Support

For issues or questions:
- GitHub Issues: https://github.com/SciPhi-AI/R2R/issues
- Documentation: https://r2r-docs.sciphi.ai
- Presidio Docs: https://microsoft.github.io/presidio/

## License

This feature uses:
- **Microsoft Presidio:** Apache 2.0 License
- **spaCy:** MIT License
- **Faker:** MIT License
