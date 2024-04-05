import logging
from typing import Any

import dotenv

from r2r.core import LoggingDatabaseConnection
from r2r.core.utils import RecursiveCharacterTextSplitter
from r2r.llms import (
    LiteLLM,
    LiteLLMConfig,
    LlamaCPP,
    LlamaCppConfig,
    OpenAIConfig,
    OpenAILLM,
)
from r2r.pipelines import (
    BasicEmbeddingPipeline,
    BasicEvalPipeline,
    BasicIngestionPipeline,
    BasicRAGPipeline,
)

from .app import create_app
from .utils import R2RConfig

dotenv.load_dotenv()


class E2EPipelineFactory:
    @staticmethod
    def get_vector_db(database_config: dict[str, Any]):
        if database_config["provider"] == "qdrant":
            from r2r.vector_dbs import QdrantDB

            return QdrantDB()
        elif database_config["provider"] == "pgvector":
            from r2r.vector_dbs import PGVectorDB

            return PGVectorDB()
        elif database_config["provider"] == "local":
            from r2r.vector_dbs import LocalVectorDB

            return LocalVectorDB()

    @staticmethod
    def get_embeddings_provider(embedding_config: dict[str, Any]):
        if embedding_config["provider"] == "openai":
            from r2r.embeddings import OpenAIEmbeddingProvider

            return OpenAIEmbeddingProvider()
        elif embedding_config["provider"] == "sentence-transformers":
            from r2r.embeddings import SentenceTransformerEmbeddingProvider

            return SentenceTransformerEmbeddingProvider(
                embedding_config["model"]
            )
        else:
            raise ValueError(
                f"Embedding provider {embedding_config['provider']} not supported"
            )

    @staticmethod
    def get_llm(llm_config: dict[str, Any]):
        if llm_config["provider"] == "openai":
            return OpenAILLM(OpenAIConfig())
        elif llm_config["provider"] == "litellm":
            return LiteLLM(LiteLLMConfig())
        elif llm_config["provider"] == "llama-cpp":
            return LlamaCPP(
                LlamaCppConfig(
                    llm_config.get("model_path", ""),
                    llm_config.get("model_name", ""),
                )
            )

    @staticmethod
    def get_text_splitter(text_splitter_config: dict[str, Any]):
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
        db=None,
        embeddings_provider=None,
        llm=None,
        text_splitter=None,
        adapters=None,
        ingestion_pipeline_impl=BasicIngestionPipeline,
        embedding_pipeline_impl=BasicEmbeddingPipeline,
        rag_pipeline_impl=BasicRAGPipeline,
        eval_pipeline_impl=BasicEvalPipeline,
        app_fn=create_app,
    ):
        logging.basicConfig(level=config.logging_database["level"])

        embeddings_provider = (
            embeddings_provider
            or E2EPipelineFactory.get_embeddings_provider(config.embedding)
        )
        embedding_model = config.embedding["model"]
        embedding_dimension = config.embedding["dimension"]
        embedding_batch_size = config.embedding["batch_size"]

        db = db or E2EPipelineFactory.get_vector_db(config.vector_database)
        collection_name = config.vector_database["collection_name"]
        db.initialize_collection(collection_name, embedding_dimension)

        llm = llm or E2EPipelineFactory.get_llm(config.language_model)

        logging_connection = LoggingDatabaseConnection(
            config.logging_database["provider"],
            config.logging_database["collection_name"],
        )

        cmpl_pipeline = rag_pipeline_impl(
            llm,
            db=db,
            embedding_model=embedding_model,
            embeddings_provider=embeddings_provider,
            logging_connection=logging_connection,
        )

        text_splitter = text_splitter or E2EPipelineFactory.get_text_splitter(
            config.ingestion["text_splitter"]
        )

        embd_pipeline = embedding_pipeline_impl(
            embedding_model,
            embeddings_provider,
            db,
            logging_connection=logging_connection,
            text_splitter=text_splitter,
            embedding_batch_size=embedding_batch_size,
        )

        eval_pipeline = eval_pipeline_impl(
            config.evals, logging_connection=logging_connection
        )
        ingst_pipeline = ingestion_pipeline_impl(adapters=adapters)

        app = app_fn(
            ingestion_pipeline=ingst_pipeline,
            embedding_pipeline=embd_pipeline,
            rag_pipeline=cmpl_pipeline,
            eval_pipeline=eval_pipeline,
            config=config,
            logging_connection=logging_connection,
        )

        return app
