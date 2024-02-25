"""A simple example to demonstrate the usage of `BasicEmbeddingPipeline`."""
import logging

import dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter

from r2r.llms import OpenAIConfig, OpenAILLM
from r2r.core import GenerationConfig, LoggingDatabaseConnection
from r2r.embeddings import ModalEmbeddingProvider
from r2r.main import load_config
from r2r.main.app import create_app
from r2r.pipelines import BasicEmbeddingPipeline
from r2r.vector_dbs import PGVectorDB
from r2r.pipelines import (
    BasicEmbeddingPipeline,
    BasicIngestionPipeline,
    BasicRAGPipeline,
)
import pprint

dotenv.load_dotenv()

(
    api_config,
    logging_config,
    embedding_config,
    database_config,
    language_model_config,
    text_splitter_config,
) = load_config()

pprint.pprint(embedding_config)

logger = logging.getLogger(logging_config["name"])
logging.basicConfig(level=logging_config["level"])

logger.info("Starting the embedding pipeline")
embedding_model = embedding_config["model"]
embedding_dimension = embedding_config["dimension"]
embedding_batch_size = embedding_config["batch_size"]

# Specify the embedding provider
embeddings_provider = ModalEmbeddingProvider(
    'embedding-all-MiniLM-L6-v2',
    'Model',
    embedding_dimension,
    embedding_batch_size
)

# Specify the vector database provider
db = PGVectorDB()
collection_name = database_config["collection_name"]
db.initialize_collection(collection_name, embedding_dimension)

# Specify the chunking strategy
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=text_splitter_config["chunk_size"],
    chunk_overlap=text_splitter_config["chunk_overlap"],
    length_function=len,
    is_separator_regex=False,
)

logging_database = LoggingDatabaseConnection(logging_config["database"])

embd_pipeline = BasicEmbeddingPipeline(
    embedding_model,
    embeddings_provider,
    db,
    text_splitter=text_splitter,
    embedding_batch_size=embedding_batch_size,
    logging_database=logging_database,
)

ingst_pipeline = BasicIngestionPipeline()

llm = OpenAILLM(OpenAIConfig())
generation_config = GenerationConfig(
    model_name=language_model_config["model_name"],
    temperature=language_model_config["temperature"],
    top_p=language_model_config["top_p"],
    top_k=language_model_config["top_k"],
    max_tokens_to_sample=language_model_config["max_tokens_to_sample"],
    do_stream=language_model_config["do_stream"],
)

cmpl_pipeline = BasicRAGPipeline(
    llm,
    generation_config,
    db=db,
    embedding_model=embedding_model,
    embeddings_provider=embeddings_provider,
    logging_database=logging_database,
)

app = create_app(
    ingestion_pipeline=ingst_pipeline,
    embedding_pipeline=embd_pipeline,
    rag_pipeline=cmpl_pipeline,
    logging_database=logging_database,
)
