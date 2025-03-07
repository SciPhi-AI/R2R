import asyncio
import json
import logging
import re
import uuid
from typing import Any, AsyncGenerator, Callable, Optional, Set, Tuple

from core.agent import R2RAgent
from core.base import (
    CitationData,
    FinalAnswerData,
    ToolCallData,
    ToolCallEvent,
    ToolResultData,
    ToolResultEvent,
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
    yield_sse_event,
)

logger = logging.getLogger(__name__)

COMPUTE_FAILURE = "<Response>I failed to reach a conclusion with my allowed compute.</Response>"


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
            local_search_method=local_search_method,
            content_method=content_method,
        )


class R2RStreamingRAGAgent(RAGAgentMixin, R2RAgent):
    """
    Streaming-capable RAG Agent that supports local_search, content, web_search,
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
        local_search_method: Callable,
        content_method: Optional[Callable] = None,
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

        async def sse_generator() -> AsyncGenerator[str, None]:
            announced_short_ids = set()
            pending_tool_calls = {}
            partial_text_buffer = ""

            # Keep streaming until we complete
            while not self._completed:
                # 1) Get current messages
                msg_list = await self.conversation.get_messages()
                gen_cfg = self.get_generation_config(msg_list[-1], stream=True)

                # 2) Start streaming from LLM
                llm_stream = self.llm_provider.aget_completion_stream(
                    msg_list, gen_cfg
                )
                async for chunk in llm_stream:
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason

                    if hasattr(delta, "thinking") and delta.thinking:
                        # Emit SSE "thinking" event
                        async for line in SSEFormatter.yield_thinking_event(
                            delta.thinking
                        ):
                            yield line

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
                                    "object": "agent.citation",
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

                    # 4) Accumulate partial tool calls if present
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

                    # 5) If the stream signals we should handle "tool_calls"
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

        # Finally, we return the async generator
        async for line in sse_generator():
            yield line


TOOLCALL_PATTERN = re.compile(r"<ToolCall>(.*?)</ToolCall>", re.DOTALL | re.IGNORECASE)
NAME_PATTERN = re.compile(r"<Name>(.*?)</Name>", re.DOTALL | re.IGNORECASE)
PARAMS_PATTERN = re.compile(r"<Parameters>(.*?)</Parameters>", re.DOTALL | re.IGNORECASE)

class R2RXMLToolsStreamingRAGAgent(R2RStreamingRAGAgent):
    """
    A streaming RAG agent that works exactly like R2RStreamingRAGAgent,
    except we parse <ToolCall> blocks from the text itself to decide
    what tools to call (instead of relying on `delta.tool_calls`).

    If the LLM includes something like:
      <ToolCall>
        <Name>local_search</Name>
        <Parameters>{"query": "some text"}</Parameters>
      </ToolCall>

    then we detect that in the output and run 'local_search' with
    the specified parameters. Once we see a finish_reason="tool_calls",
    we invoke those calls, produce "tool_call" SSE, "tool_result" SSE, etc.
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
        local_search_method,
        content_method: Optional[Any] = None,
        max_tool_context_length: int = 20_000,
    ):
        # Force streaming on
        config.stream = True

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

    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Same streaming flow as R2RStreamingRAGAgent, but we parse out <ToolCall> blocks
        from the text to figure out tool calls. 
        """

        # Reset internal flags
        self._reset()
        await self._setup(system_instruction)

        # Optionally add any initial messages to conversation
        if messages:
            for m in messages:
                await self.conversation.add_message(m)

        async def sse_generator() -> AsyncGenerator[str, None]:
            # Keep streaming until we finalize
            while not self._completed:
                # Prepare messages & generation config
                msg_list = await self.conversation.get_messages()
                gen_cfg = self.get_generation_config(msg_list[-1], stream=True)
                llm_stream = self.llm_provider.aget_completion_stream(msg_list, gen_cfg)

                # We accumulate text from partial chunks here:
                partial_text_buffer = ""

                async for chunk in llm_stream:
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason

                    # 1) If there's any "thinking" token (depends on your LLM provider),
                    #    we can emit that as SSE "thinking":
                    if getattr(delta, "thinking", None):
                        async for line in SSEFormatter.yield_thinking_event(delta.thinking):
                            yield line

                    # 2) If there's new text content from the LLM, we show it to the user
                    #    as SSE "message", but also keep it in partial_text_buffer
                    if delta.content:
                        partial_text_buffer += delta.content
                        # SSE "message"
                        async for line in SSEFormatter.yield_message_event(delta.content):
                            yield line

                    # 3) If the LLM signals "tool_calls," we parse them from partial_text_buffer
                    if finish_reason == "tool_calls":
                        # Parse <ToolCall> blocks from partial_text_buffer
                        tool_calls = self._extract_tool_calls(partial_text_buffer)

                        # SSE "tool_call" events, then run the tools
                        results_text = ""
                        for i, call in enumerate(tool_calls):
                            tool_call_id = f"xmltool_{uuid.uuid4()}"
                            # SSE tool_call
                            tc_data = ToolCallData(
                                tool_call_id=tool_call_id,
                                name=call["name"],
                                arguments=json.dumps(call["arguments"]),
                            )
                            evt = ToolCallEvent(event="tool_call", data=tc_data)
                            async for line in SSEFormatter.yield_tool_call_event(evt.data.dict()):
                                yield line

                            # Actually execute the tool
                            tool_result = await self.handle_function_or_tool_call(
                                call["name"],
                                json.dumps(call["arguments"]),
                                tool_id=tool_call_id,
                            )

                            # SSE tool_result
                            tool_result_data = ToolResultData(
                                tool_call_id=tool_call_id,
                                role="tool",
                                content=json.dumps(
                                    convert_nonserializable_objects(tool_result.raw_result.as_dict())
                                ),
                            )
                            tr_evt = ToolResultEvent(event="tool_result", data=tool_result_data)
                            async for line in SSEFormatter.yield_tool_result_event(tr_evt.data.dict()):
                                yield line

                            # We'll embed the result back into partial_text_buffer so that
                            # the next iteration of the LLM can see it in conversation
                            # if it references <ToolCall><Result>...
                            # This is up to you how you want to represent it.
                            results_text += (
                                "<ToolCall>"
                                f"<Name>{call['name']}</Name>"
                                f"<Parameters>{json.dumps(call['arguments'])}</Parameters>"
                                f"<Result>{json.dumps(tool_result.raw_result.as_dict())}</Result>"
                                "</ToolCall>\n"
                            )

                        # Now we put partial_text_buffer + results into an assistant message
                        combined_content = partial_text_buffer + "\n" + results_text
                        await self.conversation.add_message(
                            Message(role="assistant", content=combined_content)
                        )

                        # Then we break out of the chunk loop to prompt the LLM again.
                        break

                    # 4) If the LLM signals "stop," it’s done streaming – finalize.
                    if finish_reason == "stop":
                        # SSE final_answer
                        final_evt_payload = FinalAnswerData(generated_answer=partial_text_buffer)
                        async for line in SSEFormatter.yield_final_answer_event(final_evt_payload.dict()):
                            yield line

                        # SSE done
                        yield SSEFormatter.yield_done_event()
                        self._completed = True
                        return

                # If we exhausted the llm_stream but didn't get a "tool_calls" finish_reason,
                # that means we are done or the LLM provided no more output. Let's finalize here:
                else:
                    # We'll finalize in case LLM didn't produce finish_reason=stop
                    final_evt_payload = FinalAnswerData(generated_answer=partial_text_buffer)
                    async for line in SSEFormatter.yield_final_answer_event(final_evt_payload.dict()):
                        yield line
                    yield SSEFormatter.yield_done_event()
                    self._completed = True
                    return

            # If we exit the while loop (unexpected), finalize:
            if not self._completed:
                final_evt_payload = FinalAnswerData(generated_answer="No conclusion produced.")
                async for line in SSEFormatter.yield_final_answer_event(final_evt_payload.dict()):
                    yield line
                yield SSEFormatter.yield_done_event()
                self._completed = True

        # Return the actual SSE generator
        async for line in sse_generator():
            yield line

    def _extract_tool_calls(self, text: str) -> list[dict]:
        """
        Find all <ToolCall> blocks in text, parse <Name> and <Parameters>,
        returns list[{"name": str, "arguments": dict}].
        Example:
          <ToolCall>
            <Name>local_search</Name>
            <Parameters>{"query": "some text"}</Parameters>
          </ToolCall>
        """
        tool_calls = []
        matches = TOOLCALL_PATTERN.findall(text)
        for tblock in matches:
            name_match = NAME_PATTERN.search(tblock)
            params_match = PARAMS_PATTERN.search(tblock)
            if name_match:
                tool_name = name_match.group(1).strip()
            else:
                tool_name = "unknown_tool"
            if params_match:
                raw_params = params_match.group(1).strip()
                try:
                    arguments = json.loads(raw_params)
                except json.JSONDecodeError:
                    arguments = {"raw_params": raw_params}
            else:
                arguments = {}

            tool_calls.append({"name": tool_name, "arguments": arguments})
        return tool_calls
