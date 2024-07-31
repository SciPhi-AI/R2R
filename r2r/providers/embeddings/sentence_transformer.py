import asyncio
import logging
from typing import Any, List

from r2r.base import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingPurpose,
    VectorSearchResult,
)

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        config: EmbeddingConfig,
    ):
        super().__init__(config)
        logger.info(
            "Initializing `SentenceTransformerEmbeddingProvider` with separate models for search and rerank."
        )
        provider = config.provider
        if not provider:
            raise ValueError(
                "Must set provider in order to initialize SentenceTransformerEmbeddingProvider."
            )
        if provider != "sentence-transformers":
            raise ValueError(
                "SentenceTransformerEmbeddingProvider must be initialized with provider `sentence-transformers`."
            )
        try:
            from sentence_transformers import CrossEncoder, SentenceTransformer

            self.SentenceTransformer = SentenceTransformer
            self.CrossEncoder = CrossEncoder
        except ImportError as e:
            raise ValueError(
                "Must download sentence-transformers library to run `SentenceTransformerEmbeddingProvider`."
            ) from e

        self.do_search = False
        self.do_rerank = False

        self.search_encoder = self._init_model(
            config, EmbeddingProvider.PipeStage.BASE
        )
        self.rerank_encoder = self._init_model(
            config, EmbeddingProvider.PipeStage.RERANK
        )
        self.set_prefixes(config.prefixes or {}, self.base_model)
        self.semaphore = asyncio.Semaphore(config.concurrent_request_limit)

    def _init_model(
        self, config: EmbeddingConfig, stage: EmbeddingProvider.PipeStage
    ):
        stage_name = stage.name.lower()
        model = config.dict().get(f"{stage_name}_model", None)
        dimension = config.dict().get(f"{stage_name}_dimension", None)
        transformer_type = config.dict().get(
            f"{stage_name}_transformer_type", "SentenceTransformer"
        )

        if stage == EmbeddingProvider.PipeStage.BASE:
            self.do_search = True
            if not (model and dimension and transformer_type):
                raise ValueError(
                    f"Must set {stage_name}_model and {stage_name}_dimension for {stage} stage in order to initialize SentenceTransformerEmbeddingProvider."
                )

        if stage == EmbeddingProvider.PipeStage.RERANK:
            if not (model and dimension and transformer_type):
                return None

            self.do_rerank = True
            if transformer_type == "SentenceTransformer":
                raise ValueError(
                    f"`SentenceTransformer` models are not yet supported for {stage} stage in SentenceTransformerEmbeddingProvider."
                )

        setattr(self, f"{stage_name}_model", model)
        setattr(self, f"{stage_name}_dimension", dimension)
        setattr(self, f"{stage_name}_transformer_type", transformer_type)

        encoder = (
            self.SentenceTransformer(
                model, truncate_dim=dimension, trust_remote_code=True
            )
            if transformer_type == "SentenceTransformer"
            else self.CrossEncoder(model, trust_remote_code=True)
        )
        return encoder

    async def _execute_task(self, task: dict[str, Any]) -> List[float]:
        text = task["text"]
        stage = task["stage"]
        purpose = task["purpose"]

        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "Only BASE stage is supported for embedding tasks."
            )
        if not self.do_search:
            raise ValueError("Search model is not set.")

        text = self.prefixes.get(purpose, "") + text
        encoder = self.search_encoder
        return encoder.encode([text]).tolist()[0]

    def _execute_task_sync(self, task: dict[str, Any]) -> List[float]:
        return asyncio.run(self._execute_task(task))

    async def async_get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ) -> List[float]:
        task = {
            "text": text,
            "stage": stage,
            "purpose": purpose,
        }
        return await self._execute_with_backoff_async(task)

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ) -> List[float]:
        task = {
            "text": text,
            "stage": stage,
            "purpose": purpose,
        }
        return self._execute_with_backoff_sync(task)

    async def async_get_embeddings(
        self,
        texts: List[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ) -> List[List[float]]:
        tasks = [
            {
                "text": text,
                "stage": stage,
                "purpose": purpose,
            }
            for text in texts
        ]
        return await asyncio.gather(
            *[self._execute_with_backoff_async(task) for task in tasks]
        )

    def get_embeddings(
        self,
        texts: List[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
        purpose: EmbeddingPurpose = EmbeddingPurpose.INDEX,
    ) -> List[List[float]]:
        tasks = [
            {
                "text": text,
                "stage": stage,
                "purpose": purpose,
            }
            for text in texts
        ]
        return [self._execute_with_backoff_sync(task) for task in tasks]

    def rerank(
        self,
        query: str,
        results: list[VectorSearchResult],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.RERANK,
        limit: int = 10,
    ) -> list[VectorSearchResult]:
        if stage != EmbeddingProvider.PipeStage.RERANK:
            raise ValueError("`rerank` only supports `RERANK` stage.")
        if not self.do_rerank:
            return results[:limit]

        from copy import copy

        texts = copy([doc.metadata["text"] for doc in results])
        reranked_scores = self.rerank_encoder.rank(
            query, texts, return_documents=False, top_k=limit
        )
        reranked_results = []
        for score in reranked_scores:
            corpus_id = score["corpus_id"]
            new_result = results[corpus_id]
            new_result.score = float(score["score"])
            reranked_results.append(new_result)

        reranked_results.sort(key=lambda doc: doc.score, reverse=True)
        return reranked_results

    def tokenize_string(
        self,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[int]:
        raise ValueError(
            "SentenceTransformerEmbeddingProvider does not support tokenize_string."
        )
