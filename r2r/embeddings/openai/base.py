import logging
import os
from typing import Optional

from openai import OpenAI

from r2r.core import EmbeddingProvider

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

    def __init__(self, provider: str = "openai"):
        logger.info(
            "Initializing `OpenAIEmbeddingProvider` to provide embeddings."
        )

        super().__init__(provider)
        if provider != "openai":
            raise ValueError(
                "OpenAIEmbeddingProvider must be initialized with provider `openai`."
            )
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
            )
        self.client = OpenAI()

    def _check_inputs(self, model: str, dimensions: Optional[int]) -> None:
        if model not in OpenAIEmbeddingProvider.MODEL_TO_TOKENIZER:
            raise ValueError(f"OpenAI embedding model {model} not supported.")
        if (
            dimensions
            and dimensions
            not in OpenAIEmbeddingProvider.MODEL_TO_DIMENSIONS[model]
        ):
            raise ValueError(
                f"Dimensions {dimensions} for {model} are not supported"
            )
        # TODO - Check max length of tokenized documents?

    def get_embedding(
        self, text: str, model: str, dimensions: Optional[int] = None
    ) -> list[float]:
        self._check_inputs(model, dimensions)
        return (
            self.client.embeddings.create(
                input=[text],
                model=model,
                dimensions=dimensions
                or OpenAIEmbeddingProvider.MODEL_TO_DIMENSIONS[model][-1],
            )
            .data[0]
            .embedding
        )

    def get_embeddings(
        self, texts: list[str], model: str, dimensions: Optional[int] = None
    ) -> list[list[float]]:
        self._check_inputs(model, dimensions)
        return [
            ele.embedding
            for ele in self.client.embeddings.create(
                input=texts,
                model=model,
                dimensions=dimensions
                or OpenAIEmbeddingProvider.MODEL_TO_DIMENSIONS[model][-1],
            ).data
        ]

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
