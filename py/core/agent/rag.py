import asyncio
import json
import logging
import random
import re
from typing import Any, AsyncGenerator, Callable, Optional, Tuple

import tiktoken
from google.genai.errors import ServerError

from core.agent import R2RAgent, R2RStreamingAgent, R2RStreamingReasoningAgent
from core.base import (
    CitationRelabeler,
    ToolCallData,
    ToolCallEvent,
    ToolResultData,
    ToolResultEvent,
    format_search_results_for_llm,
    yield_sse_event,
)
from core.base.abstractions import (
    AggregateSearchResult,
    ContextDocumentResult,
    GenerationConfig,
    Message,
    SearchSettings,
    WebSearchResponse,
)
from core.base.agent import AgentConfig, Tool
from core.base.providers import DatabaseProvider
from core.base.utils import convert_nonserializable_objects
from core.providers import (
    AnthropicCompletionProvider,
    LiteLLMCompletionProvider,
    OpenAICompletionProvider,
    R2RCompletionProvider,
)

logger = logging.getLogger(__name__)

COMPUTE_FAILURE = "<Response>I failed to reach a conclusion with my allowed compute.</Response>"


class SearchResultsCollector:
    """
    Collects search results in the form (source_type, result_obj, aggregator_index).
    aggregator_index increments globally so that the nth item appended
    is always aggregator_index == n, across the entire conversation.
    """

    def __init__(self):
        # We'll store a list of (source_type, result_obj, agg_idx).
        self._results_in_order: list[Tuple[str, Any, int]] = []
        self._next_index = 1  # 1-based indexing

    def add_aggregate_result(self, agg: "AggregateSearchResult"):
        """
        Flatten the chunk_search_results, graph_search_results, web_search_results,
        and context_document_results, each assigned a unique aggregator index.
        """
        if agg.chunk_search_results:
            for c in agg.chunk_search_results:
                self._results_in_order.append(("chunk", c, self._next_index))
                self._next_index += 1

        if agg.graph_search_results:
            for g in agg.graph_search_results:
                self._results_in_order.append(("graph", g, self._next_index))
                self._next_index += 1

        if agg.web_search_results:
            for w in agg.web_search_results:
                self._results_in_order.append(("web", w, self._next_index))
                self._next_index += 1

        if agg.context_document_results:
            for cd in agg.context_document_results:
                self._results_in_order.append(
                    ("contextDoc", cd, self._next_index)
                )
                self._next_index += 1

    def get_all_results(self) -> list[Tuple[str, Any, int]]:
        """
        Return list of (source_type, result_obj, aggregator_index),
        in the order appended.
        """
        return self._results_in_order


