import logging

import dotenv
import uvicorn
from langchain.text_splitter import RecursiveCharacterTextSplitter

from sciphi_r2r.core import GenerationConfig, LoggingDatabaseConnection
from sciphi_r2r.datasets import HuggingFaceDataProvider
from sciphi_r2r.embeddings import OpenAIEmbeddingProvider
from sciphi_r2r.llms import OpenAIConfig, OpenAILLM
from sciphi_r2r.main import create_app
from sciphi_r2r.pipelines import (
    BasicRAGPipeline,
    BasicEmbeddingPipeline,
)
from sciphi_r2r.vector_dbs import PGVectorDB

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

    all_logging = LoggingDatabaseConnection("basic_app_logs_v1")

    cmpl_pipeline = BasicRAGPipeline(
        llm,
        generation_config,
        db=db,
        embedding_model=embedding_model,
        embeddings_provider=embeddings_provider,
        logging_database=all_logging,
    )

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=20,
        length_function=len,
        is_separator_regex=False,
    )
    dataset_provider = HuggingFaceDataProvider()

    embd_pipeline = BasicEmbeddingPipeline(
        dataset_provider,
        embedding_model,
        embeddings_provider,
        db,
        logging_database=all_logging,
        text_splitter=text_splitter,
    )

    app = create_app(
        embedding_pipeline=embd_pipeline, rag_pipeline=cmpl_pipeline
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)
