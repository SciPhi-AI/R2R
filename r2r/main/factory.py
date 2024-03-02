import logging

import dotenv

from r2r.core import LoggingDatabaseConnection
from r2r.core.utils import RecursiveCharacterTextSplitter
from r2r.llms import LiteLLM, LiteLLMConfig, OpenAIConfig, OpenAILLM
from r2r.pipelines import (
    BasicEmbeddingPipeline,
    BasicEvalPipeline,
    BasicIngestionPipeline,
    BasicRAGPipeline,
)

from .app import create_app
from .utils import load_config

dotenv.load_dotenv()


class E2EPipelineFactory:
    @staticmethod
    def get_db(database_config):
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
    def get_embeddings_provider(embedding_config: dict):
        if embedding_config["provider"] == "openai":
            from r2r.embeddings import OpenAIEmbeddingProvider

            return OpenAIEmbeddingProvider()
        elif embedding_config["provider"] == "sentence_transformers":
            from r2r.embeddings import SentenceTransformerEmbeddingProvider

            return SentenceTransformerEmbeddingProvider(
                embedding_config["model"]
            )

    @staticmethod
    def get_llm(llm_config):
        if llm_config["provider"] == "openai":
            return OpenAILLM(OpenAIConfig())
        elif llm_config["provider"] == "litellm":
            return LiteLLM(LiteLLMConfig())

    @staticmethod
    def get_text_splitter(text_splitter_config):
        return RecursiveCharacterTextSplitter(
            chunk_size=text_splitter_config["chunk_size"],
            chunk_overlap=text_splitter_config["chunk_overlap"],
            length_function=len,
            is_separator_regex=False,
        )

    @staticmethod
    def create_pipeline(
        db=None,
        embeddings_provider=None,
        llm=None,
        text_splitter=None,
        generation_config=None,
        ingestion_pipeline_impl=BasicIngestionPipeline,
        embedding_pipeline_impl=BasicEmbeddingPipeline,
        rag_pipeline_impl=BasicRAGPipeline,
        eval_pipeline_impl=BasicEvalPipeline,
        app_fn=create_app,
        config_path=None,
    ):
        (
            logging_config,
            embedding_config,
            database_config,
            llm_config,
            text_splitter_config,
            evals_config,
        ) = load_config(config_path)

        logging.basicConfig(level=logging_config["level"])

        embeddings_provider = (
            embeddings_provider
            or E2EPipelineFactory.get_embeddings_provider(embedding_config)
        )
        # TODO - Encapsulate the embedding metadata into a container
        embedding_model = embedding_config["model"]
        embedding_dimension = embedding_config["dimension"]
        embedding_batch_size = embedding_config["batch_size"]

        db = db or E2EPipelineFactory.get_db(database_config)
        collection_name = database_config["collection_name"]
        db.initialize_collection(collection_name, embedding_dimension)

        llm = llm or E2EPipelineFactory.get_llm(llm_config)

        logging_provider = LoggingDatabaseConnection(
            logging_config["provider"], logging_config["database"]
        )

        cmpl_pipeline = rag_pipeline_impl(
            llm,
            db=db,
            embedding_model=embedding_model,
            embeddings_provider=embeddings_provider,
            logging_provider=logging_provider,
        )

        text_splitter = text_splitter or E2EPipelineFactory.get_text_splitter(
            text_splitter_config
        )

        embd_pipeline = embedding_pipeline_impl(
            embedding_model,
            embeddings_provider,
            db,
            logging_provider=logging_provider,
            text_splitter=text_splitter,
            embedding_batch_size=embedding_batch_size,
        )
        # TODO - Set ingestion class in config file
        eval_pipeline = eval_pipeline_impl(
            evals_config, logging_provider=logging_provider
        )
        ingst_pipeline = ingestion_pipeline_impl()

        app = app_fn(
            ingestion_pipeline=ingst_pipeline,
            embedding_pipeline=embd_pipeline,
            rag_pipeline=cmpl_pipeline,
            eval_pipeline=eval_pipeline,
            logging_provider=logging_provider,
        )

        return app
