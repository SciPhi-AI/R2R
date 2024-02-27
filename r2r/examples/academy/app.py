import logging
from typing import Optional

from r2r.core import (
    GenerationConfig,
    LLMProvider,
    LoggingDatabaseConnection,
    VectorDBProvider,
    VectorSearchResult,
    log_execution_to_db,
)
from r2r.embeddings import OpenAIEmbeddingProvider
from r2r.main import E2EPipelineFactory
from r2r.pipelines import BasicRAGPipeline

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
        generation_config: GenerationConfig,
        db: VectorDBProvider,
        embedding_model: str,
        embeddings_provider: OpenAIEmbeddingProvider,
        logging_provider: Optional[LoggingDatabaseConnection] = None,
        system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT,
        task_prompt: Optional[str] = DEFAULT_TASK_PROMPT,
    ) -> None:
        logger.debug(f"Initalizing `SyntheticRAGPipeline`")

        super().__init__(
            llm,
            generation_config,
            db,
            embedding_model,
            embeddings_provider,
            logging_provider=logging_provider,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
        )

    def transform_query(self, query: str) -> list[str]:  # type: ignore
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
        completion = self.generate_completion(prompt)
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
    def run(self, query, filters={}, limit=5, search_only=False):
        """
        Runs the completion pipeline.
        """
        self.initialize_pipeline(query, search_only)
        transformed_queries = self.transform_query(query)
        search_results = [
            (transformed_query, self.search(transformed_query, filters, limit))
            for transformed_query in transformed_queries
        ]
        if search_only:
            return search_results, None
        context = self.construct_context(search_results)
        prompt = self.construct_prompt({"query": query, "context": context})
        completion = self.generate_completion(prompt)
        return search_results, completion

    def _format_results(
        self, results: list[VectorSearchResult], start=1
    ) -> str:
        context = ""
        for i, ele in enumerate(results, start=start):
            context += f"[{i+start}] {ele.metadata['text']}\n\n"

        return context


# Creates a pipeline using the `E2EPipelineFactory`
app = E2EPipelineFactory.create_pipeline(
    rag_pipeline_impl=SyntheticRAGPipeline
)
