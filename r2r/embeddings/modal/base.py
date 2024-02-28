import logging
from typing import Optional

import modal

from r2r.core import EmbeddingProvider

logger = logging.getLogger(__name__)


class ModalEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        modal_app_name: str,
        modal_class_name: str,
        dimension: int,
        batch: int,
        provider: str = "modal",
    ):
        logger.info(
            "Initializing `ModalEmbeddingProvider` to provide embeddings."
        )
        super().__init__(provider)
        try:
            cls = modal.Cls.lookup(modal_app_name, modal_class_name)
            model = cls()
        except ImportError:
            raise ValueError("Unable to get modal's model cls")
        self.model = model
        self.dimension = dimension
        self.batch = batch

    def _check_inputs(self, model: str, dimensions: Optional[int]) -> None:
        if dimensions and dimensions != self.dimension:
            raise ValueError(
                f"Dimensions {dimensions} for {model} are not supported"
            )

    def get_embedding(
        self, text: str, model: str, dimensions: Optional[int] = None
    ) -> list[float]:
        raise ValueError(
            "ModalEmbeddingProvider does not support `get_embedding`."
        )

    def get_embeddings(
        self, texts: list[str], model: str, dimensions: Optional[int] = None
    ) -> list[list[float]]:
        self._check_inputs(model, dimensions)
        return self.model.completion_stream.remote(texts)

    def tokenize_string(self, text: str, model: str) -> list[int]:
        raise ValueError(
            "ModalEmbeddingProvider does not support `tokenize_string`."
        )
