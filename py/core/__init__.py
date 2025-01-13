import logging

# Keep '*' imports for enhanced development velocity
from .agent import *
from .base import *
from .database import *
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
    "FUSEAgent",
    "FUSEStreamingAgent",
    # RAG Agents
    "FUSERAGAgent",
    "FUSEStreamingRAGAgent",
    ## BASE
    # Base abstractions
    "AsyncSyncMeta",
    "syncable",
    # Completion abstractions
    "MessageType",
    # Document abstractions
    "Document",
    "DocumentChunk",
    "DocumentResponse",
    "IngestionStatus",
    "KGExtractionStatus",
    "KGEnrichmentStatus",
    "DocumentType",
    # Embedding abstractions
    "EmbeddingPurpose",
    "default_embedding_prefixes",
    # Exception abstractions
    "FUSEDocumentProcessingError",
    "FUSEException",
    # KG abstractions
    "Entity",
    "KGExtraction",
    "Relationship",
    # LLM abstractions
    "GenerationConfig",
    "LLMChatCompletion",
    "LLMChatCompletionChunk",
    "RAGCompletion",
    # Prompt abstractions
    "Prompt",
    # Search abstractions
    "AggregateSearchResult",
    "WebSearchResponse",
    "GraphSearchResult",
    "ChunkSearchSettings",
    "GraphSearchSettings",
    "ChunkSearchResult",
    "SearchSettings",
    "select_search_filters",
    "SearchMode",
    "HybridSearchSettings",
    # User abstractions
    "Token",
    "TokenData",
    # Vector abstractions
    "Vector",
    "VectorEntry",
    "VectorType",
    "IndexConfig",
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
    "TokenResponse",
    "User",
    ## LOGGING
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
    # Email provider
    "EmailConfig",
    "EmailProvider",
    # Database providers
    "LimitSettings",
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
    "generate_id",
    "increment_version",
    "validate_uuid",
    ## MAIN
    ## FUSE ABSTRACTIONS
    "FUSEProviders",
    "FUSEPipes",
    "FUSEPipelines",
    "FUSEAgents",
    ## FUSE APP
    "FUSEApp",
    ## FUSE APP ENTRY
    # "fuse_app",
    ## FUSE ASSEMBLY
    # Builder
    "FUSEBuilder",
    # Config
    "FUSEConfig",
    # Factory
    "FUSEProviderFactory",
    "FUSEPipeFactory",
    "FUSEPipelineFactory",
    "FUSEAgentFactory",
    ## FUSE SERVICES
    "AuthService",
    "IngestionService",
    "ManagementService",
    "RetrievalService",
    "GraphService",
    ## PARSERS
    # Media parsers
    "AudioParser",
    "BMPParser",
    "DOCParser",
    "DOCXParser",
    "ImageParser",
    "ODTParser",
    "VLMPDFParser",
    "BasicPDFParser",
    "PDFParserUnstructured",
    "PPTParser",
    "PPTXParser",
    "RTFParser",
    # Structured parsers
    "CSVParser",
    "CSVParserAdvanced",
    "EMLParser",
    "EPUBParser",
    "JSONParser",
    "MSGParser",
    "ORGParser",
    "P7SParser",
    "RSTParser",
    "TIFFParser",
    "TSVParser",
    "XLSParser",
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
    "ParsingPipe",
    "QueryTransformPipe",
    "RAGPipe",
    "StreamingRAGPipe",
    "VectorSearchPipe",
    "VectorStoragePipe",
    "GraphStoragePipe",
    "MultiSearchPipe",
    ## PROVIDERS
    # Auth
    "SupabaseAuthProvider",
    "FUSEAuthProvider",
    # Crypto
    "BCryptCryptoProvider",
    "BcryptCryptoConfig",
    "NaClCryptoConfig",
    "NaClCryptoProvider",
    # Database
    "PostgresDatabaseProvider",
    # Embeddings
    "LiteLLMEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "OllamaEmbeddingProvider",
    # LLM
    "OpenAICompletionProvider",
    "LiteLLMCompletionProvider",
    # Ingestion
    "UnstructuredIngestionProvider",
    "FUSEIngestionProvider",
    "ChunkingStrategy",
]
