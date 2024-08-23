import logging

# Keep '*' imports for enhanced development velocity
# corresponding flake8 error codes are F403, F405
from .agent import *
from .base import *
from .integrations import *
from .main import *
from .parsers import *
from .pipelines import *
from .pipes import *
from .providers import *

logger = logging.getLogger("core")
logger.setLevel(logging.INFO)

# Create a console handler and set the level to info
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Create a formatter and set it for the handler
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
ch.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(ch)

# Optional: Prevent propagation to the root logger
logger.propagate = False


__all__ = [
    ## AGENT
    # Base
    "R2RAgent",
    "R2RStreamingAgent",
    # RAG Agents
    "R2RRAGAgent",
    "R2RStreamingRAGAgent",
    ## BASE
    # Base abstractions
    "AsyncSyncMeta",
    "syncable",
    # Completion abstractions
    "CompletionRecord",
    "MessageType",
    # Document abstractions
    "DataType",
    "Document",
    "DocumentExtraction",
    "DocumentFragment",
    "DocumentInfo",
    "DocumentStatus",
    "DocumentType",
    # Embedding abstractions
    "EmbeddingPurpose",
    "default_embedding_prefixes",
    # Exception abstractions
    "R2RDocumentProcessingError",
    "R2RException",
    # KG abstractions
    "Entity",
    "KGExtraction",
    "Triple",
    # LLM abstractions
    "GenerationConfig",
    "LLMChatCompletion",
    "LLMChatCompletionChunk",
    "RAGCompletion",
    # Prompt abstractions
    "Prompt",
    # Search abstractions
    "AggregateSearchResult",
    "KGLocalSearchResult",
    "KGGlobalSearchResult",
    "KGSearchResult",
    "KGSearchSettings",
    "VectorSearchResult",
    "VectorSearchSettings",
    # User abstractions
    "Token",
    "TokenData",
    "UserStats",
    # Vector abstractions
    "Vector",
    "VectorEntry",
    "VectorType",
    ## AGENT
    # Agent abstractions
    "Agent",
    "AgentConfig",
    "Conversation",
    "Message",
    "Tool",
    "ToolResult",
    ## API
    # Auth Responses
    "GenericMessageResponse",
    "TokenResponse",
    "UserResponse",
    ## LOGGING
    # Basic types
    "RunType",
    "AnalysisTypes",
    "LogAnalytics",
    "LogAnalyticsConfig",
    "LogFilterCriteria",
    "LogProcessor",
    # Logging Providers
    "LocalRunLoggingProvider",
    "LoggingConfig",
    "PostgresLoggingConfig",
    "PostgresRunLoggingProvider",
    "RedisLoggingConfig",
    "RedisRunLoggingProvider",
    "RunLoggingSingleton",
    # Run Manager
    "RunManager",
    "manage_run",
    ## PARSERS
    # Base parser
    "AsyncParser",
    ## PIPELINE
    # Base pipeline
    "AsyncPipeline",
    ## PIPES
    "AsyncPipe",
    "AsyncState",
    "PipeType",
    ## PROVIDERS
    # Base provider classes
    "Provider",
    "ProviderConfig",
    # Auth provider
    "AuthConfig",
    "AuthProvider",
    # Chunking provider
    "ChunkingConfig",
    "ChunkingProvider",
    "Method",
    # Crypto provider
    "CryptoConfig",
    "CryptoProvider",
    # Database providers
    "DatabaseConfig",
    "DatabaseProvider",
    "RelationalDBProvider",
    "VectorDBProvider",
    # Embedding provider
    "EmbeddingConfig",
    "EmbeddingProvider",
    # Knowledge Graph provider
    "KGConfig",
    "KGProvider",
    # LLM provider
    "CompletionConfig",
    "CompletionProvider",
    # Parsing provider
    "ParsingConfig",
    "ParsingProvider",
    "OverrideParser",
    # Prompt provider
    "PromptConfig",
    "PromptProvider",
    ## UTILS
    "RecursiveCharacterTextSplitter",
    "TextSplitter",
    "run_pipeline",
    "to_async_generator",
    "generate_run_id",
    "generate_id_from_label",
    "increment_version",
    "EntityType",
    "RelationshipType",
    "format_entity_types",
    "format_relations",
    ## INTEGRATIONS
    # Serper
    "SerperClient",
    ## MAIN
    ## R2R ABSTRACTIONS
    "R2RProviders",
    "R2RPipes",
    "R2RPipelines",
    "R2RAgents",
    ## R2R API
    # Routes
    "AuthRouter",
    "IngestionRouter",
    "ManagementRouter",
    "RetrievalRouter",
    "BaseRouter",
    ## R2R APP
    "R2RApp",
    ## R2R APP ENTRY
    # "r2r_app",
    ## R2R ENGINE
    "R2REngine",
    ## R2R ASSEMBLY
    # Builder
    "R2RBuilder",
    # Config
    "R2RConfig",
    # Factory
    "R2RProviderFactory",
    "R2RPipeFactory",
    "R2RPipelineFactory",
    "R2RAgentFactory",
    # Factory Extensions
    "R2RPipeFactoryWithMultiSearch",
    ## R2R
    "R2R",
    ## R2R SERVICES
    "AuthService",
    "IngestionService",
    "ManagementService",
    "RetrievalService",
    ## PARSERS
    # Media parsers
    "AudioParser",
    "DOCXParser",
    "ImageParser",
    "MovieParser",
    "PDFParser",
    "PDFParserUnstructured",
    "PDFParserMarker",
    "PPTParser",
    # Structured parsers
    "CSVParser",
    "CSVParserAdvanced",
    "JSONParser",
    "XLSXParser",
    "XLSXParserAdvanced",
    # Text parsers
    "MDParser",
    "HTMLParser",
    "TextParser",
    ## PIPELINES
    "IngestionPipeline",
    "SearchPipeline",
    "RAGPipeline",
    ## PIPES
    "SearchPipe",
    "EmbeddingPipe",
    "KGTriplesExtractionPipe",
    "ParsingPipe",
    "ChunkingPipe",
    "QueryTransformPipe",
    "SearchRAGPipe",
    "StreamingSearchRAGPipe",
    "VectorSearchPipe",
    "VectorStoragePipe",
    "WebSearchPipe",
    "KGSearchSearchPipe",
    "KGStoragePipe",
    "MultiSearchPipe",
    ## PROVIDERS
    # Auth
    "R2RAuthProvider",
    # Chunking
    "R2RChunkingProvider",
    "UnstructuredChunkingProvider",
    # Crypto
    "BCryptProvider",
    "BCryptConfig",
    # Database
    "PostgresDBProvider",
    # Embeddings
    "LiteLLMEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    # KG
    "Neo4jKGProvider",
    # LLM
    "OpenAICompletionProvider",
    "LiteCompletionProvider",
    # Parsing
    "R2RParsingProvider",
    "UnstructuredParsingProvider",
    # Prompts
    "R2RPromptProvider",
]
