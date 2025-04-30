# type: ignore
import logging
from typing import Any, Callable, Optional
from uuid import UUID

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
    R2RXMLToolsAgent
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
            elif tool_name == "tavily_extract":
                self._tools.append(self.tavily_extract())
            elif tool_name == "search_file_knowledge":
                self._tools.append(self.search_file_knowledge())
            elif tool_name == "search_file_descriptions":
                self._tools.append(self.search_files())
            elif tool_name == "web_search":
                self._tools.append(self.web_search())
            elif tool_name == "tavily_search":
                self._tools.append(self.tavily_search())
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
        return Tool(
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
                    "document_id": {
                        "type": "string",
                        "description": "The unique UUID of the document to fetch.",
                    },
                },
                "required": ["document_id"],
            },
        )

    async def _content_function(
        self,
        document_id: str,
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

        try:
            doc_uuid = UUID(document_id)
            filters = {"id": {"$eq": doc_uuid}}
        except ValueError:
            # Handle invalid UUID format passed by LLM
            logger.error(f"Invalid document_id format received: {document_id}")
            # Return empty result or raise specific error
            return AggregateSearchResult(document_search_results=[])

        options = options or {}

        # Actually call your data retrieval
        content = await self.content_method(filters, options)

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

    def tavily_search(self) -> Tool:
        """
        Use Tavily to perform a search and retrieve results.
        """
        return Tool(
            name="tavily_search",
            description=(
                "Use the Tavily search engine to perform an internet-based search and retrieve results. Useful when you need "
                "to search the internet for specific information.  The query should be no more than 400 characters."
            ),
            results_function=self._tavily_search_function,
            llm_format_function=self.format_search_results_for_llm,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to search using Tavily that should be no more than 400 characters.",
                    },
                    "kwargs": {
                        "type": "object",
                        "description": (
                            "Dictionary for additional parameters to pass to Tavily, such as max_results, include_domains and exclude_domains."
                            '{"max_results": 10, "include_domains": ["example.com"], "exclude_domains": ["example2.com"]}'
                        ),
                    },
                },
                "required": ["query"],
            },
        )

    async def _tavily_search_function(
        self,
        query: str,
        *args,
        **kwargs,
    ) -> AggregateSearchResult:
        """
        Calls Tavily's search API asynchronously and returns results in an AggregateSearchResult.

        Note: For efficient processing, keep queries concise (under 400 characters).
        Think of them as search engine queries, not long-form prompts.
        """
        import asyncio
        import os

        # Check if query is too long (Tavily recommends under 400 chars)
        if len(query) > 400:
            logger.warning(
                f"Tavily query is {len(query)} characters long, which exceeds the recommended 400 character limit. Consider breaking into smaller queries for better results."
            )
            # Truncate the query to improve performance
            query = query[:400]

        # Check if Tavily is installed
        try:
            from tavily import TavilyClient
        except ImportError:
            logger.error(
                "The 'tavily-python' package is not installed. Please install it with 'pip install tavily-python'"
            )
            # Return empty results in case Tavily is not installed
            return AggregateSearchResult(web_search_results=[])

        # Get API key from environment variables
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            logger.warning("TAVILY_API_KEY environment variable not set")
            return AggregateSearchResult(web_search_results=[])

        # Initialize Tavily client
        tavily_client = TavilyClient(api_key=api_key)

        try:
            # Perform the search asynchronously
            raw_results = await asyncio.get_event_loop().run_in_executor(
                None,  # Uses the default executor
                lambda: tavily_client.search(
                    query=query,
                    search_depth="advanced",
                    include_raw_content=False,
                    include_domains=kwargs.get("include_domains", []),
                    exclude_domains=kwargs.get("exclude_domains", []),
                    max_results=kwargs.get("max_results", 10),
                ),
            )

            # Extract the results from the response
            results = raw_results.get("results", [])

            # Process the raw results into a format compatible with AggregateSearchResult
            search_results = [
                WebSearchResult(
                    title=result.get("title", "Untitled"),
                    link=result.get("url", ""),
                    snippet=result.get("content", ""),
                    position=index,
                    id=generate_id(result.get("url", "")),
                    type="tavily_search",
                )
                for index, result in enumerate(results)
            ]

            agg = AggregateSearchResult(web_search_results=search_results)

            # Add results to the collector
            self.search_results_collector.add_aggregate_result(agg)

            return agg
        except Exception as e:
            logger.error(f"Error during Tavily search: {e}")
            return AggregateSearchResult(web_search_results=[])

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

    def tavily_extract(self) -> Tool:
        """
        A Tool that uses Tavily to extract content from a specific URL.
        Similar to web_scrape but using Tavily's extraction capabilities.
        """
        return Tool(
            name="tavily_extract",
            description=(
                "Use Tavily to extract and retrieve the contents of a specific webpage. "
                "This is useful when you want to get clean, structured content from a URL. "
                "Use this when you need to analyze the full content of a specific webpage."
            ),
            results_function=self._tavily_extract_function,
            llm_format_function=self.format_search_results_for_llm,
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "The absolute URL of the webpage you want to extract content from. "
                            "Example: 'https://www.example.com/article'"
                        ),
                    }
                },
                "required": ["url"],
            },
        )

    async def _tavily_extract_function(
        self,
        url: str,
        *args,
        **kwargs,
    ) -> AggregateSearchResult:
        """
        Calls Tavily's extract API asynchronously to retrieve the content from a specific URL
        and returns results in an AggregateSearchResult.
        """
        import asyncio
        import os

        # Check if Tavily is installed
        try:
            from tavily import TavilyClient
        except ImportError:
            logger.error(
                "The 'tavily-python' package is not installed. Please install it with 'pip install tavily-python'"
            )
            # Return empty results in case Tavily is not installed
            return AggregateSearchResult(web_search_results=[])

        # Get API key from environment variables
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            logger.warning("TAVILY_API_KEY environment variable not set")
            return AggregateSearchResult(web_search_results=[])

        # Initialize Tavily client
        tavily_client = TavilyClient(api_key=api_key)

        try:
            # Perform the URL extraction asynchronously
            extracted_content = await asyncio.get_event_loop().run_in_executor(
                None,  # Uses the default executor
                lambda: tavily_client.extract(url, extract_depth="advanced"),
            )

            web_search_results = []
            for successfulResult in extracted_content.results:
                content = successfulResult.raw_content
                if len(content) > 100_000:
                    content = (
                        content[:100_000] + "...FURTHER CONTENT TRUNCATED..."
                    )

                web_result = WebPageSearchResult(
                    title=successfulResult.url,
                    link=successfulResult.url,
                    snippet=content,
                    position=0,
                    id=generate_id(successfulResult.url),
                    type="tavily_extract",
                )
                web_search_results.append(web_result)

            agg = AggregateSearchResult(web_search_results=web_search_results)

            # Add results to the collector
            self.search_results_collector.add_aggregate_result(agg)

            return agg
        except Exception as e:
            logger.error(f"Error during Tavily URL extraction: {e}")
            return AggregateSearchResult(web_search_results=[])


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
        memory_enabled: bool = False,
    ):
        # Initialize base R2RAgent
        R2RAgent.__init__(
            self,
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
            memory_enabled=memory_enabled,
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
