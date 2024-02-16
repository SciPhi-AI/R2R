"""A simple example to demonstrate the usage of `BasicRAGPipeline`."""
import logging
import uuid

import dotenv

from sciphi_r2r.core import GenerationConfig, LoggingDatabaseConnection
from sciphi_r2r.embeddings import OpenAIEmbeddingProvider
from sciphi_r2r.llms import OpenAIConfig, OpenAILLM
from sciphi_r2r.main import load_config
from sciphi_r2r.pipelines import BasicRAGPipeline
from sciphi_r2r.vector_dbs import PGVectorDB


class DemoRAGPipeline(BasicRAGPipeline):
    # Modifies `BasicRAGPipeline` run to return search_results and completion
    def run(self, query, filters={}, limit=10):
        """
        Runs the completion pipeline.
        """
        self.pipeline_run_id = uuid.uuid4()
        transformed_query = self.transform_query(query)
        search_results = self.search(
            transformed_query, filters, limit
        )
        context = self.construct_context(search_results)
        prompt = self.construct_prompt(
            {"query": transformed_query, "context": context}
        )
        completion = self.generate_completion(
            prompt, transformed_query, context
        )
        return search_results, completion


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
    pipeline = DemoRAGPipeline(
        llm,
        generation_config,
        logging_database,
        db=db,
        embedding_model=embedding_model,
        embeddings_provider=embeddings_provider,
    )

    search_results, completion = pipeline.run(query)

    for result in search_results:
        logger.info("-" * 100)
        logger.info(f"Search Result:\n{result}")
    logger.info("-" * 100)
    logger.info(f"Final Result:\n{completion}")
    logger.info("-" * 100)

    pipeline.close()
