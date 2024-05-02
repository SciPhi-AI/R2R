"""
A simple example to demonstrate the usage of `QnARAGPipeline`.
"""

import logging
from typing import Optional

from r2r.core import (
    EmbeddingProvider,
    LLMProvider,
    LoggingDatabaseConnection,
    PromptProvider,
    RAGPipeline,
    VectorDBProvider,
)

from ...prompts.local.prompt import BasicPromptProvider

logger = logging.getLogger(__name__)


class QnARAGPipeline(RAGPipeline):
    """
    Implements a basic question and answer Retrieval-Augmented-Generation (RAG) pipeline.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        llm_provider: LLMProvider,
        vector_db_provider: VectorDBProvider,
        prompt_provider: Optional[PromptProvider] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        system_prompt: Optional[str] = BasicPromptProvider.BASIC_SYSTEM_PROMPT,
        return_pompt: Optional[str] = BasicPromptProvider.BASIC_RETURN_PROMPT,
    ) -> None:
        """
        Initializes the RAG pipeline with necessary components and configurations.
        """
        logger.info(f"Initalizing `QnARAGPipeline` to process user requests.")
        if not prompt_provider:
            prompt_provider = BasicPromptProvider(
                system_prompt,
                return_pompt,
            )
        self.prompt_provider = prompt_provider

        super().__init__(
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
            vector_db_provider=vector_db_provider,
            logging_connection=logging_connection,
            prompt_provider=prompt_provider,
        )
