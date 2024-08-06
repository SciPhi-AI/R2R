import logging
from typing import Any, List


from .litellm import LiteLLMEmbeddingProvider
from r2r.base import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingPurpose,
    GenerationConfig
)

logger = logging.getLogger(__name__)


class SciPhiEmbeddingProvider(LiteLLMEmbeddingProvider):
    def __init__(
        self,
        config: EmbeddingConfig,
        *args,
        **kwargs,
    ) -> None:
        if config.provider != "sciphi":
            logger.error(f"Invalid provider: {config.provider}")
            raise ValueError(
                "SciPhiEmbeddingProvider must be initialized with config with `sciphi` provider."
            )
        config.provider = "litellm"
        super().__init__(config)
        self._validate_model()

    def _validate_model(self) -> None:
        if self.base_model != "sciphi/text-embedding-3-small":
            raise ValueError(
                "SciPhiEmbeddingProvider must be initialized with `sciphi/text-embedding-3-small` model."
            )
        self.base_model = "openai/text-embedding-3-small"

    async def _execute_task(self, task: dict[str, Any]) -> List[float]:
        return await super()._execute_task(task)

    def _execute_task_sync(self, task: dict[str, Any]) -> List[float]:
        return super()._execute_task_sync(task)

    async def async_get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> List[float]:
        self._validate_model(self.base_model)
        return await super().async_get_embedding(text, stage, purpose, **kwargs)

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> List[float]:
        return super().get_embedding(text, stage, purpose, **kwargs)

    async def async_get_embeddings(
        self,
        texts: List[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> List[List[float]]:
        return await super().async_get_embeddings(texts, stage, purpose, **kwargs)

    def get_embeddings(
        self,
        texts: List[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
        **kwargs,
    ) -> List[List[float]]:
        return super().get_embeddings(texts, stage, purpose, **kwargs)