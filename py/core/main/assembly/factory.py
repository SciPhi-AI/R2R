import logging
import os
from typing import Any, Optional

from core.agent import FUSERAGAgent, FUSEStreamingRAGAgent
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
from core.pipes import (
    EmbeddingPipe,
    GeneratorPipe,
    GraphClusteringPipe,
    GraphCommunitySummaryPipe,
    GraphDescriptionPipe,
    GraphSearchSearchPipe,
    GraphStoragePipe,
    MultiSearchPipe,
    ParsingPipe,
    RAGPipe,
    SearchPipe,
    StreamingRAGPipe,
    VectorSearchPipe,
    VectorStoragePipe,
)
from core.providers.email.sendgrid import SendGridEmailProvider

from ..abstractions import FUSEAgents, FUSEPipelines, FUSEPipes, FUSEProviders
from ..config import FUSEConfig

logger = logging.getLogger()
from core.database import PostgresDatabaseProvider
from core.providers import (
    AsyncSMTPEmailProvider,
    BcryptCryptoConfig,
    BCryptCryptoProvider,
    ConsoleMockEmailProvider,
    HatchetOrchestrationProvider,
    LiteLLMCompletionProvider,
    LiteLLMEmbeddingProvider,
    NaClCryptoConfig,
    NaClCryptoProvider,
    OllamaEmbeddingProvider,
    OpenAICompletionProvider,
    OpenAIEmbeddingProvider,
    FUSEAuthProvider,
    FUSEIngestionConfig,
    FUSEIngestionProvider,
    SimpleOrchestrationProvider,
    SupabaseAuthProvider,
    UnstructuredIngestionConfig,
    UnstructuredIngestionProvider,
)


class FUSEProviderFactory:
    def __init__(self, config: FUSEConfig):
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
        ),
        *args,
        **kwargs,
    ) -> FUSEAuthProvider | SupabaseAuthProvider:
        if auth_config.provider == "fuse":
            fuse_auth = FUSEAuthProvider(
                auth_config, crypto_provider, database_provider, email_provider
            )
            await fuse_auth.initialize()
            return fuse_auth
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
        llm_provider: LiteLLMCompletionProvider | OpenAICompletionProvider,
        *args,
        **kwargs,
    ) -> FUSEIngestionProvider | UnstructuredIngestionProvider:
        config_dict = (
            ingestion_config.model_dump()
            if isinstance(ingestion_config, IngestionConfig)
            else ingestion_config
        )

        extra_fields = config_dict.pop("extra_fields", {})

        if config_dict["provider"] == "fuse":
            fuse_ingestion_config = FUSEIngestionConfig(
                **config_dict, **extra_fields
            )
            return FUSEIngestionProvider(
                fuse_ingestion_config, database_provider, llm_provider
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
            orchestration_provider.get_worker("fuse-worker")
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
            from ...database.postgres import PostgresDatabaseProvider

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
    ) -> LiteLLMCompletionProvider | OpenAICompletionProvider:
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
    ) -> (
        AsyncSMTPEmailProvider
        | ConsoleMockEmailProvider
        | SendGridEmailProvider
    ):
        """Creates an email provider based on configuration."""
        if not email_config:
            raise ValueError(
                "No email configuration provided for email provider, please add `[email]` to your `fuse.toml`."
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
            FUSEAuthProvider | SupabaseAuthProvider
        ] = None,
        crypto_provider_override: Optional[
            BCryptCryptoProvider | NaClCryptoProvider
        ] = None,
        database_provider_override: Optional[PostgresDatabaseProvider] = None,
        email_provider_override: Optional[
            AsyncSMTPEmailProvider
            | ConsoleMockEmailProvider
            | SendGridEmailProvider
        ] = None,
        embedding_provider_override: Optional[
            LiteLLMEmbeddingProvider
            | OpenAIEmbeddingProvider
            | OllamaEmbeddingProvider
        ] = None,
        ingestion_provider_override: Optional[
            FUSEIngestionProvider | UnstructuredIngestionProvider
        ] = None,
        llm_provider_override: Optional[
            OpenAICompletionProvider | LiteLLMCompletionProvider
        ] = None,
        orchestration_provider_override: Optional[Any] = None,
        *args,
        **kwargs,
    ) -> FUSEProviders:
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

        return FUSEProviders(
            auth=auth_provider,
            database=database_provider,
            embedding=embedding_provider,
            ingestion=ingestion_provider,
            llm=llm_provider,
            email=email_provider,
            orchestration=orchestration_provider,
        )


