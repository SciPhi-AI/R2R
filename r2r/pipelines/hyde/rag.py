import logging
from typing import Optional

from r2r.core import (
    EmbeddingProvider,
    GenerationConfig,
    LLMProvider,
    LoggingDatabaseConnection,
    PromptProvider,
    RAGPipeline,
    RAGPipelineOutput,
    VectorDBProvider,
    VectorSearchResult,
    log_execution_to_db,
)

from ...prompts.local.prompt import BasicPromptProvider

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."
DEFAULT_RETURN_PROMPT = """
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
DEFAULT_HYDE_PROMPT = """
### Instruction:

Given the following query that follows to write a double newline separated list of up to {num_answers} single paragraph attempted answers. 
DO NOT generate any single answer which is likely to require information from multiple distinct documents, 
EACH single answer will be used to carry out a cosine similarity semantic search over distinct indexed documents, such as varied medical documents. 
FOR EXAMPLE if asked `how do the key themes of Great Gatsby compare with 1984`, the two attempted answers would be 
`The key themes of Great Gatsby are ... ANSWER_CONTINUED` and `The key themes themes of 1984 are ... ANSWER_CONTINUED`, where `ANSWER_CONTINUED` IS TO BE COMPLETED BY YOU in your response. 
Here is the original user query to be transformed into answers:

### Query:
{message}

### Response:
"""


class HyDEPipeline(RAGPipeline):
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        llm_provider: LLMProvider,
        vector_db_provider: VectorDBProvider,
        prompt_provider: Optional[PromptProvider] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT,
        return_pompt: Optional[str] = DEFAULT_RETURN_PROMPT,
        hyde_prompt: Optional[str] = DEFAULT_HYDE_PROMPT,
    ) -> None:
        logger.info(f"Initalizing `HydePipeline` to process user requests.")

        if not prompt_provider:
            prompt_provider = BasicPromptProvider
        self.prompt_provider = prompt_provider(system_prompt, return_pompt)
        self.prompt_provider.add_prompt("hyde_prompt", hyde_prompt)

        super().__init__(
            llm_provider=llm_provider,
            vector_db_provider=vector_db_provider,
            embedding_provider=embedding_provider,
            logging_connection=logging_connection,
            prompt_provider=self.prompt_provider,
        )

    def transform_message(self, message: str, generation_config: GenerationConfig) -> list[str]:  # type: ignore
        """
        Transforms the message into a list of hypothetical queries.
        """
        orig_stream = generation_config.stream
        generation_config.stream = False

        num_answers = generation_config.add_generation_kwargs.get(
            "num_answers", "three"
        )

        formatted_prompt = self.prompt_provider.get_prompt(
            "hyde_prompt", {"message": message, "num_answers": num_answers}
        )

        completion = self.generate_completion(
            formatted_prompt, generation_config
        )
        queries = completion.choices[0].message.content.strip().split("\n\n")
        generation_config.stream = orig_stream
        return queries

    @log_execution_to_db
    def construct_context(
        self,
        results: list[VectorSearchResult],
        offset: int,
        query: str,
        *args,
        **kwargs,
    ) -> str:
        return f"## Query:\n{query}\n\n## Context:\n{self._format_results(results, offset)}\n\n"

    def _format_results(
        self, results: list[VectorSearchResult], start=1
    ) -> str:
        context = ""
        for i, ele in enumerate(results, start=start):
            context += f"[{i+start}] {ele.metadata['text']}\n\n"

        return context

    # Modifies `HydePipeline` run to return search_results and completion
    def run(
        self,
        message,
        filters={},
        search_limit=25,
        rerank_limit=15,
        search_only=False,
        generation_config: Optional[GenerationConfig] = None,
        *args,
        **kwargs,
    ):
        """
        Runs the completion pipeline.
        """
        if not generation_config:
            generation_config = GenerationConfig(model="gpt-3.5-turbo")

        self.initialize_pipeline(message, search_only)

        queries = self.transform_message(message, generation_config)
        search_results_tuple = [
            (
                query,
                self.rerank_results(
                    query,
                    self.search(query, filters, search_limit),
                    rerank_limit,
                ),
            )
            for query in queries
        ]

        if search_only:
            flattened_results = [
                result for _, search_results in search_results_tuple for result in search_results
            ]

            return RAGPipelineOutput(
                flattened_results,
                None,
                None,
                {"queries": queries},
            )

        context = ""
        for offset, (query, search_results) in enumerate(search_results_tuple):
            context += self.construct_context(search_results, offset=offset, query=query) + "\n\n"

        prompt = self.construct_prompt({"query": query, "context": context})

        if not generation_config.stream:
            completion = self.generate_completion(prompt, generation_config)
            return RAGPipelineOutput(search_results, context, completion, {"queries": queries})

        return self._return_stream(
            search_results, context, prompt, generation_config, metadata={"queries": queries},
        )
