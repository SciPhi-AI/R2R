from .auth import R2RAuthProvider, SupabaseAuthProvider
from .crypto import (
    BcryptCryptoConfig,
    BCryptCryptoProvider,
    NaClCryptoConfig,
    NaClCryptoProvider,
)
from .email import (
    AsyncSMTPEmailProvider,
    ConsoleMockEmailProvider,
    SendGridEmailProvider,
)
from .embeddings import (
    LiteLLMEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from .ingestion import (  # type: ignore
    R2RIngestionConfig,
    R2RIngestionProvider,
    UnstructuredIngestionConfig,
    UnstructuredIngestionProvider,
)
from .llm import LiteLLMCompletionProvider, OpenAICompletionProvider
from .orchestration import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

__all__ = [
    # Auth
    "R2RAuthProvider",
    "SupabaseAuthProvider",
    # Ingestion
    "R2RIngestionProvider",
    "R2RIngestionConfig",
    "UnstructuredIngestionProvider",
    "UnstructuredIngestionConfig",
    # Crypto
    "BCryptCryptoProvider",
    "BcryptCryptoConfig",
    "NaClCryptoConfig",
    "NaClCryptoProvider",
    # Embeddings
    "LiteLLMEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    # Email
    "AsyncSMTPEmailProvider",
    "ConsoleMockEmailProvider",
    "SendGridEmailProvider",
    # Orchestration
    "HatchetOrchestrationProvider",
    "SimpleOrchestrationProvider",
    # LLM
    "OpenAICompletionProvider",
    "LiteLLMCompletionProvider",
]