class FUSEPipeFactory:
    def __init__(self, config: FUSEConfig, providers: FUSEProviders):
        self.config = config
        self.providers = providers

    def create_pipes(
        self,
        parsing_pipe_override: Optional[ParsingPipe] = None,
        embedding_pipe_override: Optional[EmbeddingPipe] = None,
        graph_storage_pipe_override: Optional[GraphStoragePipe] = None,
        graph_search_pipe_override: Optional[GraphSearchSearchPipe] = None,
        vector_storage_pipe_override: Optional[VectorStoragePipe] = None,
        vector_search_pipe_override: Optional[VectorSearchPipe] = None,
        rag_pipe_override: Optional[RAGPipe] = None,
        streaming_rag_pipe_override: Optional[StreamingRAGPipe] = None,
        graph_description_pipe: Optional[GraphDescriptionPipe] = None,
        graph_clustering_pipe: Optional[GraphClusteringPipe] = None,
        graph_community_summary_pipe: Optional[
            GraphCommunitySummaryPipe
        ] = None,
        *args,
        **kwargs,
    ) -> FUSEPipes:
        return FUSEPipes(
            parsing_pipe=parsing_pipe_override
            or self.create_parsing_pipe(
                self.config.ingestion.excluded_parsers,
                *args,
                **kwargs,
            ),
            embedding_pipe=embedding_pipe_override
            or self.create_embedding_pipe(*args, **kwargs),
            graph_storage_pipe=graph_storage_pipe_override
            or self.create_graph_storage_pipe(*args, **kwargs),
            vector_storage_pipe=vector_storage_pipe_override
            or self.create_vector_storage_pipe(*args, **kwargs),
            vector_search_pipe=vector_search_pipe_override
            or self.create_vector_search_pipe(*args, **kwargs),
            graph_search_pipe=graph_search_pipe_override
            or self.create_graph_search_pipe(*args, **kwargs),
            rag_pipe=rag_pipe_override
            or self.create_rag_pipe(*args, **kwargs),
            streaming_rag_pipe=streaming_rag_pipe_override
            or self.create_rag_pipe(True, *args, **kwargs),
            graph_description_pipe=graph_description_pipe
            or self.create_graph_description_pipe(*args, **kwargs),
            graph_clustering_pipe=graph_clustering_pipe
            or self.create_graph_clustering_pipe(*args, **kwargs),
            graph_community_summary_pipe=graph_community_summary_pipe
            or self.create_graph_community_summary_pipe(*args, **kwargs),
        )

    def create_parsing_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import ParsingPipe

        return ParsingPipe(
            ingestion_provider=self.providers.ingestion,
            database_provider=self.providers.database,
            config=AsyncPipe.PipeConfig(name="parsing_pipe"),
        )

    def create_embedding_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        from core.pipes import EmbeddingPipe

        return EmbeddingPipe(
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
            database_provider=self.providers.database,
            config=AsyncPipe.PipeConfig(name="vector_storage_pipe"),
        )

    def create_default_vector_search_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        from core.pipes import VectorSearchPipe

        return VectorSearchPipe(
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
            llm_provider=self.providers.llm,
            database_provider=self.providers.database,
            config=QueryTransformPipe.QueryTransformConfig(
                name="multi_query_transform",
                task_prompt=expansion_technique,
            ),
        )

        return MultiSearchPipe(
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
            search_pipes={
                "vanilla": vanilla_vector_search_pipe,
                "hyde": hyde_search_pipe,
                "rag_fusion": rag_fusion_pipe,
            },
            default_strategy="hyde",
            config=AsyncPipe.PipeConfig(name="routing_search_pipe"),
        )

    def create_graph_storage_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import GraphStoragePipe

        return GraphStoragePipe(
            database_provider=self.providers.database,
            config=AsyncPipe.PipeConfig(name="graph_storage_pipe"),
        )

    def create_graph_search_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import GraphSearchSearchPipe

        return GraphSearchSearchPipe(
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            embedding_provider=self.providers.embedding,
            config=GeneratorPipe.PipeConfig(
                name="kg_rag_pipe", task_prompt="kg_search"
            ),
        )

    def create_rag_pipe(self, stream: bool = False, *args, **kwargs) -> Any:
        if stream:
            from core.pipes import StreamingRAGPipe

            return StreamingRAGPipe(
                llm_provider=self.providers.llm,
                database_provider=self.providers.database,
                config=GeneratorPipe.PipeConfig(
                    name="streaming_rag_pipe", task_prompt="default_rag"
                ),
            )
        else:
            from core.pipes import RAGPipe

            return RAGPipe(
                llm_provider=self.providers.llm,
                database_provider=self.providers.database,
                config=GeneratorPipe.PipeConfig(
                    name="search_rag_pipe", task_prompt="default_rag"
                ),
            )

    def create_graph_description_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import GraphDescriptionPipe

        return GraphDescriptionPipe(
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(name="graph_description_pipe"),
        )

    def create_graph_clustering_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import GraphClusteringPipe

        return GraphClusteringPipe(
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(name="graph_clustering_pipe"),
        )

    def create_graph_community_summary_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import GraphCommunitySummaryPipe

        return GraphCommunitySummaryPipe(
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(name="graph_community_summary_pipe"),
        )


