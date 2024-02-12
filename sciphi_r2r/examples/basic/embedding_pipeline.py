"""A simple example to demonstrate the usage of `BasicEmbeddingPipeline`."""
import logging

import dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter

from sciphi_r2r.core import DatasetConfig, LoggingDatabaseConnection
from sciphi_r2r.datasets import HuggingFaceDataProvider
from sciphi_r2r.embeddings import OpenAIEmbeddingProvider
from sciphi_r2r.pipelines import BasicEmbeddingPipeline
from sciphi_r2r.vector_dbs import PGVectorDB

logger = logging.getLogger("sciphi_r2r")

if __name__ == "__main__":
    dotenv.load_dotenv()
    logger = logging.getLogger("sciphi_r2r")
    logging.basicConfig(level=logging.DEBUG)

    logger.debug("Starting the embedding pipeline")

    embedding_model = "text-embedding-3-small"
    embeddings_provider = OpenAIEmbeddingProvider()
    embedding_dimension = 1536

    db = PGVectorDB()
    collection_name = "demo-v1"
    db.initialize_collection(collection_name, embedding_dimension)

    dataset_provider = HuggingFaceDataProvider()
    dataset_provider.load_datasets(
        [
            DatasetConfig("camel-ai/physics", None, 10, "message_2"),
            DatasetConfig("camel-ai/chemistry", None, 10, "message_2"),
        ],
    )

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=20,
        length_function=len,
        is_separator_regex=False,
    )
    logging_database = LoggingDatabaseConnection("embedding_demo_logs_v1")
    pipeline = BasicEmbeddingPipeline(
        dataset_provider,
        embedding_model,
        embeddings_provider,
        db,
        logging_database=logging_database,
        text_splitter=text_splitter,
    )
    pipeline.run()
    pipeline.close()
