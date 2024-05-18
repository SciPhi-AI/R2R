from typing import Any, Optional

from pydantic import BaseModel

from r2r.core import (
    EmbeddingProvider,
    IngestionPipeline,
    LLMProvider,
    PipeLoggingConnectionSingleton,
    PromptProvider,
    R2RConfig,
    RAGPipeline,
    SearchPipeline,
    VectorDBProvider,
)


class R2RProviders(BaseModel):
    vector_db: VectorDBProvider
    embedding: EmbeddingProvider
    llm: LLMProvider
    prompt: PromptProvider

    class Config:
        arbitrary_types_allowed = True


class R2RPipelines(BaseModel):
    ingestion_pipeline: IngestionPipeline
    search_pipeline: SearchPipeline
    rag_pipeline: RAGPipeline
    streaming_rag_pipeline: RAGPipeline

    class Config:
        arbitrary_types_allowed = True


class R2RProviderFactory:
    def __init__(self, config: R2RConfig):
        self.config = config

    def create_vector_db_provider(self, *args, **kwargs) -> VectorDBProvider:
        vector_db_config = self.config.vector_database
        vector_db_provider: Optional[VectorDBProvider] = None

        if vector_db_config.provider == "qdrant":
            from r2r.vector_dbs import QdrantDB

            vector_db_provider = QdrantDB(vector_db_config)
        elif vector_db_config.provider == "pgvector":
            from r2r.vector_dbs import PGVectorDB

            vector_db_provider = PGVectorDB(vector_db_config)
        elif vector_db_config.provider == "local":
            from r2r.vector_dbs import LocalVectorDB

            vector_db_provider = LocalVectorDB(vector_db_config)
        else:
            raise ValueError(
                f"Vector database provider {vector_db_config.provider} not supported"
            )
        if not vector_db_provider:
            raise ValueError("Vector database provider not found")

        if not self.config.embedding.search_dimension:
            raise ValueError("Search dimension not found in embedding config")

        vector_db_provider.initialize_collection(
            self.config.embedding.search_dimension
        )
        return vector_db_provider

    def create_embedding_provider(self, *args, **kwargs) -> EmbeddingProvider:
        embedding_config = self.config.embedding
        embedding_provider: Optional[EmbeddingProvider] = None

        if embedding_config.provider == "openai":
            from r2r.embeddings import OpenAIEmbeddingProvider

            embedding_provider = OpenAIEmbeddingProvider(embedding_config)
        elif embedding_config.provider == "sentence-transformers":
            from r2r.embeddings import SentenceTransformerEmbeddingProvider

            embedding_provider = SentenceTransformerEmbeddingProvider(
                embedding_config
            )
        elif embedding_config.provider == "dummy":
            from r2r.embeddings import DummyEmbeddingProvider

            embedding_provider = DummyEmbeddingProvider(embedding_config)
        else:
            raise ValueError(
                f"Embedding provider {embedding_config.provider} not supported"
            )
        if not embedding_provider:
            raise ValueError("Embedding provider not found")

        return embedding_provider

    def create_llm_provider(self, *args, **kwargs) -> LLMProvider:
        llm_config = self.config.language_model
        llm_provider: Optional[LLMProvider] = None
        if llm_config.provider == "openai":
            from r2r.llms import OpenAILLM

            llm_provider = OpenAILLM(llm_config)
        elif llm_config.provider == "litellm":
            from r2r.llms import LiteLLM

            llm_provider = LiteLLM(llm_config)
        elif llm_config.provider == "llama-cpp":
            from r2r.llms import LlamaCPP, LlamaCppConfig

            config_dict = llm_config.dict()
            extra_args = config_dict.pop("extra_args")

            llm_provider = LlamaCPP(
                LlamaCppConfig(**{**config_dict, **extra_args})
            )
        else:
            raise ValueError(
                f"Language model provider {llm_config.provider} not supported"
            )
        if not llm_provider:
            raise ValueError("Language model provider not found")
        return llm_provider

    def create_prompt_provider(self, *args, **kwargs) -> PromptProvider:
        prompt_config = self.config.prompt
        prompt_provider = None
        if prompt_config.provider == "local":
            from r2r.prompts import DefaultPromptProvider

            prompt_provider = DefaultPromptProvider()
        else:
            raise ValueError(
                f"Prompt provider {prompt_config.provider} not supported"
            )
        return prompt_provider

    def create_providers(self) -> R2RProviders:
        return R2RProviders(
            vector_db=self.create_vector_db_provider(),
            embedding=self.create_embedding_provider(),
            llm=self.create_llm_provider(),
            prompt=self.create_prompt_provider(),
        )