def num_tokens(text, model="gpt-4o"):
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    """Return the number of tokens used by a list of messages for both user and assistant."""
    return len(encoding.encode(text, disallowed_special=()))


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
        max_context_window_tokens=512_000,
        **kwargs,
    ):
        # Save references to the retrieval logic
        self.search_settings = search_settings
        self.local_search_method = local_search_method
        self.content_method = content_method
        self.max_tool_context_length = max_tool_context_length
        self.max_context_window_tokens = max_context_window_tokens
        self.search_results_collector = SearchResultsCollector()
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

    # Local Search Tool
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

        raw_response = await self.local_search_method(
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
            # item = { 'document': {...}, 'chunks': [...] }
            document = item["document"]
            document["metadata"].pop("chunk_metadata", None)
            context_document_results.append(
                ContextDocumentResult(
                    document=document,
                    chunks=[
                        chunk.get("text", "")
                        for chunk in item.get("chunks", [])
                    ],
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
        web_response = WebSearchResponse.from_serper_results(raw_results)

        agg = AggregateSearchResult(
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=web_response.organic_results,
        )
        self.search_results_collector.add_aggregate_result(agg)
        return agg

    def format_search_results_for_llm(
        self, results: AggregateSearchResult
    ) -> str:
        context = format_search_results_for_llm(
            results, self.search_results_collector
        )
        context_tokens = num_tokens(context) + 1
        frac_to_return = self.max_tool_context_length / (
            num_tokens(context) + 1
        )

        if frac_to_return > 1:
            return context
        else:
            return context[: int(frac_to_return * context_tokens)]


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
            | R2RCompletionProvider
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
            | R2RCompletionProvider
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

        # SSE generator function
        async def sse_generator() -> AsyncGenerator[str, None]:
            relabeler = CitationRelabeler()
            announced_refs = set()
            pending_tool_calls = {}
            partial_text_buffer = ""

            while not self._completed:
                msg_list = await self.conversation.get_messages()
                gen_cfg = self.get_generation_config(msg_list[-1], stream=True)
                llm_stream = self.llm_provider.aget_completion_stream(
                    msg_list, gen_cfg
                )

                async for chunk in llm_stream:
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason

                    # 1) Append partial text
                    if delta.content:
                        partial_text_buffer += delta.content

                        # A) Detect bracket references in the *entire* buffer or just the new substring.
                        bracket_pattern = re.compile(r"\[\s*(\d+)\s*\]")
                        for match in bracket_pattern.finditer(
                            partial_text_buffer
                        ):
                            old_ref = int(match.group(1))
                            # The CitationRelabeler simply assigns newRef=1,2,3,... in the order discovered:
                            new_ref = relabeler.get_or_assign_newref(old_ref)

                            # If we haven't "announced" a reference to `[old_ref]` yet, do so:
                            if old_ref not in announced_refs:
                                announced_refs.add(old_ref)

                                # Check if old_ref is actually within the aggregator range:
                                all_results = (
                                    self.search_results_collector.get_all_results()
                                )
                                if 1 <= old_ref <= len(all_results):
                                    # Grab that result
                                    (src_type, result_obj, agg_index) = (
                                        all_results[old_ref - 1]
                                    )
                                    # Build SSE "citation" payload
                                    citation_evt_payload = {
                                        "oldRef": old_ref,  # LLM's bracket number
                                        "newRef": new_ref,  # The re-labeled bracket
                                        "aggIndex": agg_index,
                                        "source_type": src_type,
                                        # You can attach metadata from result_obj if desired
                                        "sourceTitle": getattr(
                                            result_obj, "title", None
                                        ),
                                    }
                                    # Emit it
                                    async for line in yield_sse_event(
                                        "citation", citation_evt_payload
                                    ):
                                        yield line
                                else:
                                    # The LLM might have cited "[99]" but we have only 5 aggregator results, etc.
                                    # Up to you how to handle that.
                                    pass

                        # B) Rewrite the references in partial_text_buffer to use the newRef
                        rewritten_text = relabeler.rewrite_with_newrefs(
                            partial_text_buffer
                        )

                        # Only emit the newly added substring in SSE:
                        new_substring_start = len(rewritten_text) - len(
                            delta.content
                        )
                        new_text_to_emit = rewritten_text[new_substring_start:]

                        # SSE message event
                        msg_payload = {
                            "id": "msg_partial",
                            "object": "agent.message.delta",
                            "delta": {
                                "content": [
                                    {
                                        "type": "text",
                                        "payload": {
                                            "value": new_text_to_emit,
                                            "annotations": [],
                                        },
                                    }
                                ]
                            },
                        }
                        async for line in yield_sse_event(
                            "message", msg_payload
                        ):
                            yield line

                    # 2) Accumulate partial tool_calls if present
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in pending_tool_calls:
                                pending_tool_calls[idx] = {
                                    "id": tc.id,
                                    "name": tc.function.name or "",
                                    "arguments": tc.function.arguments or "",
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

                    # 3) If finish_reason == "tool_calls", we freeze partial content and do calls
                    if finish_reason == "tool_calls":
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

                        # SSE "tool_call" events
                        for c in calls_list:
                            tc_data = ToolCallData(**c)
                            tc_evt = ToolCallEvent(
                                event="tool_call", data=tc_data
                            )
                            async for line in yield_sse_event(
                                "tool_call", tc_evt.dict()["data"]
                            ):
                                yield line

                        # Store an assistant message capturing these calls
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

                        # Execute each tool call in parallel
                        tool_results = await asyncio.gather(
                            *[
                                self.handle_function_or_tool_call(
                                    c["name"],
                                    c["arguments"],
                                    tool_id=c["tool_call_id"],
                                )
                                for c in calls_list
                            ]
                        )

                        # SSE "tool_result" for each
                        for cinfo, result_obj in zip(calls_list, tool_results):
                            result_data = ToolResultData(
                                tool_call_id=cinfo["tool_call_id"],
                                role="tool",
                                content=json.dumps(
                                    convert_nonserializable_objects(
                                        result_obj.raw_result.as_dict()
                                    )
                                ),
                            )
                            result_evt = ToolResultEvent(
                                event="tool_result", data=result_data
                            )
                            async for line in yield_sse_event(
                                "tool_result", result_evt.dict()["data"]
                            ):
                                yield line

                        # Clear partial_text and pending calls
                        pending_tool_calls.clear()
                        partial_text_buffer = ""

                    elif finish_reason == "stop":
                        # The LLM is done. Save leftover partial_text_buffer as a final assistant message
                        if partial_text_buffer:
                            await self.conversation.add_message(
                                Message(
                                    role="assistant",
                                    content=partial_text_buffer,
                                )
                            )

                        # SSE final_answer (with references all replaced)
                        final_text = relabeler.finalize_all_citations(
                            partial_text_buffer
                        )
                        final_evt_payload = {
                            "id": "msg_final",
                            "object": "agent.final_answer",
                            "generated_answer": final_text,
                            "citations": relabeler.get_mapping(),
                        }
                        async for line in yield_sse_event(
                            "final_answer", final_evt_payload
                        ):
                            yield line

                        # SSE done
                        yield "event: done\n"
                        yield "data: [DONE]\n\n"

                        self._completed = True
                        break

            if not self._completed:
                yield "event: done\n"
                yield "data: [DONE]\n\n"
                self._completed = True

        # Return the SSE generator
        async for line in sse_generator():
            yield line


class R2RStreamingReasoningRAGAgent(RAGAgentMixin, R2RStreamingReasoningAgent):
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
            | R2RCompletionProvider
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
        R2RStreamingReasoningAgent.__init__(
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


class R2RXMLToolsStreamingReasoningRAGAgent(R2RStreamingReasoningRAGAgent):
    """
    Abstract base class for a streaming-capable RAG Agent that:
      - Streams chain-of-thought tokens vs. normal text
      - Accumulates final text for parsing <Action><ToolCalls>
      - Executes any requested tool calls (max_steps enforced)
      - Produces a final <Response> or failure if max steps are exceeded

    You must override:
      - _generate_thinking_response(user_prompt: str)
    """

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: Optional[Any],
        config: AgentConfig,
        search_settings: SearchSettings,
        rag_generation_config: GenerationConfig,
        local_search_method: Callable,
        content_method: Optional[Callable] = None,
        max_tool_context_length: int = 20_000,
        max_steps: int = 10,  # limit on number of tool calls
    ):
        super().__init__(
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            search_settings=search_settings,
            rag_generation_config=rag_generation_config,
            local_search_method=local_search_method,
            content_method=content_method,
            max_tool_context_length=max_tool_context_length,
        )

        self.max_steps = max_steps
        self.current_step_count = 0

    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Iterative approach with chain-of-thought wrapped in <Thought>...</Thought> each iteration.
        1) In each iteration (up to max_steps):
            a) Call _generate_thinking_response(conversation_context).
            b) Stream chain-of-thought tokens *inline* but enclosed by <Thought>...</Thought>.
            c) Collect "assistant" tokens (is_thought=False) in a buffer to parse after.
            d) Parse <Action> blocks; if any <Action> has <Response>, yield it & stop.
            e) Else, if there's a bare <Response> outside <Action>, yield & stop.
            f) If still no <Response>, append iteration text to context, move to next iteration.
        2) If we exhaust steps, yield fallback <Response>.
        """

        # Step 1) Setup conversation
        await self._setup(system_instruction=system_instruction)
        if messages:
            for msg in messages:
                await self.conversation.add_message(msg)

        for step_i in range(self.max_steps):
            iteration_text = ""

            messages_list = await self.conversation.get_messages()
            generation_config = self.get_generation_config(
                messages_list[-1], stream=True
            )

            stream = self.llm_provider.aget_completion_stream(
                messages_list,
                generation_config,
            )
            thought_text, action_text, in_thought = "", "", True

            closing_detected = False
            async for stream_delta in self.process_llm_response(
                stream, *args, **kwargs
            ):
                # Map deepseek `think` tags to `Thought` tags
                stream_delta = stream_delta.replace(
                    "<think>", "<Thought>"
                ).replace("</think>", "</Thought>")
                if "</" not in stream_delta and not closing_detected:
                    thought_text += stream_delta
                    yield stream_delta
                else:
                    closing_detected = True
                    if in_thought:
                        if ">" not in stream_delta:
                            continue
                        else:
                            in_thought = False
                            thought_text += "</Thought>"
                            yield "</Thought>"
                            action_text += stream_delta.split(">")[-1]
                        in_thought = False
                    else:
                        action_text += stream_delta
            iteration_text += thought_text
            try:
                parsed_tool_calls = self._parse_tool_calls(action_text)
            except Exception as e:
                logger.error(f"Failed to parse tool calls: {e}")
                iteration_text += (
                    f"<Thought>Failed to parse tool calls: {e}</Thought>"
                )
                await self.conversation.add_message(
                    Message(role="assistant", content=iteration_text)
                )

                yield f"<Thought>Failed to parse tool calls: {e}</Thought>"
                continue

            logger.debug(f"action_text:\n{action_text}")
            logger.debug(f"parsed_tool_calls:\n{parsed_tool_calls}")
            if "<Response>" in action_text:
                yield "<Response>" + action_text.split("<Response>")[-1].split(
                    "</Response>"
                )[0] + "</Response>"
                return
            # If there are tool calls, execute them concurrently and build the XML block with results
            if parsed_tool_calls:
                # Create tasks for each tool call
                tasks = []
                for call in parsed_tool_calls:
                    # Log the call before executing
                    yield f"\n\n<Thought>Calling function: {call['name']}, with payload {call['params']}</Thought>"
                    tasks.append(
                        asyncio.create_task(
                            self.execute_tool(call["name"], **call["params"])
                        )
                    )

                # Wait for all tool calls to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Build the XML block containing the original tool calls and their results
                xml_toolcalls = "<ToolCalls>"
                for call, result in zip(parsed_tool_calls, results):

                    if call["name"] == "result":
                        logger.info(
                            f"Returning response = {call['params']['answer']}"
                        )
                        yield f"<Response>{call['params']['answer']}</Response>"
                        return

                    # Handle exceptions if any
                    if isinstance(result, Exception):
                        result_str = (
                            f"Error executing tool '{call['name']}': {result}"
                        )
                    else:
                        result_str = str(result)
                    xml_toolcalls += (
                        f"<ToolCall>"
                        f"<Name>{call['name']}</Name>"
                        f"<Parameters>{json.dumps(call['params'])}</Parameters>"
                        f"<Result>{result_str}</Result>"
                        f"</ToolCall>"
                    )
                xml_toolcalls += "</ToolCalls>"

                # Append the XML block to the conversation context in its original format
                iteration_text += f"<Action>{xml_toolcalls}</Action>"
                # Optionally yield the XML block so that the user sees it
                # yield f"\n\n<Action>{xml_toolcalls}</Action>"
            else:
                iteration_text += f"<Thought>No tool calls found in this step, trying again. If I have completed my response I should use the `result` tool.</Thought>"
                yield f"<Thought>No tool calls found in this step, trying again. If I have completed my response I should use the `result` tool.</Thought>"

            await self.conversation.add_message(
                Message(role="assistant", content=iteration_text)
            )

            if step_i == self.max_steps - 1:
                yield COMPUTE_FAILURE
                return

    def _build_single_user_prompt(self, conversation_msgs: list[dict]) -> str:
        """
        Converts system+user+assistant messages into a single text prompt.
        Overridable if you want a different style.
        """
        system_msgs = []
        user_msgs = []
        for msg in conversation_msgs:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                system_msgs.append(f"[System]\n{content}\n")
            elif role == "user":
                user_msgs.append(f"[User]\n{content}\n")
            elif role == "assistant":
                user_msgs.append(f"[Assistant]\n{content}\n")

        return "\n".join(system_msgs + user_msgs)

    @staticmethod
    def _parse_tool_calls(text: str) -> list[dict]:
        """
        Parse tool calls from XML-like text.

        This function locates <Action> blocks (or, if not present, the entire text)
        and then extracts all <ToolCall> blocks within. It patches incomplete tags and
        logs debug information along the way.

        Special Handling:
        - If a "<Name>result</Name>" tag is found, returns a single tool call
            with the name "result" and its associated parameters.
        """
        # Log the initial (possibly large) text truncated for debugging.
        logger.debug(
            "Starting _parse_tool_calls with text (first 500 chars): %s",
            text[:500],
        )

        original_text = text

        # --- Patch incomplete closing tags ---
        # Ensure that any '</Action' or '</ToolCalls' missing a '>' are fixed.
        text = re.sub(r"(</Action)(?!\s*>)", r"\1>", text)
        text = re.sub(r"(</ToolCalls)(?!\s*>)", r"\1>", text)
        if text != original_text:
            logger.debug("Patched incomplete closing tags in text.")

        # If an <Action> is found without a closing </Action>, append one.
        if "<Action>" in text and "</Action>" not in text:
            logger.debug(
                "Incomplete <Action> tag detected; appending a closing </Action> tag."
            )
            text += "</Action>"

        tool_calls = []

        # --- Special handling for result tool call ---
        if "<Name>result</Name>" in text:
            logger.debug(
                "Detected '<Name>result</Name>' in text; processing as a result tool call."
            )
            try:
                raw_params = (
                    text.split("<Parameters>")[-1]
                    .split("</Parameters>")[0]
                    .strip()
                )[12:-2]
                answer = (
                    json.loads(raw_params)
                    if raw_params.startswith("{")
                    else raw_params
                )
            except Exception as e:
                logger.warning("Failed to parse result answer: %s", e)
                answer = raw_params
            tool_calls.append({"name": "result", "params": {"answer": answer}})
            logger.debug("Returning result tool call: %s", tool_calls)
            return tool_calls

        # --- Locate <Action> blocks ---
        action_pattern = re.compile(
            r"<Action>(.*?)</Action>", re.DOTALL | re.IGNORECASE
        )
        action_matches = action_pattern.findall(text)
        logger.debug("Found %d <Action> blocks.", len(action_matches))

        # If no <Action> blocks are found, attempt to use the entire text.
        if not action_matches:
            logger.debug(
                "No <Action> blocks found; attempting to parse entire text for <ToolCall> blocks."
            )
            action_matches = [text]

        # Process each Action block
        for idx, action in enumerate(action_matches):
            logger.debug(
                "Processing Action block %d (first 200 chars): %s",
                idx,
                action.strip()[:200],
            )
            toolcall_pattern = re.compile(
                r"<ToolCall>(.*?)</ToolCall>", re.DOTALL | re.IGNORECASE
            )
            toolcall_matches = toolcall_pattern.findall(action)
            logger.debug(
                "Found %d <ToolCall> blocks in Action block %d.",
                len(toolcall_matches),
                idx,
            )

            for jdx, tc in enumerate(toolcall_matches):
                logger.debug(
                    "Processing ToolCall block %d in Action block %d (first 200 chars): %s",
                    jdx,
                    idx,
                    tc.strip()[:200],
                )
                # Extract the tool name
                name_match = re.search(
                    r"<Name>(.*?)</Name>", tc, re.DOTALL | re.IGNORECASE
                )
                if not name_match:
                    logger.debug(
                        "ToolCall block %d in Action block %d missing <Name> tag. Skipping.",
                        jdx,
                        idx,
                    )
                    continue
                tool_name = name_match.group(1).strip()
                logger.debug("Extracted tool name: '%s'", tool_name)
                # Extract parameters
                params_match = re.search(
                    r"<Parameters>(.*?)</Parameters>",
                    tc,
                    re.DOTALL | re.IGNORECASE,
                )
                if params_match:
                    raw_params = params_match.group(1).strip()
                    try:
                        tool_params = json.loads(raw_params)
                        logger.debug(
                            "Parsed parameters for tool '%s': %s",
                            tool_name,
                            tool_params,
                        )
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "JSON decode error for tool '%s' parameters: %s. Error: %s",
                            tool_name,
                            raw_params,
                            e,
                        )
                        tool_params = {}
                else:
                    logger.debug(
                        "No <Parameters> found for tool '%s'. Defaulting to empty dict.",
                        tool_name,
                    )
                    tool_params = {}

                tool_calls.append({"name": tool_name, "params": tool_params})

        logger.debug("Final parsed tool calls: %s", tool_calls)
        return tool_calls


class GeminiXMLToolsStreamingReasoningRAGAgent(
    R2RXMLToolsStreamingReasoningRAGAgent
):
    """
    A Gemini-based implementation that uses the `XMLToolsStreamingRAGAgentBase`.
    """

    def __init__(
        self,
        *args,
        gemini_api_key: str = "",
        gemini_model_name: str = "gemini-2.0-flash-thinking-exp",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        import os

        from google import genai  # "pip install google-genai"

        key = gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError(
                "Gemini API key not provided or set in environment."
            )
        self.gemini_client = genai.Client(
            api_key=key,
            http_options={"api_version": "v1alpha"},
        )
        self.gemini_model_name = gemini_model_name

    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Iterative approach with chain-of-thought wrapped in <Thought>...</Thought> each iteration.
        1) In each iteration (up to max_steps):
            a) Call _generate_thinking_response(conversation_context).
            b) Stream chain-of-thought tokens *inline* but enclosed by <Thought>...</Thought>.
            c) Collect "assistant" tokens (is_thought=False) in a buffer to parse after.
            d) Parse <Action> blocks; if any <Action> has <Response>, yield it & stop.
            e) Else, if there's a bare <Response> outside <Action>, yield & stop.
            f) If still no <Response>, append iteration text to context, move to next iteration.
        2) If we exhaust steps, yield fallback <Response>.
        """

        # Step 1) Setup conversation
        await self._setup(system_instruction=system_instruction)
        if messages:
            for msg in messages:
                await self.conversation.add_message(msg)

        # Build initial conversation context from all messages
        all_msgs = await self.conversation.get_messages()
        conversation_context = self._build_single_user_prompt(all_msgs)

        for step_i in range(self.max_steps):
            # We'll collect final text tokens to parse for <Action>/<Response>.
            assistant_text_buffer = []
            # Track whether we are “inside” a <Thought> block while streaming:
            inside_thought_block = False

            conversation_context += "\n\n[Assistant]\n"

            # Step 2) Single LLM call => yields (is_thought, text) pairs
            async for (
                is_thought,
                token_text,
            ) in self._generate_thinking_response(
                conversation_context, **kwargs
            ):
                if is_thought:
                    # Stream chain-of-thought text *inline*, but bracket with <Thought>...</Thought>
                    if not inside_thought_block:
                        inside_thought_block = True
                        conversation_context += "<Thought>"
                        yield "<Thought>"
                    conversation_context += token_text
                    yield token_text
                else:
                    # If we were inside a thought block, close it
                    if inside_thought_block:
                        conversation_context += "</Thought>"
                        yield "</Thought>"
                        inside_thought_block = False

                    # “Assistant text” is user-facing text that we
                    # will parse for <Action> or <Response>
                    assistant_text_buffer.append(token_text)

            # If the model ended while still in a thought block, close it
            if inside_thought_block:
                conversation_context += "</Thought>"
                yield "</Thought>"

            # Step 3) Combine the final user-facing tokens
            iteration_text = "".join(assistant_text_buffer).strip()

            #
            # 3a) Parse out <Action> blocks
            #
            parsed_actions = self._parse_action_blocks(iteration_text)

            pre_text = iteration_text.split("<Action>")[0]
            conversation_context += pre_text

            if parsed_actions:
                # For each action block, see if it has <ToolCalls>, <Response>
                for action_block in parsed_actions:

                    # Prepare two separate <ToolCalls> blocks:
                    #  - "toolcalls_xml": with <Result> inside (for conversation_context)
                    #  - "toolcalls_minus_results": no <Result> (to show user)
                    toolcalls_xml = "<ToolCalls>"
                    toolcalls_minus_results = "<ToolCalls>"

                    # Execute any tool calls
                    for tc in action_block["tool_calls"]:
                        name = tc["name"]
                        params = tc["params"]
                        logger.info(f"Executing tool '{name}' with {params}")

                        if name == "result":
                            logger.info(
                                f"Returning response = {params['answer']}"
                            )
                            yield f"<Response>{params['answer']}</Response>"
                            return

                        # Build the <ToolCall> to show user (minus <Result>)
                        minimal_toolcall = (
                            f"<ToolCall>"
                            f"<Name>{name}</Name>"
                            f"<Parameters>{json.dumps(params)}</Parameters>"
                            f"</ToolCall>"
                        )
                        toolcalls_minus_results += minimal_toolcall

                        # Build the <ToolCall> with results for context
                        toolcall_with_result = (
                            f"<ToolCall>"
                            f"<Name>{name}</Name>"
                            f"<Parameters>{json.dumps(params)}</Parameters>"
                        )
                        try:
                            result = await self.execute_tool(name, **params)

                            context_tokens = num_tokens(str(result))
                            max_to_result = (
                                self.max_tool_context_length / context_tokens
                            )

                            if max_to_result < 1:
                                result = (
                                    str(result)[
                                        0 : int(max_to_result * context_tokens)
                                    ]
                                    + "... RESULT TRUNCATED DUE TO MAX LENGTH ..."
                                )
                        except Exception as e:
                            result = f"Error executing tool '{name}': {e}"

                        toolcall_with_result += (
                            f"<Result>{result}</Result></ToolCall>"
                        )

                        toolcalls_xml += toolcall_with_result

                    toolcalls_xml += "</ToolCalls>"
                    toolcalls_minus_results += "</ToolCalls>"

                    # Yield the no-results block so user sees the calls
                    yield toolcalls_minus_results

                    # Otherwise, embed the <ToolCalls> with <Result> in conversation context
                    conversation_context += f"<Action>{toolcalls_xml}</Action>"

            else:
                #
                # 3b) If no <Action> blocks at all, yield the iteration text below
                failed_iteration_text = "<Action><ToolCalls></ToolCalls><Response>I failed to use any tools, I should probably return a response with the `result` tool now.</Response></Action>"
                context_size = num_tokens(conversation_context)
                if context_size > self.max_context_window_tokens:
                    yield COMPUTE_FAILURE
                    return

                yield failed_iteration_text + f"\n\n[System]\n{step_i+1} steps completed, no <Action> blocks found. {context_size} tokens in context out of {self.max_context_window_tokens} consumed."
                conversation_context += failed_iteration_text
                continue

            post_text = iteration_text.split("</Action>")[-1]
            conversation_context += post_text
            context_size = num_tokens(conversation_context)
            if context_size > self.max_context_window_tokens:
                yield COMPUTE_FAILURE
                return
            conversation_context += f"\n\n[System]\n{step_i+1} steps completed. {context_size} tokens in context out of {self.max_context_window_tokens} consumed."
        # If we finish all steps with no <Response>, yield fallback:
        yield COMPUTE_FAILURE
        return

    async def _generate_thinking_response(
        self,
        user_prompt: str,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        **kwargs,
    ) -> AsyncGenerator[tuple[bool, str], None]:
        """
        Generate thinking response with retry logic for handling transient failures.

        Args:
            user_prompt: The prompt to send to Gemini
            max_retries: Maximum number of retry attempts (default: 3)
            initial_delay: Initial delay between retries in seconds (default: 1.0)
            **kwargs: Additional arguments passed to generate_content

        Yields:
            Tuples of (is_thought: bool, text: str)
        """
        config = {
            "thinking_config": {"include_thoughts": True},
            # "max_output_tokens": 8192,
        }

        attempt = 0
        last_error = None

        while attempt <= max_retries:
            try:
                response = self.gemini_client.models.generate_content(
                    model=self.gemini_model_name,
                    contents=user_prompt,
                    config=config,
                )

                # Handle empty response
                if not response.candidates:
                    yield (
                        False,
                        "I failed to retrieve a valid Gemini response.",
                    )
                    return

                # Process successful response
                for part in response.candidates[0].content.parts:
                    if part.thought:
                        yield (True, part.text)
                    else:
                        yield (False, part.text)
                return  # Success - exit the retry loop

            except ServerError as e:
                last_error = e
                attempt += 1

                if attempt <= max_retries:
                    # Exponential backoff with jitter
                    delay = (
                        initial_delay
                        * (2 ** (attempt - 1))
                        * (0.5 + random.random())
                    )
                    await asyncio.sleep(delay)
                else:
                    # All retries exhausted
                    error_msg = f"Failed after {max_retries} attempts. Last error: {str(last_error)}"
                    yield (False, error_msg)
                    return

    def _parse_action_blocks(self, text: str) -> list[dict]:
        """
        Find <Action>...</Action> blocks in 'text' using simple regex,
        then parse out <ToolCall> blocks within each <Action>.

        Returns a list of dicts, each with:
        {
            "tool_calls": [
                {"name": <tool_name>, "params": <dict>},
                ...
            ],
            "response": <str or None if no <Response> found>
        }
        """

        ### HARDCODE RESULT PARSING DUE TO TROUBLES
        if "<Name>result</Name>" in text:
            return [
                {
                    "tool_calls": [
                        {
                            "name": "result",
                            "params": {
                                "answer": text.split("<Parameters>")[-1]
                                .split("</Parameters>")[0]
                                .strip()[12:-2]
                            },
                        }
                    ],
                    "response": None,
                }
            ]

        results = []

        # 1) Find all <Action>...</Action> blocks
        action_pattern = re.compile(
            r"<Action>(.*?)</Action>", re.DOTALL | re.IGNORECASE
        )
        action_matches = action_pattern.findall(text)

        for action_content in action_matches:
            block_data = {
                "tool_calls": [],
                "response": None,
            }

            # 2) Within each <Action> block, find all <ToolCall>...</ToolCall> blocks
            toolcall_pattern = re.compile(
                r"<ToolCall>(.*?)</ToolCall>", re.DOTALL | re.IGNORECASE
            )
            toolcall_matches = toolcall_pattern.findall(action_content)

            for tc_text in toolcall_matches:
                # Look for <Name>...</Name> and <Parameters>...</Parameters>
                name_match = re.search(
                    r"<Name>(.*?)</Name>", tc_text, re.DOTALL | re.IGNORECASE
                )
                params_match = re.search(
                    r"<Parameters>(.*?)</Parameters>",
                    tc_text,
                    re.DOTALL | re.IGNORECASE,
                )

                if not name_match:
                    continue  # no <Name> => skip

                tool_name = name_match.group(1).strip()

                # If <Parameters> is present, try to parse as JSON
                if params_match:
                    raw_params = params_match.group(1).strip()
                    try:
                        tool_params = json.loads(raw_params)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to parse JSON from <Parameters>: {raw_params}"
                        )
                        tool_params = {}
                else:
                    tool_params = {}

                block_data["tool_calls"].append(
                    {"name": tool_name, "params": tool_params}
                )

            # 3) Optionally, see if there's a <Response>...</Response> in the same <Action> block
            response_pattern = re.compile(
                r"<Response>(.*?)</Response>", re.DOTALL | re.IGNORECASE
            )
            response_match = response_pattern.search(action_content)
            if response_match:
                block_data["response"] = response_match.group(1).strip()

            results.append(block_data)

        return results


