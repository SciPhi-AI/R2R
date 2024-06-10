from typing import Optional

from .base_provider import ProviderConfig


class EmbeddingConfig(ProviderConfig):
    """A base embedding configuration class"""

    provider: Optional[str] = None
    batch_size: int = 1
