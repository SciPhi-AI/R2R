"""A simple example to demonstrate the usage of `BasicRAGPipeline`."""
import logging

import dotenv

from sciphi_r2r.core import GenerationConfig, LoggingDatabaseConnection
from sciphi_r2r.embeddings import OpenAIEmbeddingProvider
from sciphi_r2r.llms import OpenAIConfig, OpenAILLM
from sciphi_r2r.pipelines import BasicRAGPipeline
from sciphi_r2r.vector_dbs import PGVectorDB

logger = logging.getLogger("sciphi_r2r")

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    logging.debug("Starting the completion pipeline")

    logging.debug("Using `OpenAIEmbeddingProvider` to provide embeddings.")
    embeddings_provider = OpenAIEmbeddingProvider()
    embedding_model = "text-embedding-3-small"
    embedding_dimension = 1536

    logging.debug("Using `PGVectorDB` to store and retrieve embeddings.")
    db = PGVectorDB()
    collection_name = "demo-v1"
    db.initialize_collection(collection_name, embedding_dimension)

    logging.debug("Using `OpenAILLM` to provide language models.")
    llm = OpenAILLM(OpenAIConfig())
    generation_config = GenerationConfig(
        model_name="gpt-4-1106-preview",
        temperature=0.1,
        top_p=0.9,
        top_k=128,
        max_tokens_to_sample=1_024,
        do_stream=False,
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
    logging.info(f"Final Result:\n{result}")
    pipeline.close()
