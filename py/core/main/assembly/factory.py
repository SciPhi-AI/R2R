import logging
import os
from typing import Any, Optional

from core.agent import R2RRAGAgent, R2RStreamingRAGAgent
from core.base import (
    AsyncPipe,
    AuthConfig,
    AuthProvider,
    CompletionConfig,
    CompletionProvider,
    CryptoConfig,
    CryptoProvider,
    DatabaseConfig,
    DatabaseProvider,
    EmbeddingConfig,
    EmbeddingProvider,
    FileConfig,
    FileProvider,
    IngestionConfig,
    IngestionProvider,
    KGProvider,
    OrchestrationConfig,
    PromptConfig,
    PromptProvider,
    RunLoggingSingleton,
)
from core.pipelines import RAGPipeline, SearchPipeline
from core.pipes import GeneratorPipe, MultiSearchPipe, SearchPipe

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig

logger = logging.getLogger(__name__)


class R2RProviderFactory:
    def __init__(self, config: R2RConfig):
        self.config = config

    @staticmethod
    async def create_auth_provider(
        auth_config: AuthConfig,
        db_provider: DatabaseProvider,
        crypto_provider: CryptoProvider,
        *args,
        **kwargs,
    ) -> AuthProvider:
        if auth_config.provider == "r2r":
            from core.providers import R2RAuthProvider

            r2r_auth = R2RAuthProvider(
                auth_config, crypto_provider, db_provider
            )
            await r2r_auth.initialize()
            return r2r_auth
        elif auth_config.provider == "supabase":
            from core.providers import SupabaseAuthProvider

            return SupabaseAuthProvider(
                auth_config, crypto_provider, db_provider
            )
        else:
            raise ValueError(
                f"Auth provider {auth_config.provider} not supported."
            )

    @staticmethod
    def create_crypto_provider(
        crypto_config: CryptoConfig, *args, **kwargs
    ) -> CryptoProvider:
        if crypto_config.provider == "bcrypt":
            from core.providers.crypto import BCryptConfig, BCryptProvider

            return BCryptProvider(BCryptConfig(**crypto_config.dict()))
        else:
            raise ValueError(
                f"Crypto provider {crypto_config.provider} not supported."
            )

    @staticmethod
    def create_ingestion_provider(
        ingestion_config: IngestionConfig, *args, **kwargs
    ) -> IngestionProvider:
        config_dict = ingestion_config.model_dump()
        extra_fields = config_dict.pop("extra_fields", {})

        if ingestion_config.provider == "r2r":
            from core.providers import R2RIngestionConfig, R2RIngestionProvider

            r2r_ingestion_config = R2RIngestionConfig(
                **config_dict, **extra_fields
            )
            return R2RIngestionProvider(r2r_ingestion_config)
        elif ingestion_config.provider in [
            "unstructured_local",
            "unstructured_api",
        ]:
            from core.providers import (
                UnstructuredIngestionConfig,
                UnstructuredIngestionProvider,
            )

            unstructured_ingestion_config = UnstructuredIngestionConfig(
                **config_dict, **extra_fields
            )

            return UnstructuredIngestionProvider(
                unstructured_ingestion_config,
            )
        else:
            raise ValueError(
                f"Ingestion provider {ingestion_config.provider} not supported"
            )

    @staticmethod
    def create_orchestration_provider(
        config: OrchestrationConfig, *args, **kwargs
    ):
        if config.provider == "hatchet":
            from core.providers import HatchetOrchestrationProvider

            orchestration_provider = HatchetOrchestrationProvider(config)
            orchestration_provider.get_worker("r2r-worker")
            return orchestration_provider
        elif config.provider == "simple":
            from core.providers import SimpleOrchestrationProvider

            return SimpleOrchestrationProvider(config)

    async def create_database_provider(
        self,
        db_config: DatabaseConfig,
        crypto_provider: CryptoProvider,
        *args,
        **kwargs,
    ) -> DatabaseProvider:
        database_provider: Optional[DatabaseProvider] = None
        if not self.config.embedding.base_dimension:
            raise ValueError(
                "Embedding config must have a base dimension to initialize database."
            )

        vector_db_dimension = self.config.embedding.base_dimension
        if db_config.provider == "postgres":
            from core.providers import PostgresDBProvider

            database_provider = PostgresDBProvider(
                db_config, vector_db_dimension, crypto_provider=crypto_provider
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
    ) -> EmbeddingProvider:
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

        elif embedding is None:
            embedding_provider = None

        else:
            raise ValueError(
                f"Embedding provider {embedding.provider} not supported"
            )

        return embedding_provider

    @staticmethod
    async def create_file_provider(
        file_config: FileConfig,
        db_provider: Any,
        *args,
        **kwargs,
    ) -> FileProvider:
        file_provider: Optional[FileProvider] = None
        if file_config.provider == "postgres":
            from core.providers import PostgresFileProvider

            file_provider = PostgresFileProvider(file_config, db_provider)
            await file_provider.initialize()
        else:
            raise ValueError(
                f"File provider {file_config.provider} not supported."
            )

        return file_provider

    @staticmethod
    def create_llm_provider(
        llm_config: CompletionConfig, *args, **kwargs
    ) -> CompletionProvider:
        llm_provider: Optional[CompletionProvider] = None
        if llm_config.provider == "openai":
            from core.providers import OpenAICompletionProvider

            llm_provider = OpenAICompletionProvider(llm_config)
        elif llm_config.provider == "litellm":
            from core.providers import LiteCompletionProvider

            llm_provider = LiteCompletionProvider(llm_config)
        else:
            raise ValueError(
                f"Language model provider {llm_config.provider} not supported"
            )
        if not llm_provider:
            raise ValueError("Language model provider not found")
        return llm_provider

    @staticmethod
    async def create_prompt_provider(
        prompt_config: PromptConfig,
        db_provider: DatabaseProvider,
        *args,
        **kwargs,
    ) -> PromptProvider:
        prompt_provider = None

        if prompt_config.provider != "r2r":
            raise ValueError(
                f"Prompt provider {prompt_config.provider} not supported"
            )
        from core.providers import R2RPromptProvider

        prompt_provider = R2RPromptProvider(prompt_config, db_provider)
        await prompt_provider.initialize()

        return prompt_provider

    @staticmethod
    async def create_kg_provider(
        kg_config, database_provider, embedding_provider, *args, **kwargs
    ):
        if kg_config.provider == "postgres":
            from core.providers import PostgresKGProvider

            provider = PostgresKGProvider(
                kg_config, database_provider, embedding_provider
            )
            await provider.initialize()
            return provider

        elif kg_config.provider is None:
            return None
        else:
            raise ValueError(
                f"KG provider {kg_config.provider} not supported."
            )

    async def create_providers(
        self,
        auth_provider_override: Optional[AuthProvider] = None,
        crypto_provider_override: Optional[CryptoProvider] = None,
        database_provider_override: Optional[DatabaseProvider] = None,
        embedding_provider_override: Optional[EmbeddingProvider] = None,
        file_provider_override: Optional[FileProvider] = None,
        ingestion_provider_override: Optional[IngestionProvider] = None,
        kg_provider_override: Optional[KGProvider] = None,
        llm_provider_override: Optional[CompletionProvider] = None,
        prompt_provider_override: Optional[PromptProvider] = None,
        orchestration_provider_override: Optional[Any] = None,
        *args,
        **kwargs,
    ) -> R2RProviders:
        embedding_provider = (
            embedding_provider_override
            or self.create_embedding_provider(
                self.config.embedding, *args, **kwargs
            )
        )

        ingestion_provider = (
            ingestion_provider_override
            or self.create_ingestion_provider(
                self.config.ingestion, *args, **kwargs
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

        kg_provider = kg_provider_override or await self.create_kg_provider(
            self.config.kg,
            database_provider,
            embedding_provider,
            *args,
            **kwargs,
        )

        auth_provider = (
            auth_provider_override
            or await self.create_auth_provider(
                self.config.auth,
                database_provider,
                crypto_provider,
                *args,
                **kwargs,
            )
        )

        prompt_provider = (
            prompt_provider_override
            or await self.create_prompt_provider(
                self.config.prompt, database_provider, *args, **kwargs
            )
        )

        file_provider = file_provider_override or await self.create_file_provider(
            self.config.file, database_provider, *args, **kwargs  # type: ignore
        )

        orchestration_provider = (
            orchestration_provider_override
            or self.create_orchestration_provider(self.config.orchestration)
        )

        return R2RProviders(
            auth=auth_provider,
            database=database_provider,
            embedding=embedding_provider,
            ingestion=ingestion_provider,
            llm=llm_provider,
            prompt=prompt_provider,
            kg=kg_provider,
            orchestration=orchestration_provider,
            file=file_provider,
        )


class R2RPipeFactory:
    def __init__(self, config: R2RConfig, providers: R2RProviders):
        self.config = config
        self.providers = providers

    def create_pipes(
        self,
        parsing_pipe_override: Optional[AsyncPipe] = None,
        embedding_pipe_override: Optional[AsyncPipe] = None,
        kg_triples_extraction_pipe_override: Optional[AsyncPipe] = None,
        kg_storage_pipe_override: Optional[AsyncPipe] = None,
        kg_search_pipe_override: Optional[AsyncPipe] = None,
        vector_storage_pipe_override: Optional[AsyncPipe] = None,
        vector_search_pipe_override: Optional[AsyncPipe] = None,
        rag_pipe_override: Optional[AsyncPipe] = None,
        streaming_rag_pipe_override: Optional[AsyncPipe] = None,
        kg_entity_description_pipe: Optional[AsyncPipe] = None,
        kg_clustering_pipe: Optional[AsyncPipe] = None,
        kg_community_summary_pipe: Optional[AsyncPipe] = None,
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
            kg_triples_extraction_pipe=kg_triples_extraction_pipe_override
            or self.create_kg_triples_extraction_pipe(*args, **kwargs),
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
            kg_community_summary_pipe=kg_community_summary_pipe
            or self.create_kg_community_summary_pipe(*args, **kwargs),
        )

    def create_parsing_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import ParsingPipe

        return ParsingPipe(
            ingestion_provider=self.providers.ingestion,
            file_provider=self.providers.file,
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
            prompt_provider=self.providers.prompt,
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

    def create_kg_triples_extraction_pipe(self, *args, **kwargs) -> Any:
        if self.config.kg.provider is None:
            return None

        from core.pipes import KGTriplesExtractionPipe

        return KGTriplesExtractionPipe(
            kg_provider=self.providers.kg,
            llm_provider=self.providers.llm,
            database_provider=self.providers.database,
            prompt_provider=self.providers.prompt,
            config=AsyncPipe.PipeConfig(name="kg_triples_extraction_pipe"),
        )

    def create_kg_storage_pipe(self, *args, **kwargs) -> Any:
        if self.config.kg.provider is None:
            return None

        from core.pipes import KGStoragePipe

        return KGStoragePipe(
            kg_provider=self.providers.kg,
            config=AsyncPipe.PipeConfig(name="kg_storage_pipe"),
        )

    def create_kg_search_pipe(self, *args, **kwargs) -> Any:
        if self.config.kg.provider is None:
            return None

        from core.pipes import KGSearchSearchPipe

        return KGSearchSearchPipe(
            kg_provider=self.providers.kg,
            llm_provider=self.providers.llm,
            prompt_provider=self.providers.prompt,
            embedding_provider=self.providers.embedding,
            config=GeneratorPipe.PipeConfig(
                name="kg_rag_pipe", task_prompt="kg_search"
            ),
        )

    def create_rag_pipe(self, stream: bool = False, *args, **kwargs) -> Any:
        if stream:
            from core.pipes import StreamingSearchRAGPipe

            return StreamingSearchRAGPipe(
                llm_provider=self.providers.llm,
                prompt_provider=self.providers.prompt,
                config=GeneratorPipe.PipeConfig(
                    name="streaming_rag_pipe", task_prompt="default_rag"
                ),
            )
        else:
            from core.pipes import SearchRAGPipe

            return SearchRAGPipe(
                llm_provider=self.providers.llm,
                prompt_provider=self.providers.prompt,
                config=GeneratorPipe.PipeConfig(
                    name="search_rag_pipe", task_prompt="default_rag"
                ),
            )

    def create_kg_entity_description_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGEntityDescriptionPipe

        return KGEntityDescriptionPipe(
            kg_provider=self.providers.kg,
            llm_provider=self.providers.llm,
            prompt_provider=self.providers.prompt,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(name="kg_entity_description_pipe"),
        )

    def create_kg_clustering_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGClusteringPipe

        return KGClusteringPipe(
            kg_provider=self.providers.kg,
            llm_provider=self.providers.llm,
            prompt_provider=self.providers.prompt,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(name="kg_clustering_pipe"),
        )

    def create_kg_community_summary_pipe(self, *args, **kwargs) -> Any:
        from core.pipes import KGCommunitySummaryPipe

        return KGCommunitySummaryPipe(
            kg_provider=self.providers.kg,
            llm_provider=self.providers.llm,
            prompt_provider=self.providers.prompt,
            embedding_provider=self.providers.embedding,
            config=AsyncPipe.PipeConfig(name="kg_community_summary_pipe"),
        )


class R2RPipelineFactory:
    def __init__(self, config: R2RConfig, pipes: R2RPipes):
        self.config = config
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

        # Add KG pipes if provider is set
        if self.config.kg.provider is not None:
            search_pipeline.add_pipe(
                self.pipes.kg_search_pipe, kg_triples_extraction_pipe=True
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
    ) -> R2RPipelines:
        try:
            self.configure_logging()
        except Exception as e:
            logger.warning(f"Error configuring logging: {e}")
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

    def configure_logging(self):
        RunLoggingSingleton.configure(self.config.logging)


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
        if not self.providers.llm or not self.providers.prompt:
            raise ValueError(
                "LLM and Prompt providers are required for RAG Agent"
            )

        return R2RStreamingRAGAgent(
            llm_provider=self.providers.llm,
            prompt_provider=self.providers.prompt,
            config=self.config.agent,
            search_pipeline=self.pipelines.search_pipeline,
        )

    def create_rag_agent(self, *args, **kwargs) -> R2RRAGAgent:
        if not self.providers.llm or not self.providers.prompt:
            raise ValueError(
                "LLM and Prompt providers are required for RAG Agent"
            )
        return R2RRAGAgent(
            llm_provider=self.providers.llm,
            prompt_provider=self.providers.prompt,
            config=self.config.agent,
            search_pipeline=self.pipelines.search_pipeline,
        )
