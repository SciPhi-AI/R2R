import logging

import dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter

from r2r.core import GenerationConfig, LoggingDatabaseConnection
from r2r.datasets import HuggingFaceDataProvider
from r2r.llms import OpenAIConfig, OpenAILLM
from r2r.pipelines import (
    BasicEmbeddingPipeline,
    BasicIngestionPipeline,
    BasicRAGPipeline,
)
from r2r.vector_dbs import PGVectorDB, QdrantDB

from .app import create_app
from .utils import load_config

dotenv.load_dotenv()


class E2EPipelineFactory:
    @staticmethod
    def get_db(database_config):
        if database_config["vector_db_provider"] == "qdrant":
            return QdrantDB()
        else:
            return PGVectorDB()

    @staticmethod
    def get_embeddings_provider(embedding_config: dict):
        if embedding_config["provider"] == "openai":
            from r2r.embeddings import OpenAIEmbeddingProvider

            return OpenAIEmbeddingProvider()
        elif embedding_config["provider"] == "sentence_transformers":
            from r2r.embeddings import SentenceTransformerEmbeddingProvider

            return SentenceTransformerEmbeddingProvider()

    @staticmethod
    def get_llm():
        return OpenAILLM(OpenAIConfig())

    @staticmethod
    def get_text_splitter(text_splitter_config):
        return RecursiveCharacterTextSplitter(
            chunk_size=text_splitter_config["chunk_size"],
            chunk_overlap=text_splitter_config["chunk_overlap"],
            length_function=len,
            is_separator_regex=False,
        )

    @staticmethod
    def get_dataset_provider():
        return HuggingFaceDataProvider()

    @staticmethod
    def create_pipeline(
        db=None,
        embeddings_provider=None,
        llm=None,
        text_splitter=None,
        dataset_provider=None,
        llm_config=None,
        ingestion_pipeline_impl=BasicIngestionPipeline,
        embedding_pipeline_impl=BasicEmbeddingPipeline,
        rag_pipeline_impl=BasicRAGPipeline,
        app_fn=create_app,
        config_path=None,
    ):
        (
            api_config,
            logging_config,
            embedding_config,
            database_config,
            llm_config,
            text_splitter_config,
        ) = load_config(config_path)

        logger = logging.getLogger(logging_config["name"])
        logging.basicConfig(level=logging_config["level"])

        logger.debug("Starting the completion pipeline")

        logger.debug("Using `OpenAIEmbeddingProvider` to provide embeddings.")

        embeddings_provider = (
            embeddings_provider
            or E2EPipelineFactory.get_embeddings_provider(embedding_config)
        )
        # TODO - Encapsulate the embedding metadata into a container
        embedding_model = embedding_config["model"]
        embedding_dimension = embedding_config["dimension"]
        embedding_batch_size = embedding_config["batch_size"]

        logger.debug("Using `PGVectorDB` to store and retrieve embeddings.")
        db = db or E2EPipelineFactory.get_db(database_config)
        collection_name = database_config["collection_name"]
        db.initialize_collection(collection_name, embedding_dimension)

        logger.debug("Using `OpenAILLM` to provide language models.")
        llm = llm or E2EPipelineFactory.get_llm()
        generation_config = llm_config or GenerationConfig(
            model_name=llm_config["model_name"],
            temperature=llm_config["temperature"],
            top_p=llm_config["top_p"],
            top_k=llm_config["top_k"],
            max_tokens_to_sample=llm_config["max_tokens_to_sample"],
            do_stream=llm_config["do_stream"],
        )

        all_logging = LoggingDatabaseConnection(logging_config["database"])

        cmpl_pipeline = rag_pipeline_impl(
            llm,
            generation_config,
            db=db,
            embedding_model=embedding_model,
            embeddings_provider=embeddings_provider,
            logging_database=all_logging,
        )

        text_splitter = text_splitter or E2EPipelineFactory.get_text_splitter(
            text_splitter_config
        )
        dataset_provider = (
            dataset_provider or E2EPipelineFactory.get_dataset_provider()
        )

        embd_pipeline = embedding_pipeline_impl(
            embedding_model,
            embeddings_provider,
            db,
            logging_database=all_logging,
            text_splitter=text_splitter,
            embedding_batch_size=embedding_batch_size,
        )
        # TODO - Set ingestion class in config file
        ingst_pipeline = ingestion_pipeline_impl()

        app = app_fn(
            ingestion_pipeline=ingst_pipeline,
            embedding_pipeline=embd_pipeline,
            rag_pipeline=cmpl_pipeline,
            logging_database=all_logging,
        )

        return app
