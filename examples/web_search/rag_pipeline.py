"""A simple example to demonstrate the usage of `WebSearchRAGPipeline`."""
import logging

import dotenv

from sciphi_r2r.core import GenerationConfig, LoggingDatabaseConnection
from sciphi_r2r.embeddings import OpenAIEmbeddingProvider
from sciphi_r2r.llms import OpenAIConfig, OpenAILLM
from sciphi_r2r.main import load_config
from sciphi_r2r.pipelines import WebSearchRAGPipeline
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

    query = "What are the energy levels for a particle in a box?"

    logger = logging.getLogger(logging_config["name"])
    logging.basicConfig(level=logging_config["level"])

    logger.debug("Starting the rag pipeline.")

    embeddings_provider = OpenAIEmbeddingProvider()
    embedding_model = embedding_config["model"]
    embedding_dimension = embedding_config["dimension"]
    embedding_batch_size = embedding_config["batch_size"]

    db = PGVectorDB()
    collection_name = database_config["collection_name"]
    db.initialize_collection(collection_name, embedding_dimension)

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
    pipeline = WebSearchRAGPipeline(
        llm,
        generation_config,
        logging_database,
        db=db,
        embedding_model=embedding_model,
        embeddings_provider=embeddings_provider,
    )

    completion = pipeline.run(query) #, search_only=True)

    logger.info(f"Final Result:\n{completion}")

    pipeline.close()
