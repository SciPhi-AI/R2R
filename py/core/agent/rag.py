from typing import Any, Callable, Optional

import tiktoken

from core.agent import R2RAgent, R2RStreamingAgent
from core.base import (
    format_search_results_for_llm,
    format_search_results_for_stream,
)
from core.base.abstractions import (
    AggregateSearchResult,
    ContextDocumentResult,
    GenerationConfig,
    SearchSettings,
    WebSearchResponse,
)
from core.base.agent import AgentConfig, Tool
from core.base.providers import DatabaseProvider
from core.providers import (
    AnthropicCompletionProvider,
    LiteLLMCompletionProvider,
    OpenAICompletionProvider,
)


def num_tokens(text, model="gpt-4o"):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    """Return the number of tokens used by a list of messages for both user and assistant."""
    return len(encoding.encode(text))


class RAGAgentMixin:
    """
    A Mixin for adding local_search, web_search, and content tools
    to your R2R Agents. This allows your agent to:
      - call local_search_method (semantic/hybrid search)
      - call content_method (fetch entire doc/chunk structures)
      - call an external web search API
    """

    def __init__(
        self,
        *args,
        search_settings: SearchSettings,
        local_search_method: Optional[Callable] = None,
        content_method: Optional[Callable] = None,
        max_tool_context_length=10_000,
        **kwargs,
    ):
        # Save references to the retrieval logic
        self.search_settings = search_settings
        self.local_search_method = local_search_method
        self.content_method = content_method
        self.max_tool_context_length = max_tool_context_length
        super().__init__(*args, **kwargs)

    def _register_tools(self):
        """
        Called by the base agent to register all requested tools
        from self.config.tools.
        """
        if not self.config.tools:
            return
        for tool_name in set(self.config.tools):
            if tool_name == "content":
                self._tools.append(self.content())
            elif tool_name == "local_search":
                self._tools.append(self.local_search())
            elif tool_name == "web_search":
                self._tools.append(self.web_search())
            elif tool_name == "multi_search":
                self._tools.append(self.multi_search())
            else:
                raise ValueError(f"Unsupported tool name: {tool_name}")

    # ---------------------------------------------------------------------
    # 1) LOCAL SEARCH TOOL
    # ---------------------------------------------------------------------
    def local_search(self) -> Tool:
        """
        Tool to do a semantic/hybrid search on the local knowledge base
        using self.local_search_method.
        """
        return Tool(
            name="search",
            description=(
                "Search your local knowledge base using the R2R system. "
                "Use this when you want relevant text chunks or knowledge graph data."
            ),
            results_function=self._local_search_function,
            llm_format_function=self.format_search_results_for_llm,
            stream_function=self.format_search_results_for_stream,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User query to search in the local DB.",
                    },
                },
                "required": ["query"],
            },
        )

    async def _local_search_function(
        self,
        query: str,
        *args,
        **kwargs,
    ) -> AggregateSearchResult:
        """
        Calls the passed-in `local_search_method(query, search_settings)`.
        Expects either an AggregateSearchResult or a dict with chunk_search_results, etc.
        """
        if not self.local_search_method:
            raise ValueError(
                "No local_search_method provided to RAGAgentMixin."
            )

        response = await self.local_search_method(
            query=query, search_settings=self.search_settings
        )

        if isinstance(response, AggregateSearchResult):
            return response

        # If it's a dict, convert the response dict to an AggregateSearchResult
        return AggregateSearchResult(
            chunk_search_results=response.get("chunk_search_results", []),
            graph_search_results=response.get("graph_search_results", []),
            web_search_results=None,
        )

    # ---------------------------------------------------------------------
    # 2) LOCAL CONTEXT TOOL
    # ---------------------------------------------------------------------
    def content(self) -> Tool:
        """
        Tool to fetch entire documents from the local database. Typically used if the agent needs
        deeper or more structured context from documents, not just chunk-level hits.
        """
        if "gemini" in self.rag_generation_config.model:
            tool = Tool(
                name="content",
                description=(
                    "Fetches the complete contents of all user documents from the local database. "
                    "Can be used alongside filter criteria (e.g. doc IDs, collection IDs, etc.) to restrict the query."
                    "For instance, a single document can be returned with a filter like so:"
                    "{'document_id': {'$eq': '...'}}."
                ),
                results_function=self._content_function,
                llm_format_function=self.format_search_results_for_llm,
                stream_function=self.format_search_results_for_stream,
                parameters={
                    "type": "object",
                    "properties": {
                        "filters": {
                            "type": "string",
                            "description": (
                                "Dictionary with filter criteria, such as "
                                '{"$and": [{"document_id": {"$eq": "6c9d1c39..."}, {"collection_ids": {"$overlap": [...]}]}'
                            ),
                        },
                    },
                    "required": ["filters"],
                },
            )

        else:
            tool = Tool(
                name="content",
                description=(
                    "Fetches the complete contents of all user documents from the local database. "
                    "Can be used alongside filter criteria (e.g. doc IDs, collection IDs, etc.) to restrict the query."
                    "For instance, a single document can be returned with a filter like so:"
                    "{'document_id': {'$eq': '...'}}."
                ),
                results_function=self._content_function,
                llm_format_function=self.format_search_results_for_llm,
                stream_function=self.format_search_results_for_stream,
                parameters={
                    "type": "object",
                    "properties": {
                        "filters": {
                            "type": "object",
                            "description": (
                                "Dictionary with filter criteria, such as "
                                '{"$and": [{"document_id": {"$eq": "6c9d1c39..."}, {"collection_ids": {"$overlap": [...]}]}'
                            ),
                        },
                    },
                    "required": ["filters"],
                },
            )
        return tool

    async def _content_function(
        self,
        filters: Optional[dict[str, Any]] = None,
        options: Optional[dict[str, Any]] = None,
        *args,
        **kwargs,
    ) -> AggregateSearchResult:
        """
        Calls the passed-in `content_method(filters, options)` to fetch
        doc+chunk structures. Typically returns a list of dicts:
        [
            { 'document': {...}, 'chunks': [ {...}, {...}, ... ] },
            ...
        ]
        We'll store these in a new field `context_document_results` of
        AggregateSearchResult so we don't collide with chunk_search_results.
        """
        if not self.content_method:
            raise ValueError("No content_method provided to RAGAgentMixin.")

        if filters:
            if "document_id" in filters:
                filters["id"] = filters.pop("document_id")
            filters = {"$and": [filters, self.search_settings.filters]}
        else:
            filters = self.search_settings.filters

        options = options or {}

        # Actually call your data retrieval
        raw_context = await self.content_method(filters, options)
        # raw_context presumably is a list[dict], each with 'document' + 'chunks'.

        # Convert them to ContextDocumentResult
        context_document_results = []
        for item in raw_context:
            # item = { 'document': {...}, 'chunks': [...] }
            context_document_results.append(
                ContextDocumentResult(
                    document=item["document"],
                    chunks=item.get("chunks", []),
                )
            )

        # Return them in the new aggregator field
        return AggregateSearchResult(
            # We won't put them in chunk_search_results:
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=None,
            context_document_results=context_document_results,
        )

    # ---------------------------------------------------------------------
    # 3) WEB SEARCH TOOL
    # ---------------------------------------------------------------------
    def web_search(self) -> Tool:
        return Tool(
            name="web_search",
            description=(
                "Search for information on the web - use this tool when the user "
                "query needs LIVE or recent data from the internet."
            ),
            results_function=self._web_search_function,
            llm_format_function=self.format_search_results_for_llm,
            stream_function=self.format_search_results_for_stream,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to search with an external web API.",
                    },
                },
                "required": ["query"],
            },
        )

    async def _web_search_function(
        self,
        query: str,
        *args,
        **kwargs,
    ) -> AggregateSearchResult:
        """
        Example: calling an external search engine (Serper, Google, etc.)
        and returning results in an AggregateSearchResult.
        """
        # Example usage with a hypothetical 'SerperClient'
        from ..utils.serper import SerperClient  # adjust your import

        serper_client = SerperClient()
        raw_results = serper_client.get_raw(query)
        web_response = WebSearchResponse.from_serper_results(raw_results)

        return AggregateSearchResult(
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=web_response.organic_results,
        )

    # # ---------------------------------------------------------------------
    # # MULTI_SEARCH IMPLEMENTATION
    # # ---------------------------------------------------------------------
    # def multi_search(self) -> Tool:
    #     """
    #     A tool that accepts multiple queries at once, runs local/web/content
    #     searches *in parallel*, merges them, and returns aggregated results.
    #     """
    #     return Tool(
    #         name="multi_search",
    #         description=(
    #             "Run parallel searches for multiple queries. Submit ALL queries in a SINGLE request with this exact format:\n"
    #             '{"queries": ["query1", "query2", "query3"], "include_web": false}\n\n'
    #             "Example valid input:\n"
    #             '{"queries": ["latest research on GPT-4", "advances in robotics 2024"], "include_web": false}\n\n'
    #             "IMPORTANT:\n"
    #             "- All queries must be in a single array under the 'queries' key\n"
    #             "- Do NOT submit multiple separate JSON objects\n"
    #             "- Do NOT add empty JSON objects {}\n"
    #             "- Each query should be a string in the array\n"
    #             "You can submit up to 10 queries in a single request. Results are limited to 20 per query."
    #         ),
    #         results_function=self._multi_search,
    #         llm_format_function=self.format_search_results_for_llm,
    #         stream_function=self.format_search_results_for_stream,
    #         parameters={
    #             "type": "object",
    #             "properties": {
    #                 "queries": {
    #                     "type": "array",
    #                     "items": {"type": "string"},
    #                     "description": "Array of search queries to run in parallel. Example: ['query1', 'query2']",
    #                     "maxItems": 10,
    #                 },
    #                 "include_web": {
    #                     "type": "boolean",
    #                     "description": "Whether to include web search results",
    #                     "default": False,
    #                 },
    #             },
    #             "required": ["queries"],
    #         },
    #     )

    # async def _multi_search(
    #     self,
    #     queries: list[str],
    #     include_web: bool = False,
    #     include_content: bool = False,
    #     *args,
    #     **kwargs,
    # ) -> list[Tuple[str, AggregateSearchResult]]:
    #     """
    #     Run local, web, and content searches *in parallel* for each query,
    #     merge results, and return them sorted by best "score".

    #     :param queries: a list of search queries
    #     :param include_web: whether to run web search (True by default)
    #     :param include_content: whether to fetch entire documents (True by default)
    #     :return: A list of (query, merged_results), sorted by highest chunk score
    #     """
    #     # Set search results to 10
    #     self.search_settings.limit = 20

    #     # Build tasks (one per query)
    #     tasks = [
    #         self._multi_search_for_single_query(
    #             q, include_web, include_content
    #         )
    #         for q in queries
    #     ]
    #     # Run them all in parallel
    #     partial_results = await asyncio.gather(*tasks)
    #     return self._merge_aggregate_results(partial_results)

    # async def _multi_search_for_single_query(
    #     self,
    #     query: str,
    #     include_web: bool,
    #     include_content: bool,
    # ) -> AggregateSearchResult:
    #     """
    #     For a single query, run local, web, and content searches in parallel,
    #     then merge everything into one AggregateSearchResult.
    #     """
    #     # local always
    #     searches = [self._local_search_function(query)]

    #     # optionally web
    #     if include_web:
    #         searches.append(self._web_search_function(query))

    #     # optionally content
    #     if include_content:
    #         # pass any needed filters/options
    #         searches.append(self._content_function(filters={}, options={}))

    #     # gather them concurrently
    #     partial_results = await asyncio.gather(*searches)

    #     # merge all partial AggregateSearchResults
    #     merged_result = self._merge_aggregate_results(partial_results)
    #     return merged_result

    # def _merge_aggregate_results(
    #     self, results: list[AggregateSearchResult]
    # ) -> AggregateSearchResult:
    #     """
    #     Concatenate chunk_search_results, web_search_results, etc. from multiple
    #     AggregateSearchResult objects into one.
    #     """
    #     all_chunks = []
    #     all_graphs = []
    #     all_web = []
    #     all_docs = []

    #     for r in results:
    #         if r.chunk_search_results:
    #             all_chunks.extend(r.chunk_search_results)
    #         if r.graph_search_results:
    #             all_graphs.extend(r.graph_search_results)
    #         if r.web_search_results:
    #             all_web.extend(r.web_search_results)
    #         if r.context_document_results:
    #             all_docs.extend(r.context_document_results)

    #     return AggregateSearchResult(
    #         chunk_search_results=all_chunks if all_chunks else None,
    #         graph_search_results=all_graphs if all_graphs else None,
    #         web_search_results=all_web if all_web else None,
    #         context_document_results=all_docs if all_docs else None,
    #     )

    # ---------------------------------------------------------------------
    # 4) Utility format methods for search results
    # ---------------------------------------------------------------------
    def format_search_results_for_stream(
        self, results: AggregateSearchResult
    ) -> str:
        return format_search_results_for_stream(results)

    def format_search_results_for_llm(
        self, results: AggregateSearchResult
    ) -> str:
        context = format_search_results_for_llm(results)
        context_tokens = num_tokens(context)
        frac_to_return = self.max_tool_context_length / num_tokens(context)

        if frac_to_return > 1:
            return context
        else:

            return context[0 : int(frac_to_return * context_tokens)]


