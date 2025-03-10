import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator, Callable, Optional, Tuple

from core.agent import R2RAgent
from core.base import (
    ToolCallData,
    ToolCallEvent,
    format_search_results_for_llm,
)
from core.base.abstractions import (
    AggregateSearchResult,
    ContextDocumentResult,
    GenerationConfig,
    Message,
    SearchSettings,
    WebSearchResult,
)
from core.base.agent import AgentConfig, Tool
from core.base.providers import DatabaseProvider
from core.providers import (
    AnthropicCompletionProvider,
    LiteLLMCompletionProvider,
    OpenAICompletionProvider,
    R2RCompletionProvider,
)
from core.utils import (
    SearchResultsCollector,
    SSEFormatter,
    convert_nonserializable_objects,
    extract_citations,
    num_tokens,
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
        Called by the base R2RAgent to register all requested tools from self.config.tools.
        """
        if not self.config.tools:
            return

        for tool_name in set(self.config.tools):
            if tool_name == "content":
                self._tools.append(self.content())
            elif tool_name == "search_file_knowledge":
                self._tools.append(self.search_file_knowledge())
            elif tool_name == "search_file_descriptions":
                self._tools.append(self.search_files())
            elif tool_name == "web_search":
                self._tools.append(self.web_search())
            else:
                raise ValueError(f"Unsupported tool name: {tool_name}")

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
            if self.search_settings.filters != {}:
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
            document = item["document"]
            chunks = item["chunks"]
            document["metadata"].pop("chunk_metadata", None)
            context_document_results.append(
                ContextDocumentResult(
                    document=document,
                    chunks=chunks,
                )
            )

        # Return them in the new aggregator field
        agg = AggregateSearchResult(
            # We won't put them in chunk_search_results:
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=None,
            context_document_results=context_document_results,
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
        Example: calling an external search engine (Serper, Google, etc.)
        and returning results in an AggregateSearchResult.
        """
        # Example usage with a hypothetical 'SerperClient'
        from ..utils.serper import SerperClient  # adjust your import

        serper_client = SerperClient()
        raw_results = serper_client.get_raw(query)
        web_response = WebSearchResult.from_serper_results(raw_results)

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
            name="search_files",
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
        """
        Implementation: calls the doc-level search method `local_doc_search_method`.
        That method typically calls `search_documents` in your retrieval service,
        returning a list of DocumentResponse objects.
        """
        if not self.local_doc_search_method:
            raise ValueError(
                "No local_doc_search_method provided to RAGAgentMixin."
            )

        # call the doc-level search
        doc_results = await self.local_doc_search_method(
            query=query,
            search_settings=self.search_settings,
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
        config: AgentConfig,
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


class R2RXMLToolsAgent(RAGAgentMixin, R2RAgent):
    """
    A non-streaming agent that:
     - parses <think> or <Thought> blocks as chain-of-thought
     - filters out XML tags related to tool calls and actions
     - processes <Action><ToolCalls><ToolCall> blocks
     - properly extracts citations when they appear in the text
    """

    # We treat <think> or <Thought> as the same token boundaries
    THOUGHT_OPEN = re.compile(r"<(Thought|think)>", re.IGNORECASE)
    THOUGHT_CLOSE = re.compile(r"</(Thought|think)>", re.IGNORECASE)

    # Regexes to parse out <Action>, <ToolCalls>, <ToolCall>, <Name>, <Parameters>, <Response>
    ACTION_PATTERN = re.compile(
        r"<Action>(.*?)</Action>", re.IGNORECASE | re.DOTALL
    )
    TOOLCALLS_PATTERN = re.compile(
        r"<ToolCalls>(.*?)</ToolCalls>", re.IGNORECASE | re.DOTALL
    )
    TOOLCALL_PATTERN = re.compile(
        r"<ToolCall>(.*?)</ToolCall>", re.IGNORECASE | re.DOTALL
    )
    NAME_PATTERN = re.compile(r"<Name>(.*?)</Name>", re.IGNORECASE | re.DOTALL)
    PARAMS_PATTERN = re.compile(
        r"<Parameters>(.*?)</Parameters>", re.IGNORECASE | re.DOTALL
    )
    RESPONSE_PATTERN = re.compile(
        r"<Response>(.*?)</Response>", re.IGNORECASE | re.DOTALL
    )

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        config: AgentConfig,
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
            content_method=content_method,
            file_search_method=file_search_method,
        )

    async def process_llm_response(self, response, *args, **kwargs):
        """
        Override the base process_llm_response to handle XML structured responses
        including thoughts and tool calls.
        """
        if self._completed:
            return

        message = response.choices[0].message
        if not message.content:
            # If there's no content, let the parent class handle the normal tool_calls flow
            return await super().process_llm_response(
                response, *args, **kwargs
            )

        # Get the response content
        content = message.content

        if not content.startswith(
            "<"
        ):  # HACK - fix issues with adding `<think>` to the beginning
            content = "<think>" + content

        # Process any tool calls in the content
        action_matches = self.ACTION_PATTERN.findall(content)
        if action_matches:
            xml_toolcalls = "<ToolCalls>"
            for action_block in action_matches:
                tool_calls_text = []
                # Look for ToolCalls wrapper, or use the raw action block
                calls_wrapper = self.TOOLCALLS_PATTERN.findall(action_block)
                if calls_wrapper:
                    for tw in calls_wrapper:
                        tool_calls_text.append(tw)
                else:
                    tool_calls_text.append(action_block)

                # Process each ToolCall
                for calls_region in tool_calls_text:
                    calls_found = self.TOOLCALL_PATTERN.findall(calls_region)
                    for tc_block in calls_found:
                        tool_name, tool_params = self._parse_single_tool_call(
                            tc_block
                        )
                        if tool_name:
                            tool_call_id = f"call_{abs(hash(tc_block))}"
                            try:
                                tool_result = (
                                    await self.handle_function_or_tool_call(
                                        tool_name,
                                        json.dumps(tool_params),
                                        tool_id=tool_call_id,
                                        save_messages=False,
                                    )
                                )

                                xml_toolcalls += (
                                    f"<ToolCall>"
                                    f"<Name>{tool_name}</Name>"
                                    f"<Parameters>{json.dumps(tool_params)}</Parameters>"
                                    f"<Result>{tool_result.llm_formatted_result}</Result>"
                                    f"</ToolCall>"
                                )

                            except Exception as e:
                                pass
                xml_toolcalls += "</ToolCalls>"
                pre_action_text = content[: content.find(action_block)]
                post_action_text = content[
                    content.find(action_block) + len(action_block) :
                ]
                iteration_text = (
                    pre_action_text + xml_toolcalls + post_action_text
                )

                # Create the final clean assistant message
                await self.conversation.add_message(
                    Message(role="assistant", content=iteration_text)
                )
            else:
                # Create the final clean assistant message
                await self.conversation.add_message(
                    Message(role="assistant", content=content)
                )

        self._completed = True

    def _parse_single_tool_call(
        self, toolcall_text: str
    ) -> Tuple[Optional[str], dict]:
        """
        Parse a ToolCall block to extract the name and parameters.

        Args:
            toolcall_text: The text content of a ToolCall block

        Returns:
            Tuple of (tool_name, tool_parameters)
        """
        name_match = self.NAME_PATTERN.search(toolcall_text)
        if not name_match:
            return None, {}
        tool_name = name_match.group(1).strip()

        params_match = self.PARAMS_PATTERN.search(toolcall_text)
        if not params_match:
            return tool_name, {}

        raw_params = params_match.group(1).strip()
        try:
            # Handle potential JSON parsing issues
            # First try direct parsing
            tool_params = json.loads(raw_params)
        except json.JSONDecodeError:
            # If that fails, try to clean up the JSON string
            try:
                # Replace escaped quotes that might cause issues
                cleaned_params = raw_params.replace('\\"', '"')
                # Try again with the cleaned string
                tool_params = json.loads(cleaned_params)
            except json.JSONDecodeError:
                # If all else fails, treat as a plain string value
                tool_params = {"value": raw_params}

        return tool_name, tool_params

    def _remove_xml_tags(self, content: str) -> str:
        """
        Remove all XML tags related to actions, tools, and thoughts from content.
        """
        # Define patterns for all tool-related XML tags
        patterns = [
            r"<Action>.*?</Action>",
            r"<ToolCalls>.*?</ToolCalls>",
            r"<ToolCall>.*?</ToolCall>",
            r"<Name>.*?</Name>",
            r"<Parameters>.*?</Parameters>",
            r"<Response>.*?</Response>",
            # r"<Thought>.*?</Thought>",
            # r"<think>.*?</think>",
        ]

        # Apply patterns to remove XML blocks
        cleaned_content = content
        for pattern in patterns:
            cleaned_content = re.sub(
                pattern, "", cleaned_content, flags=re.DOTALL | re.IGNORECASE
            )

        # Remove any empty lines created by tag removal
        cleaned_content = re.sub(r"\n\s*\n", "\n\n", cleaned_content)

        return cleaned_content.strip()

    def format_search_results_for_llm(
        self, results: AggregateSearchResult
    ) -> str:
        """
        Format search results for the LLM, with token limit enforcement.
        """
        context = format_search_results_for_llm(
            results, self.search_results_collector
        )
        context_tokens = num_tokens(context) + 1
        frac_to_return = self.max_tool_context_length / (context_tokens)

        if frac_to_return > 1:
            return context
        else:
            return context[: int(frac_to_return * len(context))]


class R2RStreamingRAGAgent(RAGAgentMixin, R2RAgent):
    """
    Streaming-capable RAG Agent that supports search_file_knowledge, content, web_search,
    but now emits citations as [abc1234] short IDs if the LLM includes them in brackets.
    """

    # These two regexes will detect bracket references and then find short IDs.
    # If your IDs are exactly 8 characters (like "e43864f5"), you can update the pattern:
    # SHORT_ID_PATTERN = re.compile(r"[A-Za-z0-9]{8}")
    BRACKET_PATTERN = re.compile(r"\[([^\]]+)\]")
    SHORT_ID_PATTERN = re.compile(
        r"[A-Za-z0-9]{7,8}"
    )  # 7-8 chars, for example

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: (
            AnthropicCompletionProvider
            | LiteLLMCompletionProvider
            | OpenAICompletionProvider
            | R2RCompletionProvider
        ),
        config: AgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        knowledge_search_method: Callable,
        content_method: Callable,
        file_search_method: Callable,
        max_tool_context_length: int = 10_000,
    ):
        # Force streaming on
        config.stream = True

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
            content_method=content_method,
            file_search_method=file_search_method,
        )

    async def arun(
        self,
        system_instruction: str | None = None,
        messages: list[Message] | None = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Main streaming entrypoint: returns an async generator of SSE lines.
        """
        self._reset()
        await self._setup(system_instruction)

        if messages:
            for m in messages:
                await self.conversation.add_message(m)

        async def sse_generator() -> AsyncGenerator[str, None]:
            announced_short_ids = set()
            pending_tool_calls = {}
            partial_text_buffer = ""
            iterations_count = 0

            try:
                # Keep streaming until we complete
                while (
                    not self._completed
                    and iterations_count < self.config.max_iterations
                ):
                    iterations_count += 1
                    # 1) Get current messages
                    msg_list = await self.conversation.get_messages()
                    gen_cfg = self.get_generation_config(
                        msg_list[-1], stream=True
                    )

                    accumulated_thinking = ""
                    thinking_signatures = (
                        {}
                    )  # Map thinking content to signatures

                    # 2) Start streaming from LLM
                    llm_stream = self.llm_provider.aget_completion_stream(
                        msg_list, gen_cfg
                    )
                    async for chunk in llm_stream:
                        delta = chunk.choices[0].delta
                        finish_reason = chunk.choices[0].finish_reason

                        if hasattr(delta, "thinking") and delta.thinking:
                            # Accumulate thinking for later use in messages
                            accumulated_thinking += delta.thinking

                            # Emit SSE "thinking" event
                            async for (
                                line
                            ) in SSEFormatter.yield_thinking_event(
                                delta.thinking
                            ):
                                yield line

                        # Add this new handler for thinking signatures
                        if hasattr(delta, "thinking_signature"):
                            thinking_signatures[accumulated_thinking] = (
                                delta.thinking_signature
                            )
                            accumulated_thinking = ""

                        # 3) If new text, accumulate it
                        if delta.content:
                            partial_text_buffer += delta.content

                            # (a) Extract bracket references from the entire partial_text_buffer
                            #     so we find newly appeared short IDs
                            new_sids = extract_citations(partial_text_buffer)
                            for sid in new_sids:
                                if sid not in announced_short_ids:
                                    announced_short_ids.add(sid)
                                    # SSE "citation"
                                    citation_evt_payload = {
                                        "id": f"cit_{sid}",
                                        "object": "citation",
                                        "payload": self.search_results_collector.find_by_short_id(
                                            sid
                                        ),
                                    }
                                    # Using SSEFormatter to yield a "citation" event
                                    async for (
                                        line
                                    ) in SSEFormatter.yield_citation_event(
                                        citation_evt_payload
                                    ):
                                        yield line

                            # (b) Now emit the newly streamed text as a "message" event
                            async for line in SSEFormatter.yield_message_event(
                                delta.content
                            ):
                                yield line

                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                idx = tc.index
                                if idx not in pending_tool_calls:
                                    pending_tool_calls[idx] = {
                                        "id": tc.id,
                                        "name": tc.function.name or "",
                                        "arguments": tc.function.arguments
                                        or "",
                                    }
                                else:
                                    # Accumulate partial name/arguments
                                    if tc.function.name:
                                        pending_tool_calls[idx][
                                            "name"
                                        ] = tc.function.name
                                    if tc.function.arguments:
                                        pending_tool_calls[idx][
                                            "arguments"
                                        ] += tc.function.arguments

                        # 5) If the stream signals we should handle "tool_calls"
                        if finish_reason == "tool_calls":
                            # 4) Accumulate partial tool calls if present

                            if thinking_signatures:
                                for (
                                    accumulated_thinking,
                                    thinking_signature,
                                ) in thinking_signatures.items():
                                    structured_content = [
                                        {
                                            "type": "thinking",
                                            "thinking": accumulated_thinking,
                                            # Anthropic will validate this in their API
                                            "signature": thinking_signature,
                                        }
                                    ]

                                    assistant_msg = Message(
                                        role="assistant",
                                        structured_content=structured_content,
                                    )
                                    await self.conversation.add_message(
                                        assistant_msg
                                    )

                            calls_list = []
                            for idx in sorted(pending_tool_calls.keys()):
                                cinfo = pending_tool_calls[idx]
                                calls_list.append(
                                    {
                                        "tool_call_id": cinfo["id"]
                                        or f"call_{idx}",
                                        "name": cinfo["name"],
                                        "arguments": cinfo["arguments"],
                                    }
                                )

                            # (a) Emit SSE "tool_call" events
                            for c in calls_list:
                                tc_data = ToolCallData(
                                    tool_call_id=c["tool_call_id"],
                                    name=c["name"],
                                    arguments=c["arguments"],
                                )
                                tc_evt = ToolCallEvent(
                                    event="tool_call", data=tc_data
                                )
                                # With SSEFormatter, you might do:
                                async for (
                                    line
                                ) in SSEFormatter.yield_tool_call_event(
                                    tc_evt.dict()["data"]
                                ):
                                    yield line

                            # (b) Add an assistant message capturing these calls
                            assistant_msg = Message(
                                role="assistant",
                                content=partial_text_buffer or None,
                                tool_calls=[
                                    {
                                        "id": c["tool_call_id"],
                                        "type": "function",
                                        "function": {
                                            "name": c["name"],
                                            "arguments": c["arguments"],
                                        },
                                    }
                                    for c in calls_list
                                ],
                            )
                            await self.conversation.add_message(assistant_msg)

                            # (c) Execute each tool call in parallel
                            await asyncio.gather(
                                *[
                                    self.handle_function_or_tool_call(
                                        c["name"],
                                        c["arguments"],
                                        tool_id=c["tool_call_id"],
                                    )
                                    for c in calls_list
                                ]
                            )

                            # Optionally emit SSE "tool_result" events for each result
                            # (commented out here, but you can do it):
                            #
                            # for cinfo, result_obj in zip(calls_list, tool_results):
                            #     result_data = ToolResultData(
                            #         tool_call_id=cinfo["tool_call_id"],
                            #         role="tool",
                            #         content=json.dumps(
                            #             convert_nonserializable_objects(result_obj.raw_result.as_dict())
                            #         ),
                            #     )
                            #     result_evt = ToolResultEvent(event="tool_result", data=result_data)
                            #     async for line in SSEFormatter.yield_tool_result_event(result_evt.dict()["data"]):
                            #         yield line

                            # Reset buffer & calls
                            pending_tool_calls.clear()
                            partial_text_buffer = ""

                        elif finish_reason == "stop":
                            if accumulated_thinking:
                                structured_content = [
                                    {
                                        "type": "thinking",
                                        "thinking": accumulated_thinking,
                                        # Anthropic will validate this in their API
                                        "signature": "placeholder_signature",
                                    }
                                ]

                                assistant_msg = Message(
                                    role="assistant",
                                    structured_content=structured_content,
                                )
                                await self.conversation.add_message(
                                    assistant_msg
                                )

                            # 6) The LLM is done. If we have any leftover partial text,
                            #    finalize it in the conversation
                            if partial_text_buffer:
                                await self.conversation.add_message(
                                    Message(
                                        role="assistant",
                                        content=partial_text_buffer,
                                    )
                                )

                            # (a) Emit final answer SSE event
                            final_evt_payload = {
                                "id": "msg_final",
                                "object": "agent.final_answer",
                                "generated_answer": partial_text_buffer,
                                "citations": [
                                    {
                                        "id": f"cit_{sid}",
                                        "object": "citation",
                                        "payload": self.search_results_collector.find_by_short_id(
                                            sid
                                        ),
                                    }
                                    for sid in announced_short_ids
                                ],
                                # Optionally attach citations, tool calls, etc.
                            }
                            async for (
                                line
                            ) in SSEFormatter.yield_final_answer_event(
                                final_evt_payload
                            ):
                                yield line

                            # (b) Signal the end of the SSE stream
                            yield SSEFormatter.yield_done_event()
                            self._completed = True
                            break

                # If we exit the while loop unexpectedly, ensure we finalize
                if not self._completed:
                    yield SSEFormatter.yield_done_event()
                    self._completed = True

            except Exception as e:
                logger.error(f"Error in streaming agent: {str(e)}")
                # Emit error event for client
                async for line in SSEFormatter.yield_error_event(
                    f"Agent error: {str(e)}"
                ):
                    yield line
                # Send done event to close the stream
                yield SSEFormatter.yield_done_event()

        # Finally, we return the async generator
        async for line in sse_generator():
            yield line


class R2RXMLToolsStreamingRAGAgent(R2RStreamingRAGAgent):
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

    # We treat <think> or <Thought> as the same token boundaries
    THOUGHT_OPEN = re.compile(r"<(Thought|think)>", re.IGNORECASE)
    THOUGHT_CLOSE = re.compile(r"</(Thought|think)>", re.IGNORECASE)

    # Regexes to parse out <Action>, <ToolCalls>, <ToolCall>, <Name>, <Parameters>, <Response>
    ACTION_PATTERN = re.compile(
        r"<Action>(.*?)</Action>", re.IGNORECASE | re.DOTALL
    )
    TOOLCALLS_PATTERN = re.compile(
        r"<ToolCalls>(.*?)</ToolCalls>", re.IGNORECASE | re.DOTALL
    )
    TOOLCALL_PATTERN = re.compile(
        r"<ToolCall>(.*?)</ToolCall>", re.IGNORECASE | re.DOTALL
    )
    NAME_PATTERN = re.compile(r"<Name>(.*?)</Name>", re.IGNORECASE | re.DOTALL)
    PARAMS_PATTERN = re.compile(
        r"<Parameters>(.*?)</Parameters>", re.IGNORECASE | re.DOTALL
    )
    RESPONSE_PATTERN = re.compile(
        r"<Response>(.*?)</Response>", re.IGNORECASE | re.DOTALL
    )

    async def arun(
        self,
        system_instruction: str | None = None,
        messages: list[Message] | None = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Main streaming entrypoint: returns an async generator of SSE lines.
        """
        self._reset()
        await self._setup(system_instruction)

        if messages:
            for m in messages:
                await self.conversation.add_message(m)

        async def sse_generator() -> AsyncGenerator[str, None]:
            announced_short_ids = set()
            iterations_count = 0

            try:
                # Keep streaming until we complete
                while (
                    not self._completed
                    and iterations_count < self.config.max_iterations
                ):
                    iterations_count += 1
                    # 1) Get current messages
                    msg_list = await self.conversation.get_messages()
                    gen_cfg = self.get_generation_config(
                        msg_list[-1], stream=True
                    )

                    # 2) Start streaming from LLM
                    llm_stream = self.llm_provider.aget_completion_stream(
                        msg_list, gen_cfg
                    )

                    # Create state variables for each iteration
                    iteration_buffer = ""
                    yielded_first_event = False
                    in_action_block = False
                    is_thinking = False

                    async for chunk in llm_stream:
                        delta = chunk.choices[0].delta
                        finish_reason = chunk.choices[0].finish_reason

                        # 3) If new text, accumulate it
                        if delta.content:
                            iteration_buffer += delta.content

                            # Check if we have accumulated enough text for a `<Thought>` block
                            if len(iteration_buffer) < len("<Thought>"):
                                continue

                            # Check if we have yielded the first event
                            if not yielded_first_event:
                                # Emit the first chunk
                                if self.THOUGHT_OPEN.findall(iteration_buffer):
                                    is_thinking = True
                                    async for (
                                        line
                                    ) in SSEFormatter.yield_thinking_event(
                                        iteration_buffer
                                    ):
                                        yield line
                                else:
                                    async for (
                                        line
                                    ) in SSEFormatter.yield_message_event(
                                        iteration_buffer
                                    ):
                                        yield line

                                # Mark as yielded
                                yielded_first_event = True
                                continue

                            # Check if we are in a thinking block
                            if is_thinking:
                                # Still thinking, so keep yielding thinking events
                                if not self.THOUGHT_CLOSE.findall(
                                    iteration_buffer
                                ):
                                    # Emit SSE "thinking" event
                                    async for (
                                        line
                                    ) in SSEFormatter.yield_thinking_event(
                                        delta.content
                                    ):
                                        yield line

                                    continue
                                # Done thinking, so emit the last thinking event
                                else:
                                    is_thinking = False
                                    thought_text = delta.content.split(
                                        "</Thought>"
                                    )[0].split("</think>")[0]
                                    async for (
                                        line
                                    ) in SSEFormatter.yield_thinking_event(
                                        thought_text
                                    ):
                                        yield line
                                    post_thought_text = delta.content.split(
                                        "</Thought>"
                                    )[-1].split("</think>")[-1]
                                    delta.content = post_thought_text

                            # Extract bracket references from the entire iteration_buffer
                            #     so we find newly appeared short IDs
                            new_sids = extract_citations(iteration_buffer)
                            for sid in new_sids:
                                if sid not in announced_short_ids:
                                    announced_short_ids.add(sid)
                                    # SSE "citation"
                                    citation_evt_payload = {
                                        "id": f"cit_{sid}",
                                        "object": "citation",
                                        "payload": self.search_results_collector.find_by_short_id(
                                            sid
                                        ),
                                    }
                                    # Using SSEFormatter to yield a "citation" event
                                    async for (
                                        line
                                    ) in SSEFormatter.yield_citation_event(
                                        citation_evt_payload
                                    ):
                                        yield line

                            # Now prepare to emit the newly streamed text as a "message" event
                            if (
                                iteration_buffer.count("<")
                                and not in_action_block
                            ):
                                in_action_block = True

                            if (
                                in_action_block
                                and len(
                                    self.ACTION_PATTERN.findall(
                                        iteration_buffer
                                    )
                                )
                                < 2
                            ):
                                continue

                            elif in_action_block:
                                in_action_block = False
                                # Emit the post action block text, if it is there
                                post_action_text = iteration_buffer.split(
                                    "</Action>"
                                )[-1]
                                if post_action_text:
                                    async for (
                                        line
                                    ) in SSEFormatter.yield_message_event(
                                        post_action_text
                                    ):
                                        yield line

                            else:
                                async for (
                                    line
                                ) in SSEFormatter.yield_message_event(
                                    delta.content
                                ):
                                    yield line

                        elif finish_reason == "stop":
                            break

                    # 6) The LLM is done. If we have any leftover partial text,
                    #    finalize it in the conversation
                    if iteration_buffer:
                        await self.conversation.add_message(
                            Message(
                                role="assistant",
                                content=iteration_buffer,
                            )
                        )

                    # --- 4) Process any <Action>/<ToolCalls> blocks, or mark completed
                    action_matches = self.ACTION_PATTERN.findall(
                        iteration_buffer
                    )

                    if len(action_matches) > 0:
                        # Process each ToolCall
                        xml_toolcalls = "<ToolCalls>"

                        for action_block in action_matches:
                            tool_calls_text = []
                            # Look for ToolCalls wrapper, or use the raw action block
                            calls_wrapper = self.TOOLCALLS_PATTERN.findall(
                                action_block
                            )
                            if calls_wrapper:
                                for tw in calls_wrapper:
                                    tool_calls_text.append(tw)
                            else:
                                tool_calls_text.append(action_block)

                            for calls_region in tool_calls_text:
                                calls_found = self.TOOLCALL_PATTERN.findall(
                                    calls_region
                                )
                                for tc_block in calls_found:
                                    tool_name, tool_params = (
                                        self._parse_single_tool_call(tc_block)
                                    )
                                    if tool_name:
                                        # Emit SSE event for tool call
                                        tool_call_id = (
                                            f"call_{abs(hash(tc_block))}"
                                        )
                                        call_evt_data = {
                                            "tool_call_id": tool_call_id,
                                            "name": tool_name,
                                            "arguments": json.dumps(
                                                tool_params
                                            ),
                                        }
                                        async for (
                                            line
                                        ) in SSEFormatter.yield_tool_call_event(
                                            call_evt_data
                                        ):
                                            yield line

                                        try:
                                            tool_result = await self.handle_function_or_tool_call(
                                                tool_name,
                                                json.dumps(tool_params),
                                                tool_id=tool_call_id,
                                                save_messages=False,
                                            )
                                            result_content = (
                                                tool_result.llm_formatted_result
                                            )
                                        except Exception as e:
                                            result_content = f"Error in tool '{tool_name}': {str(e)}"

                                        xml_toolcalls += (
                                            f"<ToolCall>"
                                            f"<Name>{tool_name}</Name>"
                                            f"<Parameters>{json.dumps(tool_params)}</Parameters>"
                                            f"<Result>{result_content}</Result>"
                                            f"</ToolCall>"
                                        )

                                        # Emit SSE tool result for non-result tools
                                        result_data = {
                                            "tool_call_id": tool_call_id,
                                            "role": "tool",
                                            "content": json.dumps(
                                                convert_nonserializable_objects(
                                                    result_content
                                                )
                                            ),
                                        }
                                        async for (
                                            line
                                        ) in SSEFormatter.yield_tool_result_event(
                                            result_data
                                        ):
                                            yield line

                        xml_toolcalls += "</ToolCalls>"
                        pre_action_text = iteration_buffer[
                            : iteration_buffer.find(action_block)
                        ]
                        post_action_text = iteration_buffer[
                            iteration_buffer.find(action_block)
                            + len(action_block) :
                        ]
                        iteration_text = (
                            pre_action_text + xml_toolcalls + post_action_text
                        )
                        await self.conversation.add_message(
                            Message(
                                role="assistant",
                                content=iteration_text,
                            )
                        )
                    else:
                        # (a) Emit final answer SSE event
                        final_evt_payload = {
                            "id": "msg_final",
                            "object": "agent.final_answer",
                            "generated_answer": iteration_buffer,
                            "citations": [
                                {
                                    "id": f"cit_{sid}",
                                    "object": "citation",
                                    "payload": self.search_results_collector.find_by_short_id(
                                        sid
                                    ),
                                }
                                for sid in announced_short_ids
                            ],  # Optionally attach citations, tool calls, etc.
                        }
                        async for (
                            line
                        ) in SSEFormatter.yield_final_answer_event(
                            final_evt_payload
                        ):
                            yield line

                        # (b) Signal the end of the SSE stream
                        yield SSEFormatter.yield_done_event()
                        self._completed = True

            except Exception as e:
                logger.error(f"Error in streaming agent: {str(e)}")
                # Emit error event for client
                async for line in SSEFormatter.yield_error_event(
                    f"Agent error: {str(e)}"
                ):
                    yield line
                # Send done event to close the stream
                yield SSEFormatter.yield_done_event()

        # Finally, we return the async generator
        async for line in sse_generator():
            yield line

    def _parse_single_tool_call(
        self, toolcall_text: str
    ) -> Tuple[Optional[str], dict]:
        """
        Parse a ToolCall block to extract the name and parameters.

        Args:
            toolcall_text: The text content of a ToolCall block

        Returns:
            Tuple of (tool_name, tool_parameters)
        """
        name_match = self.NAME_PATTERN.search(toolcall_text)
        if not name_match:
            return None, {}
        tool_name = name_match.group(1).strip()

        params_match = self.PARAMS_PATTERN.search(toolcall_text)
        if not params_match:
            return tool_name, {}

        raw_params = params_match.group(1).strip()
        try:
            # Handle potential JSON parsing issues
            # First try direct parsing
            tool_params = json.loads(raw_params)
        except json.JSONDecodeError:
            # If that fails, try to clean up the JSON string
            try:
                # Replace escaped quotes that might cause issues
                cleaned_params = raw_params.replace('\\"', '"')
                # Try again with the cleaned string
                tool_params = json.loads(cleaned_params)
            except json.JSONDecodeError:
                # If all else fails, treat as a plain string value
                tool_params = {"value": raw_params}

        return tool_name, tool_params
