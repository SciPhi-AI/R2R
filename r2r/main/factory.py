import logging
from typing import Any

import dotenv

from r2r.core import (
    EmbeddingConfig,
    EvalConfig,
    LLMConfig,
    LoggingDatabaseConnection,
    VectorDBConfig,
)
from r2r.core.utils import RecursiveCharacterTextSplitter
from r2r.llms import LiteLLM, LlamaCPP, LlamaCppConfig, OpenAILLM
from r2r.pipelines import (
    BasicEvalPipeline,
    DefaultDocumentParsingPipeline,
    DefaultEmbeddingPipeline,
    DocumentType,
    QnARAGPipeline,
)

from .app import create_app
from .utils import R2RConfig

dotenv.load_dotenv()


class E2EPipelineFactory:
    """Factory class to create the end-to-end pipeline."""

    @staticmethod
    def get_vector_db_provider(database_config: dict[str, Any]):
        """Get the vector database provider based on the provided database_config."""
        if database_config["provider"] == "qdrant":
            from r2r.vector_dbs import QdrantDB

            return QdrantDB(VectorDBConfig.create(**database_config))
        elif database_config["provider"] == "pgvector":
            from r2r.vector_dbs import PGVectorDB

            return PGVectorDB(VectorDBConfig.create(**database_config))
        elif database_config["provider"] == "local":
            from r2r.vector_dbs import (
                LocalVectorDBConfig,
                LocalVectorDBProvider,
            )

            return LocalVectorDBProvider(
                LocalVectorDBConfig.create(**database_config)
            )

    @staticmethod
    def get_embedding_provider(embedding_config: dict[str, Any]):
        """Get the embedding provider based on the provided embedding_config."""
        embedding_config = EmbeddingConfig.create(**embedding_config)

        if embedding_config.provider == "openai":
            from r2r.embeddings import OpenAIEmbeddingProvider

            return OpenAIEmbeddingProvider(embedding_config)
        elif embedding_config.provider == "sentence-transformers":
            from r2r.embeddings import SentenceTransformerEmbeddingProvider

            return SentenceTransformerEmbeddingProvider(embedding_config)
        elif embedding_config.provider == "dummy":
            from r2r.embeddings import DummyEmbeddingProvider

            return DummyEmbeddingProvider(embedding_config)
        else:
            raise ValueError(
                f"Embedding provider {embedding_config.provider} not supported"
            )

    @staticmethod
    def get_eval_provider(eval_config: dict[str, Any]):
        """Get the evaluation provider based on the provided eval_config."""
        eval_config = EvalConfig.create(**eval_config)

        if eval_config.provider == "deepeval":
            try:
                from r2r.eval import DeepEvalProvider
            except ImportError:
                raise ImportError(
                    "DeepEval is not installed. Please install it using `pip install deepeval`."
                )
            eval_provider = DeepEvalProvider(eval_config)

        elif eval_config.provider == "parea":
            try:
                from r2r.eval import PareaEvalProvider
            except ImportError:
                raise ImportError(
                    "Parea is not installed. Please install it using `pip install parea-ai`."
                )
            eval_provider = PareaEvalProvider(eval_config)
        elif eval_config.provider == "none":
            eval_provider = None
        return eval_provider

    @staticmethod
    def get_llm_provider(llm_config: dict[str, Any]):
        """Get the language model provider based on the provided llm_config."""

        if llm_config["provider"] == "openai":
            return OpenAILLM(LLMConfig.create(**llm_config))
        elif llm_config["provider"] == "litellm":
            return LiteLLM(LLMConfig.create(**llm_config))
        elif llm_config["provider"] == "llama-cpp":
            return LlamaCPP(LlamaCppConfig.create(**llm_config))

    @staticmethod
    def get_text_splitter(text_splitter_config: dict[str, Any]):
        """Get the text splitter based on the provided text_splitter_config."""

        if text_splitter_config["type"] != "recursive_character":
            raise ValueError(
                "Only recursive character text splitter is supported"
            )
        return RecursiveCharacterTextSplitter(
            chunk_size=text_splitter_config["chunk_size"],
            chunk_overlap=text_splitter_config["chunk_overlap"],
            length_function=len,
            is_separator_regex=False,
        )

    @staticmethod
    def create_pipeline(
        config: R2RConfig,
        vector_db_provider=None,
        embedding_provider=None,
        llm_provider=None,
        override_parsers=None,
        ingestion_pipeline_impl=DefaultDocumentParsingPipeline,
        embedding_pipeline_impl=DefaultEmbeddingPipeline,
        rag_pipeline_impl=QnARAGPipeline,
        eval_pipeline_impl=BasicEvalPipeline,
        app_fn=create_app,
    ):
        logging.basicConfig(level=config.logging_database.get("level", "INFO"))

        embedding_provider = (
            embedding_provider
            or E2EPipelineFactory.get_embedding_provider(config.embedding)
        )
        llm_provider = llm_provider or E2EPipelineFactory.get_llm_provider(
            config.language_model
        )
        vector_db_provider = (
            vector_db_provider
            or E2EPipelineFactory.get_vector_db_provider(
                config.vector_database
            )
        )
        vector_db_provider.initialize_collection(
            embedding_provider.search_dimension
        )

        eval_provider = E2EPipelineFactory.get_eval_provider(config.eval)

        logging_connection = LoggingDatabaseConnection(
            config.logging_database["provider"],
            config.logging_database["collection_name"],
        )

        scrpr_pipeline = scraper_pipeline_impl()
        ingst_pipeline = ingestion_pipeline_impl(
            override_parsers=override_parsers,
            selected_parsers={
                DocumentType(k): v
                for k, v in config.ingestion.get("selected_parsers").items()
            },
        )
        embd_pipeline = embedding_pipeline_impl(
            embedding_provider=embedding_provider,
            vector_db_provider=vector_db_provider,
            logging_connection=logging_connection,
            text_splitter=E2EPipelineFactory.get_text_splitter(
                config.embedding["text_splitter"]
            ),
            embedding_batch_size=config.embedding.get("batch_size", 1),
        )
        rag_pipeline = rag_pipeline_impl(
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
            vector_db_provider=vector_db_provider,
            logging_connection=logging_connection,
        )
        eval_pipeline = eval_pipeline_impl(
            eval_provider, logging_connection=logging_connection
        )

        app = app_fn(
            scraper_pipeline=scrpr_pipeline,
            ingestion_pipeline=ingst_pipeline,
            embedding_pipeline=embd_pipeline,
            rag_pipeline=rag_pipeline,
            eval_pipeline=eval_pipeline,
            config=config,
            logging_connection=logging_connection,
        )

        return app
