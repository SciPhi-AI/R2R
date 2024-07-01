import logging
import os

from openai import AsyncOpenAI, AuthenticationError, OpenAI

from r2r.base import EmbeddingConfig, EmbeddingProvider, VectorSearchResult

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    MODEL_TO_TOKENIZER = {
        "text-embedding-ada-002": "cl100k_base",
        "text-embedding-3-small": "cl100k_base",
        "text-embedding-3-large": "cl100k_base",
    }
    MODEL_TO_DIMENSIONS = {
        "text-embedding-ada-002": [1536],
        "text-embedding-3-small": [512, 1536],
        "text-embedding-3-large": [256, 1024, 3072],
    }

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        provider = config.provider
        if not provider:
            raise ValueError(
                "Must set provider in order to initialize OpenAIEmbeddingProvider."
            )

        if provider != "openai":
            raise ValueError(
                "OpenAIEmbeddingProvider must be initialized with provider `openai`."
            )
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
            )
        self.client = OpenAI()
        self.async_client = AsyncOpenAI()

        if config.rerank_model:
            raise ValueError(
                "OpenAIEmbeddingProvider does not support separate reranking."
            )
        self.base_model = config.base_model
        self.base_dimension = config.base_dimension

        if self.base_model not in OpenAIEmbeddingProvider.MODEL_TO_TOKENIZER:
            raise ValueError(
                f"OpenAI embedding model {self.base_model} not supported."
            )
        if (
            self.base_dimension
            and self.base_dimension
            not in OpenAIEmbeddingProvider.MODEL_TO_DIMENSIONS[self.base_model]
        ):
            raise ValueError(
                f"Dimensions {self.dimension} for {self.base_model} are not supported"
            )

        if not self.base_model or not self.base_dimension:
            raise ValueError(
                "Must set base_model and base_dimension in order to initialize OpenAIEmbeddingProvider."
            )

        if config.rerank_model:
            raise ValueError(
                "OpenAIEmbeddingProvider does not support separate reranking."
            )

    def get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
            )

        try:
            return (
                self.client.embeddings.create(
                    input=[text],
                    model=self.base_model,
                    dimensions=self.base_dimension
                    or OpenAIEmbeddingProvider.MODEL_TO_DIMENSIONS[
                        self.base_model
                    ][-1],
                )
                .data[0]
                .embedding
            )
        except AuthenticationError as e:
            raise ValueError(
                "Invalid OpenAI API key provided. Please check your OPENAI_API_KEY environment variable."
            ) from e

    async def async_get_embedding(
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
            )

        try:
            response = await self.async_client.embeddings.create(
                input=[text],
                model=self.base_model,
                dimensions=self.base_dimension
                or OpenAIEmbeddingProvider.MODEL_TO_DIMENSIONS[
                    self.base_model
                ][-1],
            )
            return response.data[0].embedding
        except AuthenticationError as e:
            raise ValueError(
                "Invalid OpenAI API key provided. Please check your OPENAI_API_KEY environment variable."
            ) from e

    def get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
            )

        try:
            return [
                ele.embedding
                for ele in self.client.embeddings.create(
                    input=texts,
                    model=self.base_model,
                    dimensions=self.base_dimension
                    or OpenAIEmbeddingProvider.MODEL_TO_DIMENSIONS[
                        self.base_model
                    ][-1],
                ).data
            ]
        except AuthenticationError as e:
            raise ValueError(
                "Invalid OpenAI API key provided. Please check your OPENAI_API_KEY environment variable."
            ) from e

    async def async_get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError(
                "OpenAIEmbeddingProvider only supports search stage."
            )

        try:
            response = await self.async_client.embeddings.create(
                input=texts,
                model=self.base_model,
                dimensions=self.base_dimension
                or OpenAIEmbeddingProvider.MODEL_TO_DIMENSIONS[
                    self.base_model
                ][-1],
            )
            return [ele.embedding for ele in response.data]
        except AuthenticationError as e:
            raise ValueError(
                "Invalid OpenAI API key provided. Please check your OPENAI_API_KEY environment variable."
            ) from e

    def rerank(
        self,
        query: str,
        results: list[VectorSearchResult],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.RERANK,
        limit: int = 10,
    ):
        return results[:limit]

    def tokenize_string(self, text: str, model: str) -> list[int]:
        try:
            import tiktoken
        except ImportError:
            raise ValueError(
                "Must download tiktoken library to run `tokenize_string`."
            )
        # tiktoken encoding -
        # cl100k_base -	gpt-4, gpt-3.5-turbo, text-embedding-ada-002, text-embedding-3-small, text-embedding-3-large
        if model not in OpenAIEmbeddingProvider.MODEL_TO_TOKENIZER:
            raise ValueError(f"OpenAI embedding model {model} not supported.")
        encoding = tiktoken.get_encoding(
            OpenAIEmbeddingProvider.MODEL_TO_TOKENIZER[model]
        )
        return encoding.encode(text)
