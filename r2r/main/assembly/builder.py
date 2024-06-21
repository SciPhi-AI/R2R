import os
from typing import Optional, Type

from r2r import (
    EmbeddingProvider,
    EvalPipeline,
    EvalProvider,
    IngestionPipeline,
    LLMProvider,
    LoggableAsyncPipe,
    PromptProvider,
    RAGPipeline,
    SearchPipeline,
    VectorDBProvider,
)

from ..app import R2RApp
from .config import R2RConfig
from .factory import R2RPipeFactory, R2RPipelineFactory, R2RProviderFactory


class R2RAppBuilder:
    current_file_path = os.path.dirname(__file__)
    config_root = os.path.join(
        current_file_path, "..", "..", "examples", "configs"
    )
    CONFIG_OPTIONS = {
        "default": None,
        "local_ollama": os.path.join(config_root, "local_ollama.json"),
        "local_ollama_rerank": os.path.join(
            config_root, "local_ollama_rerank.json"
        ),
        "pgvector": os.path.join(config_root, "pgvector.json"),
        "neo4j_kg": os.path.join(config_root, "neo4j_kg.json"),
        "postgres_logging": os.path.join(config_root, "postgres_logging.json"),
    }

    @staticmethod
    def _get_config(config_name):
        if config_name is None:
            return R2RConfig.from_json()
        if config_path := R2RAppBuilder.CONFIG_OPTIONS.get(config_name):
            return R2RConfig.from_json(config_path)
        raise ValueError(f"Invalid config name: {config_name}")

    def __init__(
        self,
        config: Optional[R2RConfig] = None,
        from_config: Optional[str] = None,
    ):
        if config and from_config:
            raise ValueError("Cannot specify both config and config_name")
        self.config = config or R2RAppBuilder._get_config(from_config)
        self.r2r_app_override: Optional[Type[R2RApp]] = None
        self.provider_factory_override: Optional[Type[R2RProviderFactory]] = (
            None
        )
        self.pipe_factory_override: Optional[R2RPipeFactory] = None
        self.pipeline_factory_override: Optional[R2RPipelineFactory] = None
        self.vector_db_provider_override: Optional[VectorDBProvider] = None
        self.embedding_provider_override: Optional[EmbeddingProvider] = None
        self.eval_provider_override: Optional[EvalProvider] = None
        self.llm_provider_override: Optional[LLMProvider] = None
        self.prompt_provider_override: Optional[PromptProvider] = None
        self.parsing_pipe_override: Optional[LoggableAsyncPipe] = None
        self.embedding_pipe_override: Optional[LoggableAsyncPipe] = None
        self.vector_storage_pipe_override: Optional[LoggableAsyncPipe] = None
        self.search_pipe_override: Optional[LoggableAsyncPipe] = None
        self.rag_pipe_override: Optional[LoggableAsyncPipe] = None
        self.streaming_rag_pipe_override: Optional[LoggableAsyncPipe] = None
        self.eval_pipe_override: Optional[LoggableAsyncPipe] = None
        self.ingestion_pipeline: Optional[IngestionPipeline] = None
        self.search_pipeline: Optional[SearchPipeline] = None
        self.rag_pipeline: Optional[RAGPipeline] = None
        self.streaming_rag_pipeline: Optional[RAGPipeline] = None
        self.eval_pipeline: Optional[EvalPipeline] = None

    def with_app(self, r2r_app: Type[R2RApp]):
        self.r2r_app_override = r2r_app
        return self

    def with_provider_factory(self, factory: Type[R2RProviderFactory]):
        self.provider_factory_override = factory
        return self

    def with_pipe_factory(self, factory: R2RPipeFactory):
        self.pipe_factory_override = factory
        return self

    def with_pipeline_factory(self, factory: R2RPipelineFactory):
        self.pipeline_factory_override = factory
        return self

    def with_vector_db_provider(self, provider: VectorDBProvider):
        self.vector_db_provider_override = provider
        return self

    def with_embedding_provider(self, provider: EmbeddingProvider):
        self.embedding_provider_override = provider
        return self

    def with_eval_provider(self, provider: EvalProvider):
        self.eval_provider_override = provider
        return self

    def with_llm_provider(self, provider: LLMProvider):
        self.llm_provider_override = provider
        return self

    def with_prompt_provider(self, provider: PromptProvider):
        self.prompt_provider_override = provider
        return self

    def with_parsing_pipe(self, pipe: LoggableAsyncPipe):
        self.parsing_pipe_override = pipe
        return self

    def with_embedding_pipe(self, pipe: LoggableAsyncPipe):
        self.embedding_pipe_override = pipe
        return self

    def with_vector_storage_pipe(self, pipe: LoggableAsyncPipe):
        self.vector_storage_pipe_override = pipe
        return self

    def with_search_pipe(self, pipe: LoggableAsyncPipe):
        self.search_pipe_override = pipe
        return self

    def with_rag_pipe(self, pipe: LoggableAsyncPipe):
        self.rag_pipe_override = pipe
        return self

    def with_streaming_rag_pipe(self, pipe: LoggableAsyncPipe):
        self.streaming_rag_pipe_override = pipe
        return self

    def with_eval_pipe(self, pipe: LoggableAsyncPipe):
        self.eval_pipe_override = pipe
        return self

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

    def with_eval_pipeline(self, pipeline: EvalPipeline):
        self.eval_pipeline = pipeline
        return self

    def build(self, *args, **kwargs) -> R2RApp:
        provider_factory = self.provider_factory_override or R2RProviderFactory
        pipe_factory = self.pipe_factory_override or R2RPipeFactory
        pipeline_factory = self.pipeline_factory_override or R2RPipelineFactory

        providers = provider_factory(self.config).create_providers(
            vector_db_provider_override=self.vector_db_provider_override,
            embedding_provider_override=self.embedding_provider_override,
            eval_provider_override=self.eval_provider_override,
            llm_provider_override=self.llm_provider_override,
            prompt_provider_override=self.prompt_provider_override,
            *args,
            **kwargs,
        )

        pipes = pipe_factory(self.config, providers).create_pipes(
            parsing_pipe_override=self.parsing_pipe_override,
            embedding_pipe_override=self.embedding_pipe_override,
            vector_storage_pipe_override=self.vector_storage_pipe_override,
            search_pipe_override=self.search_pipe_override,
            rag_pipe_override=self.rag_pipe_override,
            streaming_rag_pipe_override=self.streaming_rag_pipe_override,
            eval_pipe_override=self.eval_pipe_override,
            *args,
            **kwargs,
        )

        pipelines = pipeline_factory(self.config, pipes).create_pipelines(
            ingestion_pipeline=self.ingestion_pipeline,
            search_pipeline=self.search_pipeline,
            rag_pipeline=self.rag_pipeline,
            streaming_rag_pipeline=self.streaming_rag_pipeline,
            eval_pipeline=self.eval_pipeline,
            *args,
            **kwargs,
        )

        r2r_app = self.r2r_app_override or R2RApp
        return r2r_app(self.config, providers, pipelines)
