import logging

# Keep '*' imports for enhanced development velocity
# corresponding flake8 error codes are F403, F405
from .agent import *
from .base import *
from .main import *
from .parsers import *
from .pipelines import *
from .pipes import *
from .providers import *

logger = logging.getLogger()
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

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)


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
    "MessageType",
    # Document abstractions
    "DataType",
    "Document",
    "DocumentExtraction",
    "DocumentInfo",
    "IngestionStatus",
    "KGExtractionStatus",
    "KGEnrichmentStatus",
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
    "KGSearchResult",
    "KGSearchSettings",
    "VectorSearchResult",
    "VectorSearchSettings",
    "HybridSearchSettings",
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
    "PersistentLoggingConfig",
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
    ## PROVIDERS
    # Base provider classes
    "AppConfig",
    "Provider",
    "ProviderConfig",
    # Auth provider
    "AuthConfig",
    "AuthProvider",
    # Crypto provider
    "CryptoConfig",
    "CryptoProvider",
    # Database providers
    "DatabaseConfig",
    "DatabaseProvider",
    # Embedding provider
    "EmbeddingConfig",
    "EmbeddingProvider",
    # LLM provider
    "CompletionConfig",
    "CompletionProvider",
    ## UTILS
    "RecursiveCharacterTextSplitter",
    "TextSplitter",
    "run_pipeline",
    "to_async_generator",
    "generate_run_id",
    "increment_version",
    "EntityType",
    "RelationshipType",
    "format_entity_types",
    "format_relations",
    "validate_uuid",
    ## MAIN
    ## R2R ABSTRACTIONS
    "R2RProviders",
    "R2RPipes",
    "R2RPipelines",
    "R2RAgents",
    ## R2R APP
    "R2RApp",
    ## R2R APP ENTRY
    # "r2r_app",
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
    # R2R Routers
    "AuthRouter",
    "IngestionRouter",
    "ManagementRouter",
    "RetrievalRouter",
    "KGRouter",
    ## R2R SERVICES
    "AuthService",
    "IngestionService",
    "ManagementService",
    "RetrievalService",
    "KgService",
    ## PARSERS
    # Media parsers
    "AudioParser",
    "DOCXParser",
    "ImageParser",
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
    "SearchPipeline",
    "RAGPipeline",
    ## PIPES
    "SearchPipe",
    "EmbeddingPipe",
    "KGTriplesExtractionPipe",
    "ParsingPipe",
    "QueryTransformPipe",
    "SearchRAGPipe",
    "StreamingSearchRAGPipe",
    "VectorSearchPipe",
    "VectorStoragePipe",
    "KGStoragePipe",
    "MultiSearchPipe",
    ## PROVIDERS
    # Auth
    "SupabaseAuthProvider",
    "R2RAuthProvider",
    # Crypto
    "BCryptProvider",
    "BCryptConfig",
    # Database
    "PostgresDBProvider",
    # Embeddings
    "LiteLLMEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    # LLM
    "OpenAICompletionProvider",
    "LiteLLMCompletionProvider",
    # Ingestion
    "UnstructuredIngestionProvider",
    "R2RIngestionProvider",
    "ChunkingStrategy",
]
