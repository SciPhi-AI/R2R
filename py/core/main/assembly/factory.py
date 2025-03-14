import logging
import math
import os
from typing import Any, Optional

from core.base import (
    AuthConfig,
    CompletionConfig,
    CompletionProvider,
    CryptoConfig,
    DatabaseConfig,
    EmailConfig,
    EmbeddingConfig,
    EmbeddingProvider,
    IngestionConfig,
    OrchestrationConfig,
)
from core.providers import (
    AnthropicCompletionProvider,
    AsyncSMTPEmailProvider,
    BcryptCryptoConfig,
    BCryptCryptoProvider,
    ConsoleMockEmailProvider,
    HatchetOrchestrationProvider,
    JwtAuthProvider,
    LiteLLMCompletionProvider,
    LiteLLMEmbeddingProvider,
    MailerSendEmailProvider,
    NaClCryptoConfig,
    NaClCryptoProvider,
    OllamaEmbeddingProvider,
    OpenAICompletionProvider,
    OpenAIEmbeddingProvider,
    PostgresDatabaseProvider,
    R2RAuthProvider,
    R2RCompletionProvider,
    R2RIngestionConfig,
    R2RIngestionProvider,
    SendGridEmailProvider,
    SimpleOrchestrationProvider,
    SupabaseAuthProvider,
    UnstructuredIngestionConfig,
    UnstructuredIngestionProvider,
)

from ..abstractions import R2RProviders
from ..config import R2RConfig

logger = logging.getLogger()


