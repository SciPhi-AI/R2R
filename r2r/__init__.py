import logging

# Keep '*' imports for enhanced development velocity
# corresponding flake8 error codes are F403, F405
from .core import *
from .integrations import *
from .main import *
from .pipes import *
from .prebuilts import *
from .prompts import *

logger = logging.getLogger("r2r")
logger.setLevel(logging.INFO)

# Create a console handler and set the level to info
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Create a formatter and set it for the handler
formatter = logging.Formatter(
    "%(name)s - %(levelname)s - %(message)s - %(asctime)s"
)
ch.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(ch)

# Optional: Prevent propagation to the root logger
logger.propagate = False

__all__ = [
    "LoggingConfig",
    "LocalKVLoggingProvider",
    "PostgresLoggingConfig",
    "PostgresKVLoggingProvider",
    "RedisLoggingConfig",
    "RedisKVLoggingProvider",
    "KVLoggingSingleton",
    "VectorEntry",
    "VectorType",
    "Vector",
    "VectorSearchRequest",
    "VectorSearchResult",
    "AsyncPipe",
    "PipeType",
    "AsyncState",
    "Prompt",
    "DataType",
    "DocumentType",
    "Document",
    "Extraction",
    "ExtractionType",
    "Fragment",
    "FragmentType",
    "SearchPipe",
    # Parsers
    "AsyncParser",
    "CSVParser",
    "DOCXParser",
    "HTMLParser",
    "JSONParser",
    "MarkdownParser",
    "PDFParser",
    "PPTParser",
    "TextParser",
    "XLSXParser",
    "Pipeline",
    # Providers
    "EmbeddingConfig",
    "EmbeddingProvider",
    "EvalConfig",
    "EvalProvider",
    "LLMEvalProvider",
    "PromptConfig",
    "PromptProvider",
    "GenerationConfig",
    "LLMChatCompletion",
    "LLMChatCompletionChunk",
    "LLMConfig",
    "LLMProvider",
    "VectorDBConfig",
    "VectorDBProvider",
    "R2RConfig",
    "TextSplitter",
    "RecursiveCharacterTextSplitter",
    "generate_run_id",
    "generate_id_from_label",
    "R2RApp",
    # Pipes
    "EmbeddingPipe",
    "EvalPipe",
    "ParsingPipe",
    "QueryTransformPipe",
    "SearchRAGPipe",
    "StreamingSearchRAGPipe",
    "VectorSearchPipe",
    "VectorStoragePipe",
    "R2RPromptProvider",
    "WebSearchPipe",
    "R2RAppBuilder",
    "KGAgentSearchPipe",
    # Prebuilts
    "MultiSearchPipe",
    "R2RPipeFactoryWithMultiSearch",
    # Integrations
    "SerperClient",
]
