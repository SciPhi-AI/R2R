import logging
from typing import Optional

from r2r.core import EmbeddingProvider

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self, config: dict,
    ):
        super().__init__(config)
        logger.info(
            "Initializing `SentenceTransformerEmbeddingProvider` to provide embeddings."
        )
        print("config = ", config)
        provider = config.get("provider", None)
        if not provider:
            raise ValueError(
                "Must set provider in order to initialize SentenceTransformerEmbeddingProvider."
            )
        if provider != "sentence-transformers":
            raise ValueError(
                "SentenceTransformerEmbeddingProvider must be initialized with provider `sentence-transformers`."
            )
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ValueError(
                "Must download sentence-transformers library to run `SentenceTransformerEmbeddingProvider`."
            )
        
        model = config.get("model", None)
        if not model:
            raise ValueError(
                "Must set model in order to initialize SentenceTransformerEmbeddingProvider."
            )
        dimension = config.get("dimension", None)
        if not dimension:
            raise ValueError(
                "Must set dimensions in order to initialize SentenceTransformerEmbeddingProvider."
            )
        self.encoder = SentenceTransformer(model, truncate_dim=dimension, trust_remote_code=True)

    def _check_inputs(self, model: str, dimensions: Optional[int]) -> None:
        if (
            dimensions
            and dimensions != self.encoder.get_sentence_embedding_dimension()
        ):
            raise ValueError(
                f"Dimensions {dimensions} for {model} are not supported"
            )

    def get_embedding(
        self, text: str, model: str, dimensions: Optional[int] = None
    ) -> list[float]:
        self._check_inputs(model, dimensions)
        return self.encoder.encode([text]).tolist()[0]

    def get_embeddings(
        self, texts: list[str], model: str, dimensions: Optional[int] = None
    ) -> list[list[float]]:
        self._check_inputs(model, dimensions)
        return self.encoder.encode(texts).tolist()

    def tokenize_string(self, text: str, model: str) -> list[int]:
        raise ValueError(
            "SentenceTransformerEmbeddingProvider does not support `tokenize_string`."
        )
