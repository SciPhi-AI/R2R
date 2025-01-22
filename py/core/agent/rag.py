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
from core.providers import LiteLLMCompletionProvider, OpenAICompletionProvider


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
            name="local_search",
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
        return Tool(
            name="content",
            description=(
                "Fetches the complete contents of all user documents from the local database. "
                "Can be used alongside filter criteria (e.g. doc IDs, collection IDs, etc.) to restrict the query."
                "For instance, a single document can be returned with a filter like so:"
                " {'document_id': {'$eq': '...'}}."
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
                            "{'document_id': {'$eq': '6c9d1c39...'}, 'owner_id': '...', 'collection_ids': {'$overlap': [...]}}."
                        ),
                    },
                    "options": {
                        "type": "object",
                        "description": (
                            "Additional retrieval options, e.g. "
                            "{'include_summary_embedding': false, ...}."
                        ),
                        "default": {},
                    },
                },
                "required": ["filters"],
            },
        )

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
        llm_provider: LiteLLMCompletionProvider | OpenAICompletionProvider,
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
        llm_provider: LiteLLMCompletionProvider | OpenAICompletionProvider,
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