def dump_collector(collector: SearchResultsCollector) -> list[dict[str, Any]]:
    dumped = []
    for source_type, result_obj, _ in collector.get_all_results():
        # Get the dictionary from the result object
        if hasattr(result_obj, "model_dump"):
            result_dict = result_obj.model_dump()
        elif hasattr(result_obj, "dict"):
            result_dict = result_obj.dict()
        else:
            result_dict = (
                result_obj  # Fallback if no conversion method is available
            )

        # Use the recursive conversion on the entire dictionary
        result_dict = convert_nonserializable_objects(result_dict)

        dumped.append(
            {
                "source_type": source_type,
                "result": result_dict,
            }
        )
    return dumped


def tokens_count_for_message(message, encoding):
    """Return the number of tokens used by a single message."""
    tokens_per_message = 3

    num_tokens = 0
    num_tokens += tokens_per_message
    if message.get("function_call"):
        num_tokens += len(encoding.encode(message["function_call"]["name"]))
        num_tokens += len(
            encoding.encode(message["function_call"]["arguments"])
        )
    elif message.get("tool_calls"):
        for tool_call in message["tool_calls"]:
            num_tokens += len(encoding.encode(tool_call["function"]["name"]))
            num_tokens += len(
                encoding.encode(tool_call["function"]["arguments"])
            )
    else:
        num_tokens += len(encoding.encode(message["content"]))

    return num_tokens


def num_tokens_from_messages(messages, model="gpt-4o"):
    """Return the number of tokens used by a list of messages for both user and assistant."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        logger.warning("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = 0
    for i, message in enumerate(messages):
        tokens += tokens_count_for_message(messages[i], encoding)

        tokens += 3  # every reply is primed with assistant
    return tokens
