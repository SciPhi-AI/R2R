from pydantic import BaseModel

from r2r.core import (
    EmbeddingProvider,
    LLMProvider,
    Pipeline,
    PipeLoggingConnectionSingleton,
    PromptProvider,
    R2RConfig,
    RecursiveCharacterTextSplitter,
    VectorDBProvider,
)
from r2r.main.app import R2RApp
from r2r.pipes import (
    DefaultDocumentParsingPipe,
    DefaultEmbeddingPipe,
    DefaultQueryTransformPipe,
    DefaultRAGPipe,
    DefaultSearchCollectorPipe,
    DefaultVectorSearchPipe,
    DefaultVectorStoragePipe,
)


class R2RProviders(BaseModel):
    vector_db: VectorDBProvider
    embedding: EmbeddingProvider
    llm: LLMProvider
    prompt: PromptProvider

    class Config:
        arbitrary_types_allowed = True


class R2RProviderFactory:
    def __init__(self, config: R2RConfig):
        self.config = config

    def get_vector_db_provider(self, *args, **kwargs) -> VectorDBProvider:
        vector_db_config = self.config.vector_database
        vector_db_provider = None
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
        vector_db_provider.initialize_collection(
            self.config.embedding.search_dimension
        )
        return vector_db_provider

    def get_embedding_provider(self, *args, **kwargs) -> EmbeddingProvider:
        embedding_config = self.config.embedding
        embedding_provider = None
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
        return embedding_provider

    def get_llm_provider(self, *args, **kwargs) -> LLMProvider:
        llm_config = self.config.language_model
        llm_provider = None
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
        return llm_provider

    def get_prompt_provider(self, *args, **kwargs) -> PromptProvider:
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

    def get_providers(self) -> R2RProviders:
        return R2RProviders(
            vector_db=self.get_vector_db_provider(),
            embedding=self.get_embedding_provider(),
            llm=self.get_llm_provider(),
            prompt=self.get_prompt_provider(),
        )


def app_factory(config: R2RConfig, providers: R2RProviders) -> R2RApp:
    text_splitter_config = config.embedding.extra_fields.get("text_splitter")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=text_splitter_config["chunk_size"],
        chunk_overlap=text_splitter_config["chunk_overlap"],
        length_function=len,
        is_separator_regex=False,
    )

    collector_pipe = DefaultSearchCollectorPipe()
    embedding_pipe = DefaultEmbeddingPipe(
        embedding_provider=providers.embedding,
        vector_db_provider=providers.vector_db,
        text_splitter=text_splitter,
        embedding_batch_size=128,
    )
    parsing_pipe = DefaultDocumentParsingPipe()
    query_transform_pipe = DefaultQueryTransformPipe(
        llm_provider=providers.llm,
        prompt_provider=providers.prompt,
    )
    rag_pipe = DefaultRAGPipe(
        llm_provider=providers.llm,
        prompt_provider=providers.prompt,
    )
    search_pipe = DefaultVectorSearchPipe(
        vector_db_provider=providers.vector_db,
        embedding_provider=providers.embedding,
    )
    vector_storage_pipe = DefaultVectorStoragePipe(
        vector_db_provider=providers.vector_db
    )

    ingestion_pipeline = Pipeline()
    ingestion_pipeline.add_pipe(parsing_pipe)
    ingestion_pipeline.add_pipe(embedding_pipe)
    ingestion_pipeline.add_pipe(vector_storage_pipe)

    search_pipeline = Pipeline()
    search_pipeline.add_pipe(search_pipe)

    rag_pipeline = Pipeline()
    rag_pipeline.add_pipe(query_transform_pipe)
    rag_pipeline.add_pipe(search_pipe)
    rag_pipeline.add_pipe(collector_pipe)
    rag_pipeline.add_pipe(
        rag_pipe,
        add_upstream_outputs=[
            {
                "prev_pipe_name": collector_pipe.config.name,
                "prev_output_field": "search_context",
                "input_field": "context",
            }
        ],
    )
    return R2RApp(
        ingestion_pipeline=ingestion_pipeline,
        search_pipeline=search_pipeline,
        rag_pipeline=rag_pipeline,
    )