class DefaultR2RPipelineFactory:
    def __init__(self, config: R2RConfig, providers: R2RProviders):
        self.config = config
        self.providers = providers

    def create_ingestion_pipeline(self) -> IngestionPipeline:
        from r2r.core import RecursiveCharacterTextSplitter
        from r2r.pipes import (
            DefaultDocumentParsingPipe,
            DefaultEmbeddingPipe,
            DefaultVectorStoragePipe,
        )

        text_splitter_config = self.config.embedding.extra_fields.get(
            "text_splitter"
        )

        if not text_splitter_config:
            raise ValueError(
                "Text splitter config not found in embedding config"
            )

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=text_splitter_config["chunk_size"],
            chunk_overlap=text_splitter_config["chunk_overlap"],
            length_function=len,
            is_separator_regex=False,
        )

        parsing_pipe = DefaultDocumentParsingPipe()
        embedding_pipe = DefaultEmbeddingPipe(
            embedding_provider=self.providers.embedding,
            vector_db_provider=self.providers.vector_db,
            text_splitter=text_splitter,
            embedding_batch_size=self.config.embedding.batch_size,
        )
        vector_storage_pipe = DefaultVectorStoragePipe(
            vector_db_provider=self.providers.vector_db
        )

        ingestion_pipeline = IngestionPipeline()
        ingestion_pipeline.add_pipe(parsing_pipe)
        ingestion_pipeline.add_pipe(embedding_pipe)
        ingestion_pipeline.add_pipe(vector_storage_pipe)
        return ingestion_pipeline

    def create_search_pipeline(self) -> SearchPipeline:
        from r2r.pipes import DefaultVectorSearchPipe

        search_pipe = DefaultVectorSearchPipe(
            vector_db_provider=self.providers.vector_db,
            embedding_provider=self.providers.embedding,
        )

        search_pipeline = SearchPipeline()
        search_pipeline.add_pipe(search_pipe)
        return search_pipeline

    def create_rag_pipeline(self, streaming: bool = False) -> RAGPipeline:
        from r2r.pipes import DefaultVectorSearchPipe

        search_pipe = DefaultVectorSearchPipe(
            vector_db_provider=self.providers.vector_db,
            embedding_provider=self.providers.embedding,
        )

        rag_pipe: Any = None
        if streaming:
            from r2r.pipes import DefaultStreamingRAGPipe

            rag_pipe = DefaultStreamingRAGPipe(
                llm_provider=self.providers.llm,
                prompt_provider=self.providers.prompt,
            )
        else:
            from r2r.pipes import DefaultRAGPipe

            rag_pipe = DefaultRAGPipe(
                llm_provider=self.providers.llm,
                prompt_provider=self.providers.prompt,
            )

        rag_pipeline = RAGPipeline()
        rag_pipeline.add_pipe(search_pipe)
        rag_pipeline.add_pipe(
            rag_pipe,
            add_upstream_outputs=[
                {
                    "prev_pipe_name": search_pipe.config.name,
                    "prev_output_field": "search_results",
                    "input_field": "raw_search_results",
                },
                {
                    "prev_pipe_name": search_pipe.config.name,
                    "prev_output_field": "search_queries",
                    "input_field": "query",
                },
            ],
        )
        return rag_pipeline

    def create_pipelines(
        self,
        ingestion_pipeline: Optional[IngestionPipeline] = None,
        search_pipeline: Optional[SearchPipeline] = None,
        rag_pipeline: Optional[RAGPipeline] = None,
        streaming_rag_pipeline: Optional[RAGPipeline] = None,
    ) -> R2RPipelines:
        return R2RPipelines(
            ingestion_pipeline=ingestion_pipeline
            or self.create_ingestion_pipeline(),
            search_pipeline=search_pipeline or self.create_search_pipeline(),
            rag_pipeline=rag_pipeline
            or self.create_rag_pipeline(streaming=False),
            streaming_rag_pipeline=streaming_rag_pipeline
            or self.create_rag_pipeline(streaming=True),
        )

    def configure_logging(self):
        PipeLoggingConnectionSingleton.configure(self.config.logging)
