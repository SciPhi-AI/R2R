import os
from typing import Optional, Type

from r2r.base import (
    AsyncPipe,
    EmbeddingProvider,
    EvalProvider,
    LLMProvider,
    PromptProvider,
    VectorDBProvider,
)
from r2r.pipelines import (
    EvalPipeline,
    IngestionPipeline,
    RAGPipeline,
    SearchPipeline,
)

from ..app import R2RApp
from ..engine import R2REngine
from ..r2r import R2R
from .config import R2RConfig
from .factory import R2RPipeFactory, R2RPipelineFactory, R2RProviderFactory


class R2RBuilder:
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
        "neo4j_kg": os.path.join(config_root, "neo4j_kg.json"),
        "postgres_logging": os.path.join(config_root, "postgres_logging.json"),
    }

    @staticmethod
    def _get_config(config_name):
        if config_name is None:
            return R2RConfig.from_json()
        if config_name in R2RBuilder.CONFIG_OPTIONS:
            return R2RConfig.from_json(R2RBuilder.CONFIG_OPTIONS[config_name])
        raise ValueError(f"Invalid config name: {config_name}")

    def __init__(
        self,
        config: Optional[R2RConfig] = None,
        from_config: Optional[str] = None,
    ):
        if config and from_config:
            raise ValueError("Cannot specify both config and config_name")
        self.config = config or R2RBuilder._get_config(from_config)
        self.r2r_app_override: Optional[Type[R2REngine]] = None
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
        self.parsing_pipe_override: Optional[AsyncPipe] = None
        self.embedding_pipe_override: Optional[AsyncPipe] = None
        self.vector_storage_pipe_override: Optional[AsyncPipe] = None
        self.vector_search_pipe_override: Optional[AsyncPipe] = None
        self.rag_pipe_override: Optional[AsyncPipe] = None
        self.streaming_rag_pipe_override: Optional[AsyncPipe] = None
        self.eval_pipe_override: Optional[AsyncPipe] = None
        self.ingestion_pipeline: Optional[IngestionPipeline] = None
        self.search_pipeline: Optional[SearchPipeline] = None
        self.rag_pipeline: Optional[RAGPipeline] = None
        self.streaming_rag_pipeline: Optional[RAGPipeline] = None
        self.eval_pipeline: Optional[EvalPipeline] = None

    def with_app(self, app: Type[R2REngine]):
        self.r2r_app_override = app
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

    def with_eval_pipe(self, pipe: AsyncPipe):
        self.eval_pipe_override = pipe
        return self

    def with_ingestion_pipeline(self, pipeline: IngestionPipeline):
        self.ingestion_pipeline = pipeline
        return self

    def with_vector_search_pipeline(self, pipeline: SearchPipeline):
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

    def build(self, *args, **kwargs) -> R2R:
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
            vector_search_pipe_override=self.vector_search_pipe_override,
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

        engine = (self.r2r_app_override or R2REngine)(
            self.config, providers, pipelines
        )
        r2r_app = R2RApp(engine)
        return R2R(engine=engine, app=r2r_app)
