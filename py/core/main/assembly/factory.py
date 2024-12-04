import logging
import os
from typing import Any, Optional, Union

from core.agent import R2RRAGAgent, R2RStreamingRAGAgent
from core.base import (
    AsyncPipe,
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
from core.pipelines import RAGPipeline, SearchPipeline
from core.pipes import GeneratorPipe, MultiSearchPipe, SearchPipe
from core.providers.email.sendgrid import SendGridEmailProvider
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig

logger = logging.getLogger()
from core.providers import (
    AsyncSMTPEmailProvider,
    BCryptConfig,
    BCryptProvider,
    ConsoleMockEmailProvider,
    HatchetOrchestrationProvider,
    LiteLLMCompletionProvider,
    LiteLLMEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAICompletionProvider,
    OpenAIEmbeddingProvider,
    PostgresDBProvider,
    R2RAuthProvider,
    R2RIngestionConfig,
    R2RIngestionProvider,
    SimpleOrchestrationProvider,
    SupabaseAuthProvider,
    UnstructuredIngestionConfig,
    UnstructuredIngestionProvider,
)


class R2RProviderFactory:
    def __init__(self, config: R2RConfig):
        self.config = config

    @staticmethod
    async def create_auth_provider(
        auth_config: AuthConfig,
        crypto_provider: BCryptProvider,
        database_provider: PostgresDBProvider,
        email_provider: Union[
            AsyncSMTPEmailProvider,
            ConsoleMockEmailProvider,
            SendGridEmailProvider,
        ],
        *args,
        **kwargs,
    ) -> Union[R2RAuthProvider, SupabaseAuthProvider]:
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
        else:
            raise ValueError(
                f"Auth provider {auth_config.provider} not supported."
            )

    @staticmethod
    def create_crypto_provider(
        crypto_config: CryptoConfig, *args, **kwargs
    ) -> BCryptProvider:
        if crypto_config.provider == "bcrypt":
            return BCryptProvider(BCryptConfig(**crypto_config.dict()))
        else:
            raise ValueError(
                f"Crypto provider {crypto_config.provider} not supported."
            )

    @staticmethod
    def create_ingestion_provider(
        ingestion_config: IngestionConfig,
        database_provider: PostgresDBProvider,
        llm_provider: Union[
            LiteLLMCompletionProvider, OpenAICompletionProvider
        ],
        *args,
        **kwargs,
    ) -> Union[R2RIngestionProvider, UnstructuredIngestionProvider]:

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
    ) -> Union[HatchetOrchestrationProvider, SimpleOrchestrationProvider]:
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
        crypto_provider: BCryptProvider,
        *args,
        **kwargs,
    ) -> PostgresDBProvider:
        if not self.config.embedding.base_dimension:
            raise ValueError(
                "Embedding config must have a base dimension to initialize database."
            )

        dimension = self.config.embedding.base_dimension
        quantization_type = (
            self.config.embedding.quantization_settings.quantization_type
        )
        if db_config.provider == "postgres":
            from core.providers import PostgresDBProvider

            database_provider = PostgresDBProvider(
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
    ) -> Union[
        LiteLLMEmbeddingProvider,
        OllamaEmbeddingProvider,
        OpenAIEmbeddingProvider,
    ]:
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
    ) -> Union[LiteLLMCompletionProvider, OpenAICompletionProvider]:
        llm_provider: Optional[CompletionProvider] = None
        if llm_config.provider == "openai":
            llm_provider = OpenAICompletionProvider(llm_config)
        elif llm_config.provider == "litellm":
            llm_provider = LiteLLMCompletionProvider(llm_config)
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
    ) -> Union[
        AsyncSMTPEmailProvider, ConsoleMockEmailProvider, SendGridEmailProvider
    ]:
        """Creates an email provider based on configuration."""
        if not email_config:
            raise ValueError(
                f"No email configuration provided for email provider, please add `[email]` to your `r2r.toml`."
            )

        if email_config.provider == "smtp":
            return AsyncSMTPEmailProvider(email_config)
        elif email_config.provider == "console_mock":
            return ConsoleMockEmailProvider(email_config)
        elif email_config.provider == "sendgrid":
            return SendGridEmailProvider(email_config)
        else:
            raise ValueError(
                f"Email provider {email_config.provider} not supported."
            )

    async def create_providers(
        self,
        auth_provider_override: Optional[
            Union[R2RAuthProvider, SupabaseAuthProvider]
        ] = None,
        crypto_provider_override: Optional[BCryptProvider] = None,
        database_provider_override: Optional[PostgresDBProvider] = None,
        email_provider_override: Optional[
            Union[
                AsyncSMTPEmailProvider,
                ConsoleMockEmailProvider,
                SendGridEmailProvider,
            ]
        ] = None,
        embedding_provider_override: Optional[
            Union[
                LiteLLMEmbeddingProvider,
                OpenAIEmbeddingProvider,
                OllamaEmbeddingProvider,
            ]
        ] = None,
        ingestion_provider_override: Optional[
            Union[R2RIngestionProvider, UnstructuredIngestionProvider]
        ] = None,
        llm_provider_override: Optional[
            Union[OpenAICompletionProvider, LiteLLMCompletionProvider]
        ] = None,
        orchestration_provider_override: Optional[Any] = None,
        r2r_logging_provider_override: Optional[
            SqlitePersistentLoggingProvider
        ] = None,
        *args,
        **kwargs,
    ) -> R2RProviders:
        embedding_provider = (
            embedding_provider_override
            or self.create_embedding_provider(
                self.config.embedding, *args, **kwargs
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

        logging_provider = (
            r2r_logging_provider_override
            or SqlitePersistentLoggingProvider(self.config.logging)
        )
        await logging_provider.initialize()

        return R2RProviders(
            auth=auth_provider,
            database=database_provider,
            embedding=embedding_provider,
            ingestion=ingestion_provider,
            llm=llm_provider,
            email=email_provider,
            orchestration=orchestration_provider,
            logging=logging_provider,
        )


class R2RPipeFactory:
    def __init__(self, config: R2RConfig, providers: R2RProviders):
        self.config = config
        self.providers = providers

    def create_pipes(
        self,
        parsing_pipe_override: Optional[AsyncPipe] = None,
        embedding_pipe_override: Optional[AsyncPipe] = None,
        kg_relationships_extraction_pipe_override: Optional[AsyncPipe] = None,
        kg_storage_pipe_override: Optional[AsyncPipe] = None,
        kg_search_pipe_override: Optional[AsyncPipe] = None,
        vector_storage_pipe_override: Optional[AsyncPipe] = None,
        vector_search_pipe_override: Optional[AsyncPipe] = None,
        rag_pipe_override: Optional[AsyncPipe] = None,
        streaming_rag_pipe_override: Optional[AsyncPipe] = None,
        kg_entity_description_pipe: Optional[AsyncPipe] = None,
        kg_clustering_pipe: Optional[AsyncPipe] = None,
        kg_entity_deduplication_pipe: Optional[AsyncPipe] = None,
        kg_entity_deduplication_summary_pipe: Optional[AsyncPipe] = None,
        kg_community_summary_pipe: Optional[AsyncPipe] = None,
        kg_prompt_tuning_pipe: Optional[AsyncPipe] = None,
        *args,
        **kwargs,
    ) -> R2RPipes:
        return R2RPipes(
            parsing_pipe=parsing_pipe_override
            or self.create_parsing_pipe(
                self.config.ingestion.excluded_parsers,
                *args,
                **kwargs,
            ),
            embedding_pipe=embedding_pipe_override
            or self.create_embedding_pipe(*args, **kwargs),
            kg_relationships_extraction_pipe=kg_relationships_extraction_pipe_override
            or self.create_kg_relationships_extraction_pipe(*args, **kwargs),
            kg_storage_pipe=kg_storage_pipe_override
            or self.create_kg_storage_pipe(*args, **kwargs),
            vector_storage_pipe=vector_storage_pipe_override
            or self.create_vector_storage_pipe(*args, **kwargs),
            vector_search_pipe=vector_search_pipe_override
            or self.create_vector_search_pipe(*args, **kwargs),
            kg_search_pipe=kg_search_pipe_override
            or self.create_kg_search_pipe(*args, **kwargs),
            rag_pipe=rag_pipe_override
            or self.create_rag_pipe(*args, **kwargs),
            streaming_rag_pipe=streaming_rag_pipe_override
            or self.create_rag_pipe(True, *args, **kwargs),
            kg_entity_description_pipe=kg_entity_description_pipe
            or self.create_kg_entity_description_pipe(*args, **kwargs),
            kg_clustering_pipe=kg_clustering_pipe
            or self.create_kg_clustering_pipe(*args, **kwargs),
            kg_entity_deduplication_pipe=kg_entity_deduplication_pipe
            or self.create_kg_entity_deduplication_pipe(*args, **kwargs),
            kg_entity_deduplication_summary_pipe=kg_entity_deduplication_summary_pipe
            or self.create_kg_entity_deduplication_summary_pipe(
                *args, **kwargs
            ),
            kg_community_summary_pipe=kg_community_summary_pipe
            or self.create_kg_community_summary_pipe(*args, **kwargs),
            kg_prompt_tuning_pipe=kg_prompt_tuning_pipe
            or self.create_kg_prompt_tuning_pipe(*args, **kwargs),
        )

    def create_parsing_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import ParsingPipe

        return ParsingPipe(
            logging_provider=self.providers.logging,
            ingestion_provider=self.providers.ingestion,
            database_provider=self.providers.database,
            config=AsyncPipe.PipeConfig(name="parsing_pipe"),
        )

    def create_embedding_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        from core.pipes import EmbeddingPipe

        return EmbeddingPipe(
            logging_provider=self.providers.logging,
            embedding_provider=self.providers.embedding,
            database_provider=self.providers.database,
            embedding_batch_size=self.config.embedding.batch_size,
            config=AsyncPipe.PipeConfig(name="embedding_pipe"),
        )

    def create_vector_storage_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        from core.pipes import VectorStoragePipe

        return VectorStoragePipe(
            logging_provider=self.providers.logging,
            database_provider=self.providers.database,
            config=AsyncPipe.PipeConfig(name="vector_storage_pipe"),
        )

    def create_default_vector_search_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        from core.pipes import VectorSearchPipe

        return VectorSearchPipe(
            logging_provider=self.providers.logging,
            database_provider=self.providers.database,
            embedding_provider=self.providers.embedding,
            config=SearchPipe.SearchConfig(name="vector_search_pipe"),
        )

    def create_multi_search_pipe(
        self,
        inner_search_pipe: SearchPipe,
        use_rrf: bool = False,
        expansion_technique: str = "hyde",
        expansion_factor: int = 3,
        *args,
        **kwargs,
    ) -> MultiSearchPipe:
        from core.pipes import QueryTransformPipe

        multi_search_config = MultiSearchPipe.PipeConfig(
            use_rrf=use_rrf, expansion_factor=expansion_factor
        )

        query_transform_pipe = QueryTransformPipe(
            logging_provider=self.providers.logging,
            llm_provider=self.providers.llm,
            database_provider=self.providers.database,
            config=QueryTransformPipe.QueryTransformConfig(
                name="multi_query_transform",
                task_prompt=expansion_technique,
            ),
        )

        return MultiSearchPipe(
            logging_provider=self.providers.logging,
            query_transform_pipe=query_transform_pipe,
            inner_search_pipe=inner_search_pipe,
            config=multi_search_config,
        )

    def create_vector_search_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        vanilla_vector_search_pipe = self.create_default_vector_search_pipe(
            *args, **kwargs
        )
        hyde_search_pipe = self.create_multi_search_pipe(
            vanilla_vector_search_pipe,
            False,
            "hyde",
            *args,
            **kwargs,
        )
        rag_fusion_pipe = self.create_multi_search_pipe(
            vanilla_vector_search_pipe,
            True,
            "rag_fusion",
            *args,
            **kwargs,
        )

        from core.pipes import RoutingSearchPipe

        return RoutingSearchPipe(
            logging_provider=self.providers.logging,
            search_pipes={
                "vanilla": vanilla_vector_search_pipe,
                "hyde": hyde_search_pipe,
                "rag_fusion": rag_fusion_pipe,
            },
            default_strategy="hyde",
            config=AsyncPipe.PipeConfig(name="routing_search_pipe"),
        )

    def create_kg_relationships_extraction_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGExtractionPipe

        return KGExtractionPipe(
            logging_provider=self.providers.logging,
            llm_provider=self.providers.llm,
            database_provider=self.providers.database,
            config=AsyncPipe.PipeConfig(
                name="kg_relationships_extraction_pipe"
            ),
        )

    def create_kg_storage_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGStoragePipe

        return KGStoragePipe(
            logging_provider=self.providers.logging,
            database_provider=self.providers.database,
            config=AsyncPipe.PipeConfig(name="kg_storage_pipe"),
        )

    def create_kg_search_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGSearchSearchPipe

        return KGSearchSearchPipe(
            logging_provider=self.providers.logging,
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            embedding_provider=self.providers.embedding,
            config=GeneratorPipe.PipeConfig(
                name="kg_rag_pipe", task_prompt="kg_search"
            ),
        )

    def create_rag_pipe(self, stream: bool = False, *args, **kwargs) -> Any:
        if stream:
            from core.pipes import StreamingSearchRAGPipe

            return StreamingSearchRAGPipe(
                logging_provider=self.providers.logging,
                llm_provider=self.providers.llm,
                database_provider=self.providers.database,
                config=GeneratorPipe.PipeConfig(
                    name="streaming_rag_pipe", task_prompt="default_rag"
                ),
            )
        else:
            from core.pipes import SearchRAGPipe

            return SearchRAGPipe(
                logging_provider=self.providers.logging,
                llm_provider=self.providers.llm,
                database_provider=self.providers.database,
                config=GeneratorPipe.PipeConfig(
                    name="search_rag_pipe", task_prompt="default_rag"
                ),
            )

    def create_kg_entity_description_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGEntityDescriptionPipe

        return KGEntityDescriptionPipe(
            logging_provider=self.providers.logging,
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(name="kg_entity_description_pipe"),
        )

    def create_kg_clustering_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGClusteringPipe

        return KGClusteringPipe(
            logging_provider=self.providers.logging,
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(name="kg_clustering_pipe"),
        )

    def create_kg_deduplication_summary_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGEntityDeduplicationSummaryPipe

        return KGEntityDeduplicationSummaryPipe(
            logging_provider=self.providers.logging,
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(name="kg_deduplication_summary_pipe"),
        )

    def create_kg_community_summary_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGCommunitySummaryPipe

        return KGCommunitySummaryPipe(
            logging_provider=self.providers.logging,
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(name="kg_community_summary_pipe"),
        )

    def create_kg_entity_deduplication_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGEntityDeduplicationPipe

        return KGEntityDeduplicationPipe(
            logging_provider=self.providers.logging,
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(name="kg_entity_deduplication_pipe"),
        )

    def create_kg_entity_deduplication_summary_pipe(
        self, *args, **kwargs
    ) -> Any:
        from core.pipes import KGEntityDeduplicationSummaryPipe

        return KGEntityDeduplicationSummaryPipe(
            logging_provider=self.providers.logging,
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(
                name="kg_entity_deduplication_summary_pipe"
            ),
        )

    def create_kg_prompt_tuning_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGPromptTuningPipe

        return KGPromptTuningPipe(
            logging_provider=self.providers.logging,
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            config=AsyncPipe.PipeConfig(name="kg_prompt_tuning_pipe"),
        )


class R2RPipelineFactory:
    def __init__(
        self, config: R2RConfig, providers: R2RProviders, pipes: R2RPipes
    ):
        self.config = config
        self.providers = providers
        self.pipes = pipes

    def create_search_pipeline(self, *args, **kwargs) -> SearchPipeline:
        """factory method to create an ingestion pipeline."""
        search_pipeline = SearchPipeline(
            logging_provider=self.providers.logging
        )

        # Add vector search pipes if embedding provider and vector provider is set
        if (
            self.config.embedding.provider is not None
            and self.config.database.provider is not None
        ):
            search_pipeline.add_pipe(
                self.pipes.vector_search_pipe, vector_search_pipe=True
            )
            search_pipeline.add_pipe(
                self.pipes.kg_search_pipe, kg_search_pipe=True
            )

        return search_pipeline

    def create_rag_pipeline(
        self,
        search_pipeline: SearchPipeline,
        stream: bool = False,
        *args,
        **kwargs,
    ) -> RAGPipeline:
        rag_pipe = (
            self.pipes.streaming_rag_pipe if stream else self.pipes.rag_pipe
        )

        rag_pipeline = RAGPipeline(logging_provider=self.providers.logging)
        rag_pipeline.set_search_pipeline(search_pipeline)
        rag_pipeline.add_pipe(rag_pipe)
        return rag_pipeline

    def create_pipelines(
        self,
        search_pipeline: Optional[SearchPipeline] = None,
        rag_pipeline: Optional[RAGPipeline] = None,
        streaming_rag_pipeline: Optional[RAGPipeline] = None,
        *args,
        **kwargs,
    ) -> R2RPipelines:
        search_pipeline = search_pipeline or self.create_search_pipeline(
            *args, **kwargs
        )
        return R2RPipelines(
            search_pipeline=search_pipeline,
            rag_pipeline=rag_pipeline
            or self.create_rag_pipeline(
                search_pipeline,
                False,
                *args,
                **kwargs,
            ),
            streaming_rag_pipeline=streaming_rag_pipeline
            or self.create_rag_pipeline(
                search_pipeline,
                True,
                *args,
                **kwargs,
            ),
        )


class R2RAgentFactory:
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
    ):
        self.config = config
        self.providers = providers
        self.pipelines = pipelines

    def create_agents(
        self,
        rag_agent_override: Optional[R2RRAGAgent] = None,
        stream_rag_agent_override: Optional[R2RStreamingRAGAgent] = None,
        *args,
        **kwargs,
    ) -> R2RAgents:
        return R2RAgents(
            rag_agent=rag_agent_override
            or self.create_rag_agent(*args, **kwargs),
            streaming_rag_agent=stream_rag_agent_override
            or self.create_streaming_rag_agent(*args, **kwargs),
        )

    def create_streaming_rag_agent(
        self, *args, **kwargs
    ) -> R2RStreamingRAGAgent:
        if not self.providers.llm or not self.providers.database:
            raise ValueError(
                "LLM and database providers are required for RAG Agent"
            )

        return R2RStreamingRAGAgent(
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            config=self.config.agent,
            search_pipeline=self.pipelines.search_pipeline,
        )

    def create_rag_agent(self, *args, **kwargs) -> R2RRAGAgent:
        if not self.providers.llm or not self.providers.database:
            raise ValueError(
                "LLM and database providers are required for RAG Agent"
            )
        return R2RRAGAgent(
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            config=self.config.agent,
            search_pipeline=self.pipelines.search_pipeline,
        )
