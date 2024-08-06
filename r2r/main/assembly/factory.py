import logging
import os
from typing import Any, Optional

from r2r.agents import R2RRAGAgent, R2RStreamingRAGAgent
from r2r.base import (
    AgentConfig,
    AsyncPipe,
    AuthConfig,
    AuthProvider,
    ChunkingConfig,
    ChunkingProvider,
    CompletionConfig,
    CompletionProvider,
    CryptoConfig,
    CryptoProvider,
    DatabaseConfig,
    DatabaseProvider,
    EmbeddingConfig,
    EmbeddingProvider,
    EvalProvider,
    KGProvider,
    KVLoggingSingleton,
    ParsingConfig,
    ParsingProvider,
    PromptConfig,
    PromptProvider,
)
from r2r.pipelines import (
    EvalPipeline,
    IngestionPipeline,
    RAGPipeline,
    SearchPipeline,
)

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from .config import R2RConfig

logger = logging.getLogger(__name__)


class R2RProviderFactory:
    def __init__(self, config: R2RConfig):
        self.config = config

    @staticmethod
    def create_auth_provider(
        auth_config: AuthConfig,
        db_provider: DatabaseProvider,
        crypto_provider: Optional[CryptoProvider] = None,
        *args,
        **kwargs,
    ) -> AuthProvider:
        auth_provider: Optional[AuthProvider] = None
        if auth_config.provider == "r2r":
            from r2r.providers import R2RAuthProvider

            auth_provider = R2RAuthProvider(
                auth_config, crypto_provider, db_provider
            )
        elif auth_config.provider is None:
            auth_provider = None
        else:
            raise ValueError(
                f"Auth provider {auth_config.provider} not supported."
            )
        return auth_provider

    @staticmethod
    def create_crypto_provider(
        crypto_config: CryptoConfig, *args, **kwargs
    ) -> CryptoProvider:
        crypto_provider: Optional[CryptoProvider] = None
        if crypto_config.provider == "bcrypt":
            from r2r.providers.crypto import BCryptConfig, BCryptProvider

            crypto_provider = BCryptProvider(
                BCryptConfig(**crypto_config.dict())
            )
        elif crypto_config.provider is None:
            crypto_provider = None
        else:
            raise ValueError(
                f"Crypto provider {crypto_config.provider} not supported."
            )
        return crypto_provider

    @staticmethod
    def create_parsing_provider(
        parsing_config: ParsingConfig, *args, **kwargs
    ) -> ParsingProvider:
        if parsing_config.provider == "r2r":
            from r2r.providers import R2RParsingProvider

            return R2RParsingProvider(parsing_config)
        elif parsing_config.provider == "unstructured":
            from r2r.providers import UnstructuredParsingProvider

            return UnstructuredParsingProvider(parsing_config)
        else:
            raise ValueError(
                f"Parsing provider {parsing_config.provider} not supported"
            )

    @staticmethod
    def create_chunking_provider(
        chunking_config: ChunkingConfig, *args, **kwargs
    ) -> ChunkingProvider:
        if chunking_config.provider == "r2r":
            from r2r.providers import R2RChunkingProvider

            return R2RChunkingProvider(chunking_config)
        elif chunking_config.provider == "unstructured":
            from r2r.providers import UnstructuredChunkingProvider

            return UnstructuredChunkingProvider(chunking_config)
        else:
            raise ValueError(
                f"Chunking provider {chunking_config.provider} not supported"
            )

    def create_database_provider(
        self,
        db_config: DatabaseConfig,
        crypto_provider: Optional[CryptoProvider] = None,
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
            from r2r.providers import PostgresDBProvider

            database_provider = PostgresDBProvider(
                db_config, vector_db_dimension, crypto_provider=crypto_provider
            )
        elif db_config.provider is None:
            database_provider = None
        else:
            raise ValueError(
                f"Database provider {db_config.provider} not supported"
            )

        return database_provider

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
            from r2r.providers import OpenAIEmbeddingProvider

            embedding_provider = OpenAIEmbeddingProvider(embedding)

        elif embedding.provider == "litellm":
            from r2r.providers import LiteLLMEmbeddingProvider

            embedding_provider = LiteLLMEmbeddingProvider(embedding)

        elif embedding.provider == "sciphi":
            from r2r.providers.embeddings import SciPhiEmbeddingProvider

            embedding_provider = SciPhiEmbeddingProvider(embedding)

        elif embedding.provider == "ollama":
            from r2r.providers import OllamaEmbeddingProvider

            embedding_provider = OllamaEmbeddingProvider(embedding)

        elif embedding is None:
            embedding_provider = None

        else:
            raise ValueError(
                f"Embedding provider {embedding.provider} not supported"
            )

        return embedding_provider

    @staticmethod
    def create_eval_provider(
        eval_config, prompt_provider, *args, **kwargs
    ) -> Optional[EvalProvider]:
        if eval_config.provider == "local":
            from r2r.providers import LLMEvalProvider

            llm_provider = R2RProviderFactory.create_llm_provider(
                eval_config.llm
            )
            eval_provider = LLMEvalProvider(
                eval_config,
                llm_provider=llm_provider,
                prompt_provider=prompt_provider,
            )
        elif eval_config.provider is None:
            eval_provider = None
        else:
            raise ValueError(
                f"Eval provider {eval_config.provider} not supported."
            )

        return eval_provider

    @staticmethod
    def create_llm_provider(
        llm_config: CompletionConfig, *args, **kwargs
    ) -> CompletionProvider:
        llm_provider: Optional[CompletionProvider] = None
        if llm_config.provider == "openai":
            from r2r.providers import OpenAICompletionProvider

            llm_provider = OpenAICompletionProvider(llm_config)
        elif llm_config.provider == "litellm":
            from r2r.providers import LiteCompletionProvider

            llm_provider = LiteCompletionProvider(llm_config)
        elif llm_config.provider == "sciphi":
            from r2r.providers.llm import SciPhiCompletionProvider

            llm_provider = SciPhiCompletionProvider(llm_config)
        else:
            raise ValueError(
                f"Language model provider {llm_config.provider} not supported"
            )
        if not llm_provider:
            raise ValueError("Language model provider not found")
        return llm_provider

    @staticmethod
    def create_prompt_provider(
        prompt_config: PromptConfig, *args, **kwargs
    ) -> PromptProvider:
        prompt_provider = None
        if prompt_config.provider == "r2r":
            from r2r.providers import R2RPromptProvider

            prompt_provider = R2RPromptProvider(prompt_config)
        else:
            raise ValueError(
                f"Prompt provider {prompt_config.provider} not supported"
            )
        return prompt_provider

    @staticmethod
    def create_kg_provider(kg_config, *args, **kwargs):
        if kg_config.provider == "neo4j":
            from r2r.providers import Neo4jKGProvider

            return Neo4jKGProvider(kg_config)
        elif kg_config.provider is None:
            return None
        else:
            raise ValueError(
                f"KG provider {kg_config.provider} not supported."
            )

    def create_providers(
        self,
        embedding_provider_override: Optional[EmbeddingProvider] = None,
        eval_provider_override: Optional[EvalProvider] = None,
        llm_provider_override: Optional[CompletionProvider] = None,
        prompt_provider_override: Optional[PromptProvider] = None,
        kg_provider_override: Optional[KGProvider] = None,
        crypto_provider_override: Optional[CryptoProvider] = None,
        auth_provider_override: Optional[AuthProvider] = None,
        database_provider_override: Optional[DatabaseProvider] = None,
        parsing_provider_override: Optional[ParsingProvider] = None,
        chunking_config_override: Optional[ChunkingProvider] = None,
        *args,
        **kwargs,
    ) -> R2RProviders:

        prompt_provider = (
            prompt_provider_override
            or self.create_prompt_provider(self.config.prompt, *args, **kwargs)
        )
        embedding_provider = (
            embedding_provider_override
            or self.create_embedding_provider(
                self.config.embedding, *args, **kwargs
            )
        )
        eval_provider = eval_provider_override or self.create_eval_provider(
            self.config.eval,
            prompt_provider=prompt_provider,
            *args,
            **kwargs,
        )

        llm_provider = llm_provider_override or self.create_llm_provider(
            self.config.completion, *args, **kwargs
        )
        kg_provider = kg_provider_override or self.create_kg_provider(
            self.config.kg, *args, **kwargs
        )
        crypto_provider = (
            crypto_provider_override
            or self.create_crypto_provider(self.config.crypto, *args, **kwargs)
        )
        database_provider = (
            database_provider_override
            or self.create_database_provider(
                self.config.database, crypto_provider, *args, **kwargs
            )
        )
        auth_provider = auth_provider_override or self.create_auth_provider(
            self.config.auth,
            database_provider,
            crypto_provider,
            *args,
            **kwargs,
        )
        parsing_provider = (
            parsing_provider_override
            or self.create_parsing_provider(
                self.config.parsing, *args, **kwargs
            )
        )
        chunking_provider = (
            chunking_config_override
            or self.create_chunking_provider(
                self.config.chunking, *args, **kwargs
            )
        )

        return R2RProviders(
            auth=auth_provider,
            chunking=chunking_provider,
            database=database_provider,
            embedding=embedding_provider,
            eval=eval_provider,
            llm=llm_provider,
            parsing=parsing_provider,
            prompt=prompt_provider,
            kg=kg_provider,
        )


class R2RPipeFactory:
    def __init__(self, config: R2RConfig, providers: R2RProviders):
        self.config = config
        self.providers = providers

    def create_pipes(
        self,
        parsing_pipe_override: Optional[AsyncPipe] = None,
        embedding_pipe_override: Optional[AsyncPipe] = None,
        kg_pipe_override: Optional[AsyncPipe] = None,
        kg_storage_pipe_override: Optional[AsyncPipe] = None,
        kg_search_pipe_override: Optional[AsyncPipe] = None,
        vector_storage_pipe_override: Optional[AsyncPipe] = None,
        vector_search_pipe_override: Optional[AsyncPipe] = None,
        rag_pipe_override: Optional[AsyncPipe] = None,
        streaming_rag_pipe_override: Optional[AsyncPipe] = None,
        eval_pipe_override: Optional[AsyncPipe] = None,
        chunking_pipe_override: Optional[AsyncPipe] = None,
        *args,
        **kwargs,
    ) -> R2RPipes:
        return R2RPipes(
            parsing_pipe=parsing_pipe_override
            or self.create_parsing_pipe(
                self.config.parsing.excluded_parsers,
                self.config.parsing.override_parsers,
                *args,
                **kwargs,
            ),
            embedding_pipe=embedding_pipe_override
            or self.create_embedding_pipe(*args, **kwargs),
            kg_pipe=kg_pipe_override or self.create_kg_pipe(*args, **kwargs),
            kg_storage_pipe=kg_storage_pipe_override
            or self.create_kg_storage_pipe(*args, **kwargs),
            kg_search_search_pipe=kg_search_pipe_override
            or self.create_kg_search_pipe(*args, **kwargs),
            vector_storage_pipe=vector_storage_pipe_override
            or self.create_vector_storage_pipe(*args, **kwargs),
            vector_search_pipe=vector_search_pipe_override
            or self.create_vector_search_pipe(*args, **kwargs),
            rag_pipe=rag_pipe_override
            or self.create_rag_pipe(*args, **kwargs),
            streaming_rag_pipe=streaming_rag_pipe_override
            or self.create_rag_pipe(stream=True, *args, **kwargs),
            eval_pipe=eval_pipe_override
            or self.create_eval_pipe(*args, **kwargs),
            chunking_pipe=chunking_pipe_override
            or self.create_chunking_pipe(*args, **kwargs),
        )

    def create_parsing_pipe(
        self,
        excluded_parsers: Optional[list] = None,
        override_parsers: Optional[list] = None,
        *args,
        **kwargs,
    ) -> Any:
        from r2r.pipes import ParsingPipe

        return ParsingPipe(
            excluded_parsers=excluded_parsers or [],
            override_parsers=override_parsers or [],
        )

    def create_parsing_pipe(self, *args, **kwargs) -> Any:
        from r2r.pipes import ParsingPipe

        return ParsingPipe(parsing_provider=self.providers.parsing)

    def create_chunking_pipe(self, *args, **kwargs) -> Any:
        from r2r.pipes import ChunkingPipe

        return ChunkingPipe(chunking_provider=self.providers.chunking)

    def create_embedding_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        from r2r.base import RecursiveCharacterTextSplitter
        from r2r.pipes import EmbeddingPipe

        return EmbeddingPipe(
            embedding_provider=self.providers.embedding,
            database_provider=self.providers.database,
            embedding_batch_size=self.config.embedding.batch_size,
        )

    def create_vector_storage_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        from r2r.pipes import VectorStoragePipe

        return VectorStoragePipe(database_provider=self.providers.database)

    def create_vector_search_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        from r2r.pipes import VectorSearchPipe

        return VectorSearchPipe(
            database_provider=self.providers.database,
            embedding_provider=self.providers.embedding,
        )

    def create_kg_pipe(self, *args, **kwargs) -> Any:
        if self.config.kg.provider is None:
            return None

        from r2r.pipes import KGExtractionPipe

        return KGExtractionPipe(
            kg_provider=self.providers.kg,
            llm_provider=self.providers.llm,
            prompt_provider=self.providers.prompt,
            chunking_provider=self.providers.chunking,
            kg_batch_size=self.config.kg.batch_size,
        )

    def create_kg_storage_pipe(self, *args, **kwargs) -> Any:
        if self.config.kg.provider is None:
            return None

        from r2r.pipes import KGStoragePipe

        return KGStoragePipe(
            kg_provider=self.providers.kg,
            embedding_provider=self.providers.embedding,
        )

    def create_kg_search_pipe(self, *args, **kwargs) -> Any:
        if self.config.kg.provider is None:
            return None

        from r2r.pipes import KGSearchSearchPipe

        return KGSearchSearchPipe(
            kg_provider=self.providers.kg,
            llm_provider=self.providers.llm,
            prompt_provider=self.providers.prompt,
        )

    def create_rag_pipe(self, stream: bool = False, *args, **kwargs) -> Any:
        if stream:
            from r2r.pipes import StreamingSearchRAGPipe

            return StreamingSearchRAGPipe(
                llm_provider=self.providers.llm,
                prompt_provider=self.providers.prompt,
            )
        else:
            from r2r.pipes import SearchRAGPipe

            return SearchRAGPipe(
                llm_provider=self.providers.llm,
                prompt_provider=self.providers.prompt,
            )

    def create_eval_pipe(self, *args, **kwargs) -> Any:
        from r2r.pipes import EvalPipe

        return EvalPipe(eval_provider=self.providers.eval)


class R2RPipelineFactory:
    def __init__(self, config: R2RConfig, pipes: R2RPipes):
        self.config = config
        self.pipes = pipes

    def create_ingestion_pipeline(self, *args, **kwargs) -> IngestionPipeline:
        """factory method to create an ingestion pipeline."""
        ingestion_pipeline = IngestionPipeline()

        ingestion_pipeline.add_pipe(
            pipe=self.pipes.parsing_pipe, parsing_pipe=True
        )
        ingestion_pipeline.add_pipe(
            self.pipes.chunking_pipe, chunking_pipe=True
        )

        # Add embedding pipes if provider is set
        if (
            self.config.embedding.provider is not None
            and self.config.database.provider is not None
        ):
            ingestion_pipeline.add_pipe(
                self.pipes.embedding_pipe, embedding_pipe=True
            )
            ingestion_pipeline.add_pipe(
                self.pipes.vector_storage_pipe, embedding_pipe=True
            )
        # Add KG pipes if provider is set
        if self.config.kg.provider is not None:
            ingestion_pipeline.add_pipe(self.pipes.kg_pipe, kg_pipe=True)
            ingestion_pipeline.add_pipe(
                self.pipes.kg_storage_pipe, kg_pipe=True
            )

        return ingestion_pipeline

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
                self.pipes.kg_search_search_pipe, kg_pipe=True
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

    def create_eval_pipeline(self, *args, **kwargs) -> EvalPipeline:
        eval_pipeline = EvalPipeline()
        eval_pipeline.add_pipe(self.pipes.eval_pipe)
        return eval_pipeline

    def create_pipelines(
        self,
        ingestion_pipeline: Optional[IngestionPipeline] = None,
        search_pipeline: Optional[SearchPipeline] = None,
        rag_pipeline: Optional[RAGPipeline] = None,
        streaming_rag_pipeline: Optional[RAGPipeline] = None,
        eval_pipeline: Optional[EvalPipeline] = None,
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
            ingestion_pipeline=ingestion_pipeline
            or self.create_ingestion_pipeline(*args, **kwargs),
            search_pipeline=search_pipeline,
            rag_pipeline=rag_pipeline
            or self.create_rag_pipeline(
                search_pipeline=search_pipeline,
                stream=False,
                *args,
                **kwargs,
            ),
            streaming_rag_pipeline=streaming_rag_pipeline
            or self.create_rag_pipeline(
                search_pipeline=search_pipeline,
                stream=True,
                *args,
                **kwargs,
            ),
            eval_pipeline=eval_pipeline
            or self.create_eval_pipeline(*args, **kwargs),
        )

    def configure_logging(self):
        KVLoggingSingleton.configure(self.config.logging)


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
            or self.create_rag_agent(*args, **kwargs, stream=True),
        )

    def create_rag_agent(
        self, stream: bool = False, *args, **kwargs
    ) -> R2RRAGAgent:
        if not self.providers.llm or not self.providers.prompt:
            raise ValueError(
                "LLM and Prompt providers are required for RAG Agent"
            )

        if stream:
            rag_agent = R2RStreamingRAGAgent(
                llm_provider=self.providers.llm,
                prompt_provider=self.providers.prompt,
                config=self.config.agent,
                search_pipeline=self.pipelines.search_pipeline,
            )
        else:
            rag_agent = R2RRAGAgent(
                llm_provider=self.providers.llm,
                prompt_provider=self.providers.prompt,
                config=self.config.agent,
                search_pipeline=self.pipelines.search_pipeline,
            )

        return rag_agent
