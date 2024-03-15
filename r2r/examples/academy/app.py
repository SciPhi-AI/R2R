import logging
from typing import Optional

from r2r.core import (
    GenerationConfig,
    LLMProvider,
    LoggingDatabaseConnection,
    PromptProvider,
    RAGPipelineOutput,
    VectorDBProvider,
    VectorSearchResult,
    log_execution_to_db,
)
from r2r.embeddings import OpenAIEmbeddingProvider
from r2r.main import E2EPipelineFactory, R2RConfig
from r2r.pipelines import BasicPromptProvider, BasicRAGPipeline

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."
DEFAULT_TASK_PROMPT = """
## Task:
Answer the query given immediately below given the context which follows later. Use line item references to like [1], [2], ... refer to specifically numbered items in the provided context. Pay close attention to the title of each given source to ensure it is consistent with the query.

### Query:
{query}

### Context:
{context}

### Query:
{query}

REMINDER - Use line item references to like [1], [2], ... refer to specifically numbered items in the provided context.
## Response:
"""


class SyntheticRAGPipeline(BasicRAGPipeline):
    def __init__(
        self,
        llm: LLMProvider,
        db: VectorDBProvider,
        embedding_model: str,
        embeddings_provider: OpenAIEmbeddingProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        prompt_provider: Optional[PromptProvider] = BasicPromptProvider(
            DEFAULT_SYSTEM_PROMPT, DEFAULT_TASK_PROMPT
        ),
    ) -> None:
        logger.debug(f"Initalizing `SyntheticRAGPipeline`")

        super().__init__(
            llm,
            db,
            embedding_model,
            embeddings_provider,
            logging_connection=logging_connection,
            prompt_provider=prompt_provider,
        )

    def transform_query(self, query: str, generation_config: GenerationConfig) -> list[str]:  # type: ignore
        """
        Transforms the query into a list of strings.
        """
        print(f"Transforming query: {query}")
        prompt = (
            "Use the query that follows to write a comma separated three queries "
            "that will be used to retrieve the relevant materials. DO NOT generate "
            "queries which require multiple document types. E.g. ask for `lecture notes "
            "with information about X` or `readings that cover topic Y`.\n\n## Query:\n"
            "{query}\n\n## Response:".format(query=query)
        )
        generation_config.stream = False
        completion = self.generate_completion(prompt, generation_config)
        transformed_queries = (
            completion.choices[0].message.content.strip().split("\n")
        )
        print(f"Transformed Queries: {transformed_queries}")
        return transformed_queries

    @log_execution_to_db
    def search(
        self,
        transformed_query: str,
        filters: dict,
        limit: int,
    ) -> list[VectorSearchResult]:
        logger.debug(f"Retrieving results for query: {transformed_query}")

        results = self.db.search(
            query_vector=self.embeddings_provider.get_embedding(
                transformed_query,
                self.embedding_model,
            ),
            filters=filters,
            limit=limit,
        )
        logger.debug(f"Retrieved the raw results shown:\n{results}\n")
        return results

    @log_execution_to_db
    def construct_context(
        self,
        results: list,
    ) -> str:
        queries = [ele[0] for ele in results]
        search_results = [ele[1] for ele in results]
        reranked_results = [
            self.rerank_results(search_result)
            for search_result in search_results
        ]
        context = ""
        offset = 1
        for query, results in zip(queries, reranked_results):
            context += f"## Query:\n{query}\n\n## Context:\n{self._format_results(results, offset)}\n\n"
            offset += len(results)
        return context

    # Modifies `SyntheticRAGPipeline` run to return search_results and completion
    def run(
        self,
        query,
        filters={},
        limit=5,
        search_only=False,
        generation_config: Optional[GenerationConfig] = None,
    ):
        """
        Runs the completion pipeline.
        """
        if not generation_config:
            generation_config = GenerationConfig(model="gpt-3.5-turbo")

        self.initialize_pipeline(query, search_only)
        transformed_queries = self.transform_query(query, generation_config)
        search_results = [
            (transformed_query, self.search(transformed_query, filters, limit))
            for transformed_query in transformed_queries
        ]
        if search_only:
            return RAGPipelineOutput(search_results, None, None)

        context = self.construct_context(search_results)
        prompt = self.construct_prompt({"query": query, "context": context})

        if not generation_config.stream:
            completion = self.generate_completion(prompt, generation_config)
            return RAGPipelineOutput(search_results, context, completion)

        return self._stream_run(
            search_results, context, prompt, generation_config
        )

    def _format_results(
        self, results: list[VectorSearchResult], start=1
    ) -> str:
        context = ""
        for i, ele in enumerate(results, start=start):
            context += f"[{i+start}] {ele.metadata['text']}\n\n"

        return context


# Creates a pipeline using the `E2EPipelineFactory`
app = E2EPipelineFactory.create_pipeline(
    config=R2RConfig.load_config(), rag_pipeline_impl=SyntheticRAGPipeline
)