class R2RProviderFactory:
    def __init__(self, config: R2RConfig):
        self.config = config

    @staticmethod
    async def create_auth_provider(
        auth_config: AuthConfig,
        crypto_provider: BCryptCryptoProvider | NaClCryptoProvider,
        database_provider: PostgresDatabaseProvider,
        email_provider: (
            AsyncSMTPEmailProvider
            | ConsoleMockEmailProvider
            | SendGridEmailProvider
            | MailerSendEmailProvider
        ),
        *args,
        **kwargs,
    ) -> R2RAuthProvider | SupabaseAuthProvider | JwtAuthProvider:
        if auth_config.provider == "r2r":
            r2r_auth = R2RAuthProvider(
                auth_config, crypto_provider, database_provider, email_provider
            )
            await r2r_auth.initialize()
            return r2r_auth
        elif auth_config.provider == "supabase":
            return SupabaseAuthProvider(
                auth_config, crypto_provider, database_provider, email_provider
            )
        elif auth_config.provider == "jwt":
            return JwtAuthProvider(
                auth_config, crypto_provider, database_provider, email_provider
            )
        else:
            raise ValueError(
                f"Auth provider {auth_config.provider} not supported."
            )

    @staticmethod
    def create_crypto_provider(
        crypto_config: CryptoConfig, *args, **kwargs
    ) -> BCryptCryptoProvider | NaClCryptoProvider:
        if crypto_config.provider == "bcrypt":
            return BCryptCryptoProvider(
                BcryptCryptoConfig(**crypto_config.model_dump())
            )
        if crypto_config.provider == "nacl":
            return NaClCryptoProvider(
                NaClCryptoConfig(**crypto_config.model_dump())
            )
        else:
            raise ValueError(
                f"Crypto provider {crypto_config.provider} not supported."
            )

    @staticmethod
    def create_ingestion_provider(
        ingestion_config: IngestionConfig,
        database_provider: PostgresDatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        *args,
        **kwargs,
    ) -> R2RIngestionProvider | UnstructuredIngestionProvider:
        config_dict = (
            ingestion_config.model_dump()
            if isinstance(ingestion_config, IngestionConfig)
            else ingestion_config
        )

        extra_fields = config_dict.pop("extra_fields", {})

        if config_dict["provider"] == "r2r":
            r2r_ingestion_config = R2RIngestionConfig(
                **config_dict, **extra_fields
            )
            return R2RIngestionProvider(
                r2r_ingestion_config, database_provider, llm_provider
            )
        elif config_dict["provider"] in [
            "unstructured_local",
            "unstructured_api",
        ]:
            unstructured_ingestion_config = UnstructuredIngestionConfig(
                **config_dict, **extra_fields
            )

            return UnstructuredIngestionProvider(
                unstructured_ingestion_config, database_provider, llm_provider
            )
        else:
            raise ValueError(
                f"Ingestion provider {ingestion_config.provider} not supported"
            )

    @staticmethod
    def create_orchestration_provider(
        config: OrchestrationConfig, *args, **kwargs
    ) -> HatchetOrchestrationProvider | SimpleOrchestrationProvider:
        if config.provider == "hatchet":
            orchestration_provider = HatchetOrchestrationProvider(config)
            orchestration_provider.get_worker("r2r-worker")
            return orchestration_provider
        elif config.provider == "simple":
            from core.providers import SimpleOrchestrationProvider

            return SimpleOrchestrationProvider(config)
        else:
            raise ValueError(
                f"Orchestration provider {config.provider} not supported"
            )

    async def create_database_provider(
        self,
        db_config: DatabaseConfig,
        crypto_provider: BCryptCryptoProvider | NaClCryptoProvider,
        *args,
        **kwargs,
    ) -> PostgresDatabaseProvider:
        if not self.config.embedding.base_dimension:
            raise ValueError(
                "Embedding config must have a base dimension to initialize database."
            )

        dimension = self.config.embedding.base_dimension
        quantization_type = (
            self.config.embedding.quantization_settings.quantization_type
        )
        if db_config.provider == "postgres":
            database_provider = PostgresDatabaseProvider(
                db_config,
                dimension,
                crypto_provider=crypto_provider,
                quantization_type=quantization_type,
            )
            await database_provider.initialize()
            return database_provider
        else:
            raise ValueError(
                f"Database provider {db_config.provider} not supported"
            )

    @staticmethod
    def create_embedding_provider(
        embedding: EmbeddingConfig, *args, **kwargs
    ) -> (
        LiteLLMEmbeddingProvider
        | OllamaEmbeddingProvider
        | OpenAIEmbeddingProvider
    ):
        embedding_provider: Optional[EmbeddingProvider] = None

        if embedding.provider == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError(
                    "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
                )
            from core.providers import OpenAIEmbeddingProvider

            embedding_provider = OpenAIEmbeddingProvider(embedding)

        elif embedding.provider == "litellm":
            from core.providers import LiteLLMEmbeddingProvider

            embedding_provider = LiteLLMEmbeddingProvider(embedding)

        elif embedding.provider == "ollama":
            from core.providers import OllamaEmbeddingProvider

            embedding_provider = OllamaEmbeddingProvider(embedding)

        else:
            raise ValueError(
                f"Embedding provider {embedding.provider} not supported"
            )

        return embedding_provider

    @staticmethod
    def create_llm_provider(
        llm_config: CompletionConfig, *args, **kwargs
    ) -> (
        AnthropicCompletionProvider
        | LiteLLMCompletionProvider
        | OpenAICompletionProvider
        | R2RCompletionProvider
    ):
        llm_provider: Optional[CompletionProvider] = None
        if llm_config.provider == "anthropic":
            llm_provider = AnthropicCompletionProvider(llm_config)
        elif llm_config.provider == "litellm":
            llm_provider = LiteLLMCompletionProvider(llm_config)
        elif llm_config.provider == "openai":
            llm_provider = OpenAICompletionProvider(llm_config)
        elif llm_config.provider == "r2r":
            llm_provider = R2RCompletionProvider(llm_config)
        else:
            raise ValueError(
                f"Language model provider {llm_config.provider} not supported"
            )
        if not llm_provider:
            raise ValueError("Language model provider not found")
        return llm_provider

    @staticmethod
    async def create_email_provider(
        email_config: Optional[EmailConfig] = None, *args, **kwargs
    ) -> (
        AsyncSMTPEmailProvider
        | ConsoleMockEmailProvider
        | SendGridEmailProvider
        | MailerSendEmailProvider
    ):
        """Creates an email provider based on configuration."""
        if not email_config:
            raise ValueError(
                "No email configuration provided for email provider, please add `[email]` to your `r2r.toml`."
            )

        if email_config.provider == "smtp":
            return AsyncSMTPEmailProvider(email_config)
        elif email_config.provider == "console_mock":
            return ConsoleMockEmailProvider(email_config)
        elif email_config.provider == "sendgrid":
            return SendGridEmailProvider(email_config)
        elif email_config.provider == "mailersend":
            return MailerSendEmailProvider(email_config)
        else:
            raise ValueError(
                f"Email provider {email_config.provider} not supported."
            )

    async def create_providers(
        self,
        auth_provider_override: Optional[
            R2RAuthProvider | SupabaseAuthProvider
        ] = None,
        crypto_provider_override: Optional[
            BCryptCryptoProvider | NaClCryptoProvider
        ] = None,
        database_provider_override: Optional[PostgresDatabaseProvider] = None,
        email_provider_override: Optional[
            AsyncSMTPEmailProvider
            | ConsoleMockEmailProvider
            | SendGridEmailProvider
            | MailerSendEmailProvider
        ] = None,
        embedding_provider_override: Optional[
            LiteLLMEmbeddingProvider
            | OpenAIEmbeddingProvider
            | OllamaEmbeddingProvider
        ] = None,
        ingestion_provider_override: Optional[
            R2RIngestionProvider | UnstructuredIngestionProvider
        ] = None,
        llm_provider_override: Optional[
            AnthropicCompletionProvider
            | OpenAICompletionProvider
            | LiteLLMCompletionProvider
            | R2RCompletionProvider
        ] = None,
        orchestration_provider_override: Optional[Any] = None,
        *args,
        **kwargs,
    ) -> R2RProviders:
        if (
            math.isnan(self.config.embedding.base_dimension)
            != math.isnan(self.config.completion_embedding.base_dimension)
        ) or (
            not math.isnan(self.config.embedding.base_dimension)
            and not math.isnan(self.config.completion_embedding.base_dimension)
            and self.config.embedding.base_dimension
            != self.config.completion_embedding.base_dimension
        ):
            raise ValueError(
                f"Both embedding configurations must use the same dimensions. Got {self.config.embedding.base_dimension} and {self.config.completion_embedding.base_dimension}"
            )

        embedding_provider = (
            embedding_provider_override
            or self.create_embedding_provider(
                self.config.embedding, *args, **kwargs
            )
        )

        completion_embedding_provider = (
            embedding_provider_override
            or self.create_embedding_provider(
                self.config.completion_embedding, *args, **kwargs
            )
        )

        llm_provider = llm_provider_override or self.create_llm_provider(
            self.config.completion, *args, **kwargs
        )

        crypto_provider = (
            crypto_provider_override
            or self.create_crypto_provider(self.config.crypto, *args, **kwargs)
        )

        database_provider = (
            database_provider_override
            or await self.create_database_provider(
                self.config.database, crypto_provider, *args, **kwargs
            )
        )

        ingestion_provider = (
            ingestion_provider_override
            or self.create_ingestion_provider(
                self.config.ingestion,
                database_provider,
                llm_provider,
                *args,
                **kwargs,
            )
        )

        email_provider = (
            email_provider_override
            or await self.create_email_provider(
                self.config.email, crypto_provider, *args, **kwargs
            )
        )

        auth_provider = (
            auth_provider_override
            or await self.create_auth_provider(
                self.config.auth,
                crypto_provider,
                database_provider,
                email_provider,
                *args,
                **kwargs,
            )
        )

        orchestration_provider = (
            orchestration_provider_override
            or self.create_orchestration_provider(self.config.orchestration)
        )

        return R2RProviders(
            auth=auth_provider,
            database=database_provider,
            embedding=embedding_provider,
            completion_embedding=completion_embedding_provider,
            ingestion=ingestion_provider,
            llm=llm_provider,
            email=email_provider,
            orchestration=orchestration_provider,
        )
