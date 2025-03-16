# type: ignore
import logging
from typing import Any, Callable, Optional

from core.base import (
    format_search_results_for_llm,
)
from core.base.abstractions import (
    AggregateSearchResult,
    GenerationConfig,
    SearchSettings,
    WebPageSearchResult,
    WebSearchResult,
)
from core.base.agent import Tool
from core.base.providers import DatabaseProvider
from core.providers import (
    AnthropicCompletionProvider,
    LiteLLMCompletionProvider,
    OpenAICompletionProvider,
    R2RCompletionProvider,
)
from core.utils import (
    SearchResultsCollector,
    generate_id,
    num_tokens,
)

from ..base.agent.agent import RAGAgentConfig

# Import the base classes from the refactored base file
from .base import (
    R2RAgent,
    R2RStreamingAgent,
    R2RXMLStreamingAgent,
    R2RXMLToolsAgent,
)

logger = logging.getLogger(__name__)


class RAGAgentMixin:
    """
    A Mixin for adding search_file_knowledge, web_search, and content tools
    to your R2R Agents. This allows your agent to:
      - call knowledge_search_method (semantic/hybrid search)
      - call content_method (fetch entire doc/chunk structures)
      - call an external web search API
    """

    def __init__(
        self,
        *args,
        search_settings: SearchSettings,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        max_tool_context_length=10_000,
        max_context_window_tokens=512_000,
        **kwargs,
    ):
        # Save references to the retrieval logic
        self.search_settings = search_settings
        self.knowledge_search_method = knowledge_search_method
        self.content_method = content_method
        self.file_search_method = file_search_method
        self.max_tool_context_length = max_tool_context_length
        self.max_context_window_tokens = max_context_window_tokens
        self.search_results_collector = SearchResultsCollector()
        super().__init__(*args, **kwargs)

    def _register_tools(self):
        """
        Called by the base R2RAgent to register all requested tools from self.config.rag_tools.
        """
        if not self.config.rag_tools:
            return

        for tool_name in set(self.config.rag_tools):
            if tool_name == "get_file_content":
                self._tools.append(self.content())
            elif tool_name == "web_scrape":
                self._tools.append(self.web_scrape())
            elif tool_name == "search_file_knowledge":
                self._tools.append(self.search_file_knowledge())
            elif tool_name == "search_file_descriptions":
                self._tools.append(self.search_files())
            elif tool_name == "web_search":
                self._tools.append(self.web_search())
            else:
                raise ValueError(f"Unknown tool requested: {tool_name}")
        logger.debug(f"Registered {len(self._tools)} RAG tools.")

    # Local Search Tool
    def search_file_knowledge(self) -> Tool:
        """
        Tool to do a semantic/hybrid search on the local knowledge base
        using self.knowledge_search_method.
        """
        return Tool(
            name="search_file_knowledge",
            description=(
                "Search your local knowledge base using the R2R system. "
                "Use this when you want relevant text chunks or knowledge graph data."
            ),
            results_function=self._file_knowledge_search_function,
            llm_format_function=self.format_search_results_for_llm,
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

    async def _file_knowledge_search_function(
        self,
        query: str,
        *args,
        **kwargs,
    ) -> AggregateSearchResult:
        """
        Calls the passed-in `knowledge_search_method(query, search_settings)`.
        Expects either an AggregateSearchResult or a dict with chunk_search_results, etc.
        """
        if not self.knowledge_search_method:
            raise ValueError(
                "No knowledge_search_method provided to RAGAgentMixin."
            )

        raw_response = await self.knowledge_search_method(
            query=query, search_settings=self.search_settings
        )

        if isinstance(raw_response, AggregateSearchResult):
            agg = raw_response
        else:
            agg = AggregateSearchResult(
                chunk_search_results=raw_response.get(
                    "chunk_search_results", []
                ),
                graph_search_results=raw_response.get(
                    "graph_search_results", []
                ),
            )

        # 1) Store them so that we can do final citations later
        self.search_results_collector.add_aggregate_result(agg)
        return agg

    # 2) Local Context
    def content(self) -> Tool:
        """Tool to fetch entire documents from the local database.

        Typically used if the agent needs deeper or more structured context
        from documents, not just chunk-level hits.
        """
        if "gemini" in self.rag_generation_config.model:
            tool = Tool(
                name="get_file_content",
                description=(
                    "Fetches the complete contents of all user documents from the local database. "
                    "Can be used alongside filter criteria (e.g. doc IDs, collection IDs, etc.) to restrict the query."
                    "For instance, a single document can be returned with a filter like so:"
                    "{'document_id': {'$eq': '...'}}."
                    "Be sure to use the full 32 character hexidecimal document ID, and not the shortened 8 character ID."
                ),
                results_function=self._content_function,
                llm_format_function=self.format_search_results_for_llm,
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
                name="get_file_content",
                description=(
                    "Fetches the complete contents of all user documents from the local database. "
                    "Can be used alongside filter criteria (e.g. doc IDs, collection IDs, etc.) to restrict the query."
                    "For instance, a single document can be returned with a filter like so:"
                    "{'document_id': {'$eq': '...'}}."
                ),
                results_function=self._content_function,
                llm_format_function=self.format_search_results_for_llm,
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
        """Calls the passed-in `content_method(filters, options)` to fetch
        doc+chunk structures.

        Typically returns a list of dicts:
        [
            { 'document': {...}, 'chunks': [ {...}, {...}, ... ] },
            ...
        ]
        We'll store these in a new field `document_search_results` of
        AggregateSearchResult so we don't collide with chunk_search_results.
        """
        if not self.content_method:
            raise ValueError("No content_method provided to RAGAgentMixin.")

        if filters:
            if "document_id" in filters:
                filters["id"] = filters.pop("document_id")
            if self.search_settings.filters != {}:
                filters = {"$and": [filters, self.search_settings.filters]}
        else:
            filters = self.search_settings.filters

        options = options or {}

        # Actually call your data retrieval
        content = await self.content_method(filters, options)
        # raw_context presumably is a list[dict], each with 'document' + 'chunks'.

        # Return them in the new aggregator field
        agg = AggregateSearchResult(
            # We won't put them in chunk_search_results:
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=None,
            document_search_results=content,
        )
        self.search_results_collector.add_aggregate_result(agg)
        return agg

    # Web Search Tool
    def web_search(self) -> Tool:
        return Tool(
            name="web_search",
            description=(
                "Search for information on the web - use this tool when the user "
                "query needs LIVE or recent data from the internet."
            ),
            results_function=self._web_search_function,
            llm_format_function=self.format_search_results_for_llm,
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
        Calls an external search engine (Serper, Google, etc.) asynchronously
        and returns results in an AggregateSearchResult.
        """
        import asyncio

        from ..utils.serper import SerperClient  # adjust your import

        serper_client = SerperClient()

        # If SerperClient.get_raw is not already async, wrap it in run_in_executor
        raw_results = await asyncio.get_event_loop().run_in_executor(
            None,  # Uses the default executor
            lambda: serper_client.get_raw(query),
        )

        # If from_serper_results is not already async, wrap it in run_in_executor too
        web_response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: WebSearchResult.from_serper_results(raw_results)
        )

        agg = AggregateSearchResult(
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=web_response.organic_results,
        )
        self.search_results_collector.add_aggregate_result(agg)
        return agg

    def search_files(self) -> Tool:
        """
        A tool to search over file-level metadata (titles, doc-level descriptions, etc.)
        returning a list of DocumentResponse objects.
        """
        return Tool(
            name="search_file_descriptions",
            description=(
                "Semantic search over the stored documents over AI generated summaries of input documents. "
                "This does NOT retrieve chunk-level contents or knowledge-graph relationships. "
                "Use this when you need a broad overview of which documents (files) might be relevant."
            ),
            results_function=self._search_files_function,
            llm_format_function=self.format_search_results_for_llm,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query string to semantic search over available files 'list documents about XYZ'.",
                    }
                },
                "required": ["query"],
            },
        )

    async def _search_files_function(
        self, query: str, *args, **kwargs
    ) -> AggregateSearchResult:
        if not self.file_search_method:
            raise ValueError(
                "No file_search_method provided to RAGAgentMixin."
            )

        # call the doc-level search
        """
        FIXME: This is going to fail, as it requires an embedding NOT a query.
        I've moved 'search_settings' to 'settings' which had been causing a silent failure
        causing null content in the Message object.
        """
        doc_results = await self.file_search_method(
            query=query,
            settings=self.search_settings,
        )

        # Wrap them in an AggregateSearchResult
        agg = AggregateSearchResult(document_search_results=doc_results)

        # Add them to the collector
        self.search_results_collector.add_aggregate_result(agg)
        return agg

    def format_search_results_for_llm(
        self, results: AggregateSearchResult
    ) -> str:
        context = format_search_results_for_llm(
            results, self.search_results_collector
        )
        context_tokens = num_tokens(context) + 1
        frac_to_return = self.max_tool_context_length / (context_tokens)

        if frac_to_return > 1:
            return context
        else:
            return context[: int(frac_to_return * len(context))]

    def web_scrape(self) -> Tool:
        """
        A new Tool that uses Firecrawl to scrape a single URL and return
        its contents in an LLM-friendly format (e.g. markdown).
        """
        return Tool(
            name="web_scrape",
            description=(
                "Use Firecrawl to scrape a single webpage and retrieve its contents "
                "as clean markdown. Useful when you need the entire body of a page, "
                "not just a quick snippet or standard web search result."
            ),
            results_function=self._web_scrape_function,
            llm_format_function=self.format_search_results_for_llm,
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "The absolute URL of the webpage you want to scrape. "
                            "Example: 'https://docs.firecrawl.dev/getting-started'"
                        ),
                    }
                },
                "required": ["url"],
            },
        )

    async def _web_scrape_function(
        self,
        url: str,
        *args,
        **kwargs,
    ) -> AggregateSearchResult:
        """
        Performs the Firecrawl scrape asynchronously, returning results
        as an `AggregateSearchResult` with a single WebPageSearchResult.
        """
        import asyncio

        from firecrawl import FirecrawlApp

        app = FirecrawlApp()
        logger.debug(f"[Firecrawl] Scraping URL={url}")

        # Create a proper async wrapper for the synchronous scrape_url method
        # This offloads the blocking operation to a thread pool
        response = await asyncio.get_event_loop().run_in_executor(
            None,  # Uses the default executor
            lambda: app.scrape_url(
                url=url,
                params={"formats": ["markdown"]},
            ),
        )

        markdown_text = response.get("markdown", "")
        metadata = response.get("metadata", {})
        page_title = metadata.get("title", "Untitled page")

        if len(markdown_text) > 100_000:
            markdown_text = (
                markdown_text[:100_000] + "...FURTHER CONTENT TRUNCATED..."
            )

        # Create a single WebPageSearchResult HACK - TODO FIX
        web_result = WebPageSearchResult(
            title=page_title,
            link=url,
            snippet=markdown_text,
            position=0,
            id=generate_id(markdown_text),
            type="firecrawl",
        )

        agg = AggregateSearchResult(web_search_results=[web_result])

        # Add results to the collector
        if self.search_results_collector:
            self.search_results_collector.add_aggregate_result(agg)

        return agg


class R2RRAGAgent(RAGAgentMixin, R2RAgent):
    """
    Non-streaming RAG Agent that supports search_file_knowledge, content, web_search.
    """

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        config: RAGAgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        max_tool_context_length: int = 20_000,
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
            knowledge_search_method=knowledge_search_method,
            file_search_method=file_search_method,
            content_method=content_method,
        )


class R2RXMLToolsRAGAgent(RAGAgentMixin, R2RXMLToolsAgent):
    """
    Non-streaming RAG Agent that supports search_file_knowledge, content, web_search.
    """

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        config: RAGAgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        max_tool_context_length: int = 20_000,
    ):
        # Initialize base R2RAgent
        R2RXMLToolsAgent.__init__(
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
            knowledge_search_method=knowledge_search_method,
            file_search_method=file_search_method,
            content_method=content_method,
        )


class R2RStreamingRAGAgent(RAGAgentMixin, R2RStreamingAgent):
    """
    Streaming-capable RAG Agent that supports search_file_knowledge, content, web_search,
    and emits citations as [abc1234] short IDs if the LLM includes them in brackets.
    """

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        config: RAGAgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
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
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
        )


class R2RXMLToolsStreamingRAGAgent(RAGAgentMixin, R2RXMLStreamingAgent):
    """
    A streaming agent that:
     - treats <think> or <Thought> blocks as chain-of-thought
       and emits them incrementally as SSE "thinking" events.
     - accumulates user-visible text outside those tags as SSE "message" events.
     - filters out all XML tags related to tool calls and actions.
     - upon finishing each iteration, it parses <Action><ToolCalls><ToolCall> blocks,
       calls the appropriate tool, and emits SSE "tool_call" / "tool_result".
     - properly emits citations when they appear in the text
    """

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        config: RAGAgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        max_tool_context_length: int = 10_000,
    ):
        # Force streaming on
        config.stream = True

        # Initialize base R2RXMLStreamingAgent
        R2RXMLStreamingAgent.__init__(
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
            knowledge_search_method=knowledge_search_method,
            content_method=content_method,
            file_search_method=file_search_method,
        )
