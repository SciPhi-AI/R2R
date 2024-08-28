import os
from typing import TYPE_CHECKING, Optional, Type

from core.agent import R2RRAGAgent
from core.base import (
    AsyncPipe,
    AuthProvider,
    CompletionProvider,
    CryptoProvider,
    DatabaseProvider,
    EmbeddingProvider,
    KGProvider,
    PromptProvider,
    RunLoggingSingleton,
    RunManager,
)
from core.pipelines import (
    IngestionPipeline,
    KGEnrichmentPipeline,
    RAGPipeline,
    SearchPipeline,
)

from ..api.routes.auth.base import AuthRouter
from ..api.routes.ingestion.base import IngestionRouter
from ..api.routes.management.base import ManagementRouter
from ..api.routes.restructure.base import RestructureRouter
from ..api.routes.retrieval.base import RetrievalRouter
from ..app import R2RApp
from ..config import R2RConfig
from ..services.auth_service import AuthService
from ..services.ingestion_service import IngestionService
from ..services.management_service import ManagementService
from ..services.restructure_service import RestructureService
from ..services.retrieval_service import RetrievalService
from .factory import (
    R2RAgentFactory,
    R2RPipeFactory,
    R2RPipelineFactory,
    R2RProviderFactory,
)


class R2RBuilder:
    def __init__(
        self,
        config: R2RConfig,
    ):
        self.config = config
        self.provider_factory_override: Optional[Type[R2RProviderFactory]] = (
            None
        )

        self.pipe_factory_override: Optional[R2RPipeFactory] = None
        self.pipeline_factory_override: Optional[R2RPipelineFactory] = None

        # Provider overrides
        self.auth_provider_override: Optional[AuthProvider] = None
        self.database_provider_override: Optional[DatabaseProvider] = None
        self.embedding_provider_override: Optional[EmbeddingProvider] = None
        self.llm_provider_override: Optional[CompletionProvider] = None
        self.prompt_provider_override: Optional[PromptProvider] = None
        self.kg_provider_override: Optional[KGProvider] = None
        self.crypto_provider_override: Optional[CryptoProvider] = None

        # Pipe overrides
        self.parsing_pipe_override: Optional[AsyncPipe] = None
        self.embedding_pipe_override: Optional[AsyncPipe] = None
        self.vector_storage_pipe_override: Optional[AsyncPipe] = None
        self.vector_search_pipe_override: Optional[AsyncPipe] = None
        self.rag_pipe_override: Optional[AsyncPipe] = None
        self.streaming_rag_pipe_override: Optional[AsyncPipe] = None
        self.kg_pipe_override: Optional[AsyncPipe] = None
        self.kg_storage_pipe_override: Optional[AsyncPipe] = None
        self.kg_search_pipe_override: Optional[AsyncPipe] = None
        self.kg_node_extraction_pipe_override: Optional[AsyncPipe] = None
        self.kg_node_description_pipe_override: Optional[AsyncPipe] = None
        self.kg_clustering_pipe_override: Optional[AsyncPipe] = None

        # Pipeline overrides
        self.ingestion_pipeline: Optional[IngestionPipeline] = None
        self.search_pipeline: Optional[SearchPipeline] = None
        self.rag_pipeline: Optional[RAGPipeline] = None
        self.streaming_rag_pipeline: Optional[RAGPipeline] = None
        self.kg_enrichment_pipeline: Optional[KGEnrichmentPipeline] = None

        # Agent overrides
        self.assistant_factory_override: Optional[R2RAgentFactory] = None
        self.rag_agent_override: Optional[R2RRAGAgent] = None

        # Service overrides
        self.auth_service_override: Optional["AuthService"] = None
        self.ingestion_service_override: Optional["IngestionService"] = None
        self.management_service_override: Optional["ManagementService"] = None
        self.retrieval_service_override: Optional["RetrievalService"] = None
        self.restructure_service_override: Optional["RestructureService"] = (
            None
        )

    def with_provider_factory(self, factory: Type[R2RProviderFactory]):
        self.provider_factory_override = factory
        return self

    def with_pipe_factory(self, factory: R2RPipeFactory):
        self.pipe_factory_override = factory
        return self

    def with_pipeline_factory(self, factory: R2RPipelineFactory):
        self.pipeline_factory_override = factory
        return self

    # Provider override methods
    def with_auth_provider(self, provider: AuthProvider):
        self.auth_provider_override = provider
        return self

    def with_database_provider(self, provider: DatabaseProvider):
        self.database_provider_override = provider
        return self

    def with_embedding_provider(self, provider: EmbeddingProvider):
        self.embedding_provider_override = provider
        return self

    def with_llm_provider(self, provider: CompletionProvider):
        self.llm_provider_override = provider
        return self

    def with_prompt_provider(self, provider: PromptProvider):
        self.prompt_provider_override = provider
        return self

    def with_kg_provider(self, provider: KGProvider):
        self.kg_provider_override = provider
        return self

    def with_crypto_provider(self, provider: CryptoProvider):
        self.crypto_provider_override = provider
        return self

    # Pipe override methods
    def with_parsing_pipe(self, pipe: AsyncPipe):
        self.parsing_pipe_override = pipe
        return self

    def with_embedding_pipe(self, pipe: AsyncPipe):
        self.embedding_pipe_override = pipe
        return self

    def with_vector_storage_pipe(self, pipe: AsyncPipe):
        self.vector_storage_pipe_override = pipe
        return self

    def with_vector_search_pipe(self, pipe: AsyncPipe):
        self.vector_search_pipe_override = pipe
        return self

    def with_rag_pipe(self, pipe: AsyncPipe):
        self.rag_pipe_override = pipe
        return self

    def with_streaming_rag_pipe(self, pipe: AsyncPipe):
        self.streaming_rag_pipe_override = pipe
        return self

    def with_kg_pipe(self, pipe: AsyncPipe):
        self.kg_pipe_override = pipe
        return self

    def with_kg_storage_pipe(self, pipe: AsyncPipe):
        self.kg_storage_pipe_override = pipe
        return self

    def with_kg_search_pipe(self, pipe: AsyncPipe):
        self.kg_search_pipe_override = pipe
        return self

    def with_kg_node_extraction_pipe(self, pipe: AsyncPipe):
        self.kg_node_extraction_pipe_override = pipe
        return self

    def with_kg_clustering_pipe(self, pipe: AsyncPipe):
        self.kg_clustering_pipe_override = pipe
        return self

    def with_kg_node_description_pipe(self, pipe: AsyncPipe):
        self.kg_node_description_pipe_override = pipe
        return self

    # Pipeline override methods
    def with_ingestion_pipeline(self, pipeline: IngestionPipeline):
        self.ingestion_pipeline = pipeline
        return self

    def with_search_pipeline(self, pipeline: SearchPipeline):
        self.search_pipeline = pipeline
        return self

    def with_rag_pipeline(self, pipeline: RAGPipeline):
        self.rag_pipeline = pipeline
        return self

    def with_streaming_rag_pipeline(self, pipeline: RAGPipeline):
        self.streaming_rag_pipeline = pipeline
        return self

    def with_kg_enrichment_pipeline(self, pipeline: KGEnrichmentPipeline):
        self.kg_enrichment_pipeline = pipeline
        return self

    def with_assistant_factory(self, factory: R2RAgentFactory):
        self.assistant_factory_override = factory
        return self

    def with_rag_agent(self, agent: R2RRAGAgent):
        self.rag_agent_override = agent
        return self

    def with_auth_service(self, service: "AuthService"):
        self.auth_service_override = service
        return self

    def with_ingestion_service(self, service: "IngestionService"):
        self.ingestion_service_override = service
        return self

    def with_management_service(self, service: "ManagementService"):
        self.management_service_override = service
        return self

    def with_retrieval_service(self, service: "RetrievalService"):
        self.retrieval_service_override = service
        return self

    def with_restructure_service(self, service: "RestructureService"):
        self.restructure_service_override = service
        return self

    def build(self, *args, **kwargs) -> R2RApp:

        provider_factory = self.provider_factory_override or R2RProviderFactory
        pipe_factory = self.pipe_factory_override or R2RPipeFactory
        pipeline_factory = self.pipeline_factory_override or R2RPipelineFactory

        providers = provider_factory(self.config).create_providers(
            auth_provider_override=self.auth_provider_override,
            database_provider_override=self.database_provider_override,
            embedding_provider_override=self.embedding_provider_override,
            llm_provider_override=self.llm_provider_override,
            prompt_provider_override=self.prompt_provider_override,
            kg_provider_override=self.kg_provider_override,
            crypto_provider_override=self.crypto_provider_override,
            *args,
            **kwargs,
        )
        pipes = pipe_factory(self.config, providers).create_pipes(
            parsing_pipe_override=self.parsing_pipe_override,
            embedding_pipe_override=self.embedding_pipe_override,
            vector_storage_pipe_override=self.vector_storage_pipe_override,
            vector_search_pipe_override=self.vector_search_pipe_override,
            rag_pipe_override=self.rag_pipe_override,
            streaming_rag_pipe_override=self.streaming_rag_pipe_override,
            kg_pipe_override=self.kg_pipe_override,
            kg_storage_pipe_override=self.kg_storage_pipe_override,
            kg_search_pipe_override=self.kg_search_pipe_override,
            kg_node_extraction_pipe=self.kg_node_extraction_pipe_override,
            kg_node_description_pipe=self.kg_node_description_pipe_override,
            kg_clustering_pipe=self.kg_clustering_pipe_override,
            *args,
            **kwargs,
        )

        pipelines = pipeline_factory(self.config, pipes).create_pipelines(
            ingestion_pipeline=self.ingestion_pipeline,
            search_pipeline=self.search_pipeline,
            rag_pipeline=self.rag_pipeline,
            streaming_rag_pipeline=self.streaming_rag_pipeline,
            kg_enrichment_pipeline=self.kg_enrichment_pipeline,
            *args,
            **kwargs,
        )

        assistant_factory = self.assistant_factory_override or R2RAgentFactory(
            self.config, providers, pipelines
        )
        agents = assistant_factory.create_agents(
            rag_agent_override=self.rag_agent_override,
            *args,
            **kwargs,
        )
        run_singleton = RunLoggingSingleton()
        run_manager = RunManager(run_singleton)

        service_params = {
            "config": self.config,
            "providers": providers,
            "pipelines": pipelines,
            "agents": agents,
            "run_manager": run_manager,
            "logging_connection": run_singleton,
        }

        service_params = {
            "config": self.config,
            "providers": providers,
            "pipelines": pipelines,
            "agents": agents,
            "run_manager": run_manager,
            "logging_connection": run_singleton,
        }

        auth_service = self.auth_service_override or AuthService(
            **service_params
        )
        ingestion_service = (
            self.ingestion_service_override
            or IngestionService(**service_params)
        )
        management_service = (
            self.management_service_override
            or ManagementService(**service_params)
        )
        retrieval_service = (
            self.retrieval_service_override
            or RetrievalService(**service_params)
        )
        restructure_service = (
            self.restructure_service_override
            or RestructureService(**service_params)
        )

        auth_router = AuthRouter(auth_service).get_router()
        ingestion_router = IngestionRouter(ingestion_service).get_router()
        management_router = ManagementRouter(management_service).get_router()
        retrieval_router = RetrievalRouter(retrieval_service).get_router()
        restructure_router = RestructureRouter(
            restructure_service
        ).get_router()

        return R2RApp(
            config=self.config,
            auth_router=auth_router,
            ingestion_service=ingestion_service,
            ingestion_router=ingestion_router,
            management_router=management_router,
            retrieval_router=retrieval_router,
            restructure_router=restructure_router,
        )
