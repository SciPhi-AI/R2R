"""A simple example to demonstrate the usage of `BasicEmbeddingPipeline`."""
import logging
import uuid

import dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter

from r2r.core import DatasetConfig, LoggingDatabaseConnection
from r2r.datasets import HuggingFaceDataProvider
from r2r.embeddings import OpenAIEmbeddingProvider
from r2r.main import load_config
from r2r.pipelines import BasicDocument, BasicEmbeddingPipeline
from r2r.vector_dbs import PGVectorDB, QdrantDB

if __name__ == "__main__":
    dotenv.load_dotenv()

    (
        logging_config,
        embedding_config,
        database_config,
        llm_config,
        text_splitter_config,
        evals_config,
    ) = load_config()

    logger = logging.getLogger(logging_config["name"])
    logging.basicConfig(level=logging_config["level"])

    logger.info("Starting the embedding pipeline")

    # Specify the embedding provider
    embeddings_provider = OpenAIEmbeddingProvider()
    embedding_model = embedding_config["model"]
    embedding_dimension = embedding_config["dimension"]
    embedding_batch_size = embedding_config["batch_size"]

    # Specify the vector database provider
    db = (
        QdrantDB() if database_config["provider"] == "qdrant" else PGVectorDB()
    )
    collection_name = database_config["collection_name"]
    db.initialize_collection(collection_name, embedding_dimension)

    # Specify the dataset providers
    dataset_provider = HuggingFaceDataProvider()
    dataset_provider.load_datasets(
        [
            DatasetConfig("camel-ai/physics", None, 10, "message_2"),
            DatasetConfig("camel-ai/chemistry", None, 10, "message_2"),
        ],
    )

    # Specify the chunking strategy
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=text_splitter_config["chunk_size"],
        chunk_overlap=text_splitter_config["chunk_overlap"],
        length_function=len,
        is_separator_regex=False,
    )

    logging_provider = LoggingDatabaseConnection(logging_config["database"])

    pipeline = BasicEmbeddingPipeline(
        embedding_model,
        embeddings_provider,
        db,
        text_splitter=text_splitter,
        embedding_batch_size=embedding_batch_size,
        logging_provider=logging_provider,
    )

    entry_id = 0
    document_batch = []
    for entry in dataset_provider.stream_text():
        if entry is None:
            break
        text, config = entry
        document_id = str(uuid.uuid5(uuid.NAMESPACE_URL, config.name))

        if text is None:
            break
        document_batch.append(
            BasicDocument(
                id=str(
                    uuid.uuid5(uuid.NAMESPACE_URL, f"{config.name}_{text}")
                ),
                text=text,
                metadata={"document_id": document_id},
            )
        )
        entry_id += 1

        if len(document_batch) == 1:
            logging.info(
                f"Processing batch of {len(document_batch)} documents."
            )
            pipeline.run(document_batch)
            document_batch = []

    logging.info(f"Processing final {len(document_batch)} documents.")
    pipeline.run(document_batch)

    pipeline.close()
