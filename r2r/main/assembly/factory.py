import logging
import os
from typing import Any, Optional

from r2r.base import (
    AsyncPipe,
    EmbeddingConfig,
    EmbeddingProvider,
    EvalProvider,
    KGProvider,
    KVLoggingSingleton,
    LLMConfig,
    LLMProvider,
    PromptProvider,
    VectorDBConfig,
    VectorDBProvider,
)
from r2r.pipelines import (
    EvalPipeline,
    IngestionPipeline,
    RAGPipeline,
    SearchPipeline,
)

from ..abstractions import R2RPipelines, R2RPipes, R2RProviders
from .config import R2RConfig

logger = logging.getLogger(__name__)


class R2RProviderFactory:
    def __init__(self, config: R2RConfig):
        self.config = config

    def create_vector_db_provider(
        self, vector_db_config: VectorDBConfig, *args, **kwargs
    ) -> VectorDBProvider:
        vector_db_provider: Optional[VectorDBProvider] = None
        if vector_db_config.provider == "pgvector":
            from r2r.providers.vector_dbs import PGVectorDB

            vector_db_provider = PGVectorDB(vector_db_config)
        else:
            raise ValueError(
                f"Vector database provider {vector_db_config.provider} not supported"
            )
        if not vector_db_provider:
            raise ValueError("Vector database provider not found")

        if not self.config.embedding.base_dimension:
            raise ValueError("Search dimension not found in embedding config")

        vector_db_provider.initialize_collection(
            self.config.embedding.base_dimension
        )
        return vector_db_provider

    def create_embedding_provider(
        self, embedding: EmbeddingConfig, *args, **kwargs
    ) -> EmbeddingProvider:
        embedding_provider: Optional[EmbeddingProvider] = None

        if embedding.provider == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError(
                    "Must set OPENAI_API_KEY in order to initialize OpenAIEmbeddingProvider."
                )
            from r2r.providers.embeddings import OpenAIEmbeddingProvider

            embedding_provider = OpenAIEmbeddingProvider(embedding)
        elif embedding.provider == "ollama":
            from r2r.providers.embeddings import OllamaEmbeddingProvider

            embedding_provider = OllamaEmbeddingProvider(embedding)

        elif embedding.provider == "sentence-transformers":
            from r2r.providers.embeddings import (
                SentenceTransformerEmbeddingProvider,
            )

            embedding_provider = SentenceTransformerEmbeddingProvider(
                embedding
            )
        elif embedding is None:
            embedding_provider = None
        else:
            raise ValueError(
                f"Embedding provider {embedding.provider} not supported"
            )

        return embedding_provider

    def create_eval_provider(
        self, eval_config, prompt_provider, *args, **kwargs
    ) -> Optional[EvalProvider]:
        if eval_config.provider == "local":
            from r2r.providers.eval import LLMEvalProvider

            llm_provider = self.create_llm_provider(eval_config.llm)
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

    def create_llm_provider(
        self, llm_config: LLMConfig, *args, **kwargs
    ) -> LLMProvider:
        llm_provider: Optional[LLMProvider] = None
        if llm_config.provider == "openai":
            from r2r.providers.llms import OpenAILLM

            llm_provider = OpenAILLM(llm_config)
        elif llm_config.provider == "litellm":
            from r2r.providers.llms import LiteLLM

            llm_provider = LiteLLM(llm_config)
        else:
            raise ValueError(
                f"Language model provider {llm_config.provider} not supported"
            )
        if not llm_provider:
            raise ValueError("Language model provider not found")
        return llm_provider

    def create_prompt_provider(
        self, prompt_config, *args, **kwargs
    ) -> PromptProvider:
        prompt_provider = None
        if prompt_config.provider == "local":
            from r2r.prompts import R2RPromptProvider

            prompt_provider = R2RPromptProvider()
        else:
            raise ValueError(
                f"Prompt provider {prompt_config.provider} not supported"
            )
        return prompt_provider

    def create_kg_provider(self, kg_config, *args, **kwargs):
        if kg_config.provider == "neo4j":
            from r2r.providers.kg import Neo4jKGProvider

            return Neo4jKGProvider(kg_config)
        elif kg_config.provider is None:
            return None
        else:
            raise ValueError(
                f"KG provider {kg_config.provider} not supported."
            )

    def create_providers(
        self,
        vector_db_provider_override: Optional[VectorDBProvider] = None,
        embedding_provider_override: Optional[EmbeddingProvider] = None,
        eval_provider_override: Optional[EvalProvider] = None,
        llm_provider_override: Optional[LLMProvider] = None,
        prompt_provider_override: Optional[PromptProvider] = None,
        kg_provider_override: Optional[KGProvider] = None,
        *args,
        **kwargs,
    ) -> R2RProviders:
        prompt_provider = (
            prompt_provider_override
            or self.create_prompt_provider(self.config.prompt, *args, **kwargs)
        )
        return R2RProviders(
            vector_db=vector_db_provider_override
            or self.create_vector_db_provider(
                self.config.vector_database, *args, **kwargs
            ),
            embedding=embedding_provider_override
            or self.create_embedding_provider(
                self.config.embedding, *args, **kwargs
            ),
            eval=eval_provider_override
            or self.create_eval_provider(
                self.config.eval,
                prompt_provider=prompt_provider,
                *args,
                **kwargs,
            ),
            llm=llm_provider_override
            or self.create_llm_provider(
                self.config.completions, *args, **kwargs
            ),
            prompt=prompt_provider_override
            or self.create_prompt_provider(
                self.config.prompt, *args, **kwargs
            ),
            kg=kg_provider_override
            or self.create_kg_provider(self.config.kg, *args, **kwargs),
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
        kg_agent_pipe_override: Optional[AsyncPipe] = None,
        vector_storage_pipe_override: Optional[AsyncPipe] = None,
        vector_search_pipe_override: Optional[AsyncPipe] = None,
        rag_pipe_override: Optional[AsyncPipe] = None,
        streaming_rag_pipe_override: Optional[AsyncPipe] = None,
        eval_pipe_override: Optional[AsyncPipe] = None,
        *args,
        **kwargs,
    ) -> R2RPipes:
        return R2RPipes(
            parsing_pipe=parsing_pipe_override
            or self.create_parsing_pipe(
                self.config.ingestion.get("excluded_parsers"), *args, **kwargs
            ),
            embedding_pipe=embedding_pipe_override
            or self.create_embedding_pipe(*args, **kwargs),
            kg_pipe=kg_pipe_override or self.create_kg_pipe(*args, **kwargs),
            kg_storage_pipe=kg_storage_pipe_override
            or self.create_kg_storage_pipe(*args, **kwargs),
            kg_agent_search_pipe=kg_agent_pipe_override
            or self.create_kg_agent_pipe(*args, **kwargs),
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
        )

    def create_parsing_pipe(
        self, excluded_parsers: Optional[list] = None, *args, **kwargs
    ) -> Any:
        from r2r.pipes import ParsingPipe

        return ParsingPipe(excluded_parsers=excluded_parsers or [])

    def create_embedding_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        from r2r.base import RecursiveCharacterTextSplitter
        from r2r.pipes import EmbeddingPipe

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
        return EmbeddingPipe(
            embedding_provider=self.providers.embedding,
            vector_db_provider=self.providers.vector_db,
            text_splitter=text_splitter,
            embedding_batch_size=self.config.embedding.batch_size,
        )

    def create_vector_storage_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        from r2r.pipes import VectorStoragePipe

        return VectorStoragePipe(vector_db_provider=self.providers.vector_db)

    def create_vector_search_pipe(self, *args, **kwargs) -> Any:
        if self.config.embedding.provider is None:
            return None

        from r2r.pipes import VectorSearchPipe

        return VectorSearchPipe(
            vector_db_provider=self.providers.vector_db,
            embedding_provider=self.providers.embedding,
        )

    def create_kg_pipe(self, *args, **kwargs) -> Any:
        if self.config.kg.provider is None:
            return None

        from r2r.base import RecursiveCharacterTextSplitter
        from r2r.pipes import KGExtractionPipe

        text_splitter_config = self.config.kg.extra_fields.get("text_splitter")
        if not text_splitter_config:
            raise ValueError("Text splitter config not found in kg config.")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=text_splitter_config["chunk_size"],
            chunk_overlap=text_splitter_config["chunk_overlap"],
            length_function=len,
            is_separator_regex=False,
        )
        return KGExtractionPipe(
            kg_provider=self.providers.kg,
            llm_provider=self.providers.llm,
            prompt_provider=self.providers.prompt,
            vector_db_provider=self.providers.vector_db,
            text_splitter=text_splitter,
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

    def create_kg_agent_pipe(self, *args, **kwargs) -> Any:
        if self.config.kg.provider is None:
            return None

        from r2r.pipes import KGAgentSearchPipe

        return KGAgentSearchPipe(
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
        # Add embedding pipes if provider is set
        if self.config.embedding.provider is not None:
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
            and self.config.vector_database.provider is not None
        ):
            search_pipeline.add_pipe(
                self.pipes.vector_search_pipe, vector_search_pipe=True
            )

        # Add KG pipes if provider is set
        if self.config.kg.provider is not None:
            search_pipeline.add_pipe(
                self.pipes.kg_agent_search_pipe, kg_pipe=True
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
            logger.warn(f"Error configuring logging: {e}")
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
