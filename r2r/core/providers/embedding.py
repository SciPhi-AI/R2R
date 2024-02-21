from abc import ABC, abstractmethod
from typing import Optional


class EmbeddingProvider(ABC):
    supported_providers = ["openai", "sentence-transformers"]

    def __init__(self, provider: str):
        if provider not in EmbeddingProvider.supported_providers:
            raise ValueError(
                f"Error, `{provider}` is not in EmbeddingProvider's list of supported providers."
            )

    @abstractmethod
    def _check_inputs(self, model: str, dimensions: Optional[int]) -> None:
        pass

    @abstractmethod
    def get_embedding(
        self, text: str, model: str, dimensions: Optional[int] = None
    ):
        pass

    @abstractmethod
    def get_embeddings(
        self, texts: list[str], model: str, dimensions: Optional[int] = None
    ):
        pass

    @abstractmethod
    def tokenize_string(self, text: str, model: str) -> list[int]:
        """Tokenizes the input string."""
        pass