# ------------------------------------------------------------------------------
# AGENT CLASSES
# ------------------------------------------------------------------------------


class R2RRAGAgent(RAGAgentMixin, R2RAgent):
    """
    Non-streaming RAG Agent that supports local_search, content, web_search.
    """

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
        ),
        config: AgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        local_search_method: Callable,
        content_method: Optional[Callable] = None,
        max_tool_context_length: int = 10_000,
    ):
        # Initialize base R2RAgent
        R2RAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
        )
        # Initialize the RAGAgentMixin
        RAGAgentMixin.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            max_tool_context_length=max_tool_context_length,
            local_search_method=local_search_method,
            content_method=content_method,
        )


class R2RStreamingRAGAgent(RAGAgentMixin, R2RStreamingAgent):
    """
    Streaming-capable RAG Agent that supports local_search, content, web_search.
    """

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
        ),
        config: AgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        local_search_method: Callable,
        content_method: Optional[Callable] = None,
        max_tool_context_length: int = 10_000,
    ):
        # Force streaming on
        config.stream = True

        # Initialize base R2RStreamingAgent
        R2RStreamingAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
        )
        # Initialize the RAGAgentMixin
        RAGAgentMixin.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            max_tool_context_length=max_tool_context_length,
            local_search_method=local_search_method,
            content_method=content_method,
        )
