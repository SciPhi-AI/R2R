"""A simple example to demonstrate the usage of `BasicRAGPipeline`."""
import logging

import dotenv

from sciphi_r2r.core import GenerationConfig, LoggingDatabaseConnection
from sciphi_r2r.embeddings import OpenAIEmbeddingProvider
from sciphi_r2r.llms import OpenAIConfig, OpenAILLM
from sciphi_r2r.main import load_config
from sciphi_r2r.pipelines import BasicRAGPipeline
from sciphi_r2r.vector_dbs import PGVectorDB

if __name__ == "__main__":
    dotenv.load_dotenv()

    (
        api_config,
        logging_config,
        embedding_config,
        database_config,
        language_model_config,
        text_splitter_config,
    ) = load_config()

    logger = logging.getLogger(logging_config["name"])
    logging.basicConfig(level=logging_config["level"])

    logger.debug("Starting the completion pipeline")

    logger.debug("Using `OpenAIEmbeddingProvider` to provide embeddings.")
    embeddings_provider = OpenAIEmbeddingProvider()
    embedding_model = embedding_config["model"]
    embedding_dimension = embedding_config["dimension"]
    embedding_batch_size = embedding_config["batch_size"]

    logger.debug("Using `PGVectorDB` to store and retrieve embeddings.")
    db = PGVectorDB()
    collection_name = database_config["collection_name"]
    db.initialize_collection(collection_name, embedding_dimension)

    logger.debug("Using `OpenAILLM` to provide language models.")
    llm = OpenAILLM(OpenAIConfig())
    generation_config = GenerationConfig(
        model_name=language_model_config["model_name"],
        temperature=language_model_config["temperature"],
        top_p=language_model_config["top_p"],
        top_k=language_model_config["top_k"],
        max_tokens_to_sample=language_model_config["max_tokens_to_sample"],
        do_stream=language_model_config["do_stream"],
    )

    logging_database = LoggingDatabaseConnection("completion_demo_logs_v1")
    pipeline = BasicRAGPipeline(
        llm,
        generation_config,
        logging_database,
        db=db,
        embedding_model=embedding_model,
        embeddings_provider=embeddings_provider,
    )

    query = "What is Schrodingers equation?"
    result = pipeline.run(query)
    logger.info(f"Final Result:\n{result}")
    pipeline.close()