class FUSEPipelineFactory:
    def __init__(
        self, config: FUSEConfig, providers: FUSEProviders, pipes: FUSEPipes
    ):
        self.config = config
        self.providers = providers
        self.pipes = pipes

    def create_search_pipeline(self, *args, **kwargs) -> SearchPipeline:
        """factory method to create an ingestion pipeline."""
        search_pipeline = SearchPipeline()

        # Add vector search pipes if embedding provider and vector provider is set
        if (
            self.config.embedding.provider is not None
            and self.config.database.provider is not None
        ):
            search_pipeline.add_pipe(
                self.pipes.vector_search_pipe, vector_search_pipe=True
            )
            search_pipeline.add_pipe(
                self.pipes.graph_search_pipe, graph_search_pipe=True
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

        rag_pipeline = RAGPipeline()
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
    ) -> FUSEPipelines:
        search_pipeline = search_pipeline or self.create_search_pipeline(
            *args, **kwargs
        )
        return FUSEPipelines(
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


class FUSEAgentFactory:
    def __init__(
        self,
        config: FUSEConfig,
        providers: FUSEProviders,
        pipelines: FUSEPipelines,
    ):
        self.config = config
        self.providers = providers
        self.pipelines = pipelines

    def create_agents(
        self,
        rag_agent_override: Optional[FUSERAGAgent] = None,
        stream_rag_agent_override: Optional[FUSEStreamingRAGAgent] = None,
        *args,
        **kwargs,
    ) -> FUSEAgents:
        return FUSEAgents(
            rag_agent=rag_agent_override
            or self.create_rag_agent(*args, **kwargs),
            streaming_rag_agent=stream_rag_agent_override
            or self.create_streaming_rag_agent(*args, **kwargs),
        )

    def create_streaming_rag_agent(
        self, *args, **kwargs
    ) -> FUSEStreamingRAGAgent:
        if not self.providers.llm or not self.providers.database:
            raise ValueError(
                "LLM and database providers are required for RAG Agent"
            )

        return FUSEStreamingRAGAgent(
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            config=self.config.agent,
            search_pipeline=self.pipelines.search_pipeline,
        )

    def create_rag_agent(self, *args, **kwargs) -> FUSERAGAgent:
        if not self.providers.llm or not self.providers.database:
            raise ValueError(
                "LLM and database providers are required for RAG Agent"
            )
        return FUSERAGAgent(
            database_provider=self.providers.database,
            llm_provider=self.providers.llm,
            config=self.config.agent,
            search_pipeline=self.pipelines.search_pipeline,
        )
