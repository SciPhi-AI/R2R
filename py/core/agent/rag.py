
import asyncio
import json
import logging
import re
import uuid
from typing import Any, AsyncGenerator, Callable, Optional, Set, Tuple

from core.agent import R2RAgent, R2RStreamingAgent, R2RStreamingReasoningAgent
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
from core.utils import convert_nonserializable_objects, yield_sse_event, num_tokens, SearchResultsCollector, extract_citations, SSEFormatter

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



class R2RStreamingRAGAgent(RAGAgentMixin, R2RStreamingAgent):
    """
    Streaming-capable RAG Agent that supports local_search, content, web_search,
    but now emits citations as [abc1234] short IDs if the LLM includes them in brackets.
    """

    # These two regexes will detect bracket references and then find short IDs.
    # If your IDs are exactly 8 characters (like "e43864f5"), you can update the pattern:
    # SHORT_ID_PATTERN = re.compile(r"[A-Za-z0-9]{8}")
    BRACKET_PATTERN = re.compile(r"\[([^\]]+)\]")
    SHORT_ID_PATTERN = re.compile(r"[A-Za-z0-9]{7,8}")  # 7-8 chars, for example

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
                llm_stream = self.llm_provider.aget_completion_stream(msg_list, gen_cfg)
                async for chunk in llm_stream:
                    print('chunk = ', chunk)
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason

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
                                    "payload": self.search_results_collector.find_by_short_id(sid),
                                }
                                # Using SSEFormatter to yield a "citation" event
                                async for line in SSEFormatter.yield_citation_event(citation_evt_payload):
                                    yield line

                        # (b) Now emit the newly streamed text as a "message" event
                        async for line in SSEFormatter.yield_message_event(delta.content):
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
                                    pending_tool_calls[idx]["name"] = tc.function.name
                                if tc.function.arguments:
                                    pending_tool_calls[idx]["arguments"] += tc.function.arguments

                    # 5) If the stream signals we should handle "tool_calls"
                    if finish_reason == "tool_calls":
                        calls_list = []
                        for idx in sorted(pending_tool_calls.keys()):
                            cinfo = pending_tool_calls[idx]
                            calls_list.append(
                                {
                                    "tool_call_id": cinfo["id"] or f"call_{idx}",
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
                            tc_evt = ToolCallEvent(event="tool_call", data=tc_data)
                            # With SSEFormatter, you might do:
                            async for line in SSEFormatter.yield_tool_call_event(tc_evt.dict()["data"]):
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
                                    c["name"], c["arguments"], tool_id=c["tool_call_id"]
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
                                Message(role="assistant", content=partial_text_buffer)
                            )

                        # (a) Emit final answer SSE event
                        final_evt_payload = {
                            "id": "msg_final",
                            "object": "agent.final_answer",
                            "generated_answer": partial_text_buffer,
                            # Optionally attach citations, tool calls, etc.
                        }
                        async for line in SSEFormatter.yield_final_answer_event(final_evt_payload):
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

class R2RXMLToolsStreamingReasoningRAGAgent(
    RAGAgentMixin, R2RStreamingReasoningAgent
):
    """
    A streaming, iterative RAG Agent that looks for <Thought>, <Action>, <Response> blocks.

    At a high level:
      - We run up to `max_steps` iterations.
      - Each iteration calls the LLM in streaming mode.
      - For each partial chunk, we split out <Thought> vs. normal text =>
        SSE "thinking" or "message".
      - After streaming stops (finish_reason or tool_calls), we parse <Action> blocks:
        - If there's a <Response>, we finalize and emit final_answer + done.
        - Otherwise, if we see <ToolCall>, we run those tools and store the results,
          then proceed to the next iteration.
      - If we exhaust `max_steps` without a <Response>, we fallback to `COMPUTE_FAILURE`.
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
        max_steps: int = 10,
    ):
        # Ensure streaming is on
        config.stream = True

        # Initialize the parent streaming reasoning agent
        super().__init__(
            database_provider=database_provider,
            llm_provider=llm_provider,
            config=config,
            rag_generation_config=rag_generation_config,
            search_settings=search_settings,
            local_search_method=local_search_method,
            content_method=content_method,
            max_tool_context_length=max_tool_context_length,
        )
        self.max_steps = max_steps

    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        The main iterative loop. Each iteration:
          1) Stream partial LLM output => parse <Thought> => SSE "thinking",
             normal text => SSE "message".
          2) Collect all text in iteration_text + user_facing_buffer.
          3) Parse <Action> blocks for <ToolCall> or <Response>.
             - If <Response>, finalize => SSE "final_answer" + "done".
             - Else run <ToolCall>, store tool results, proceed.
          4) If no <Response> after max_steps => fallback.
        """
        # Reset internal state, run any setup
        self._reset()
        await self._setup(system_instruction)

        # Optionally add initial messages to conversation
        if messages:
            for m in messages:
                await self.conversation.add_message(m)

        # For bracket references
        relabeler = CitationRelabeler()
        announced_refs: Set[int] = set()

        for step_i in range(self.max_steps):
            iteration_text = ""
            user_facing_buffer = []

            # 1) Single LLM streaming pass
            msgs = await self.conversation.get_messages()
            print("msgs = ", msgs)
            gen_cfg = self.get_generation_config(msgs[-1], stream=True)
            llm_stream = self.llm_provider.aget_completion_stream(
                msgs, gen_cfg
            )

            async for chunk in llm_stream:
                finish_reason = chunk.choices[0].finish_reason
                delta = chunk.choices[0].delta

                # If we got new content
                if delta.content:
                    # Split out <Thought> from normal text
                    segments = self._split_thought_tags(delta.content)
                    for text_seg, is_thought in segments:
                        if is_thought:
                            # SSE "thinking"
                            thinking_data = {
                                "id": str(uuid.uuid4()),
                                "object": "agent.thinking.delta",
                                "delta": {
                                    "content": [
                                        {
                                            "type": "text",
                                            "payload": {
                                                "value": text_seg,
                                                "annotations": [],
                                            },
                                        }
                                    ]
                                },
                            }
                            async for line in yield_sse_event(
                                "thinking", thinking_data
                            ):
                                yield line

                            # Add to iteration_text with explicit <Thought> tags
                            iteration_text += f"<Thought>{text_seg}</Thought>"
                        else:
                            # SSE "message"
                            msg_data = {
                                "id": str(uuid.uuid4()),
                                "object": "agent.message.delta",
                                "delta": {
                                    "content": [
                                        {
                                            "type": "text",
                                            "payload": {
                                                "value": text_seg,
                                                "annotations": [],
                                            },
                                        }
                                    ]
                                },
                            }
                            async for line in yield_sse_event(
                                "message", msg_data
                            ):
                                yield line

                            user_facing_buffer.append(text_seg)
                            iteration_text += text_seg

                if finish_reason in ("stop", "tool_calls"):
                    # End the streaming loop for this iteration
                    break

            # 2) After streaming: parse <Action> blocks and <Response>
            actions = self._parse_action_blocks(iteration_text)
            if actions:
                for action_block in actions:
                    # If there's <Response>
                    if action_block["response"] is not None:
                        final_answer = (
                            "".join(user_facing_buffer)
                            + action_block["response"]
                        )
                        # Finalize => SSE "final_answer" + "done"
                        async for line in self._finalize_response(
                            final_answer, relabeler, announced_refs
                        ):
                            yield line
                        return

                    # If there's <ToolCall>
                    if action_block["tool_calls"]:
                        for tc in action_block["tool_calls"]:
                            # SSE "tool_call"
                            tool_call_id = f"xmltool_{uuid.uuid4()}"
                            tc_data = ToolCallData(
                                tool_call_id=tool_call_id,
                                name=tc["name"],
                                arguments=tc["params"],
                            )
                            evt = ToolCallEvent(
                                event="tool_call", data=tc_data
                            )
                            async for line in yield_sse_event(
                                "tool_call", evt.data.dict()
                            ):
                                yield line

                            # Actually execute the tool
                            result_obj = await self.execute_tool(
                                tc["name"], **tc["params"]
                            )

                            # SSE "tool_result"
                            tool_result_data = ToolResultData(
                                tool_call_id=tool_call_id,
                                role="tool",
                                content=json.dumps(
                                    convert_nonserializable_objects(
                                        result_obj.raw_result.as_dict()
                                    )
                                ),
                            )
                            tr_evt = ToolResultEvent(
                                event="tool_result", data=tool_result_data
                            )
                            async for line in yield_sse_event(
                                "tool_result", tr_evt.data.dict()
                            ):
                                yield line

                            # Add the toolcall + result to iteration_text
                            # (so the next iteration can see it, if the LLM references it)
                            iteration_text += (
                                "<Action><ToolCalls>"
                                f"<ToolCall><Name>{tc['name']}</Name>"
                                f"<Parameters>{json.dumps(tc['params'])}</Parameters>"
                                f"<Result>{result_obj}</Result></ToolCall>"
                                "</ToolCalls></Action>"
                            )
            else:
                # Possibly there's a <Response> outside <Action>
                resp_m = re.search(
                    r"<Response>(.*?)</Response>", iteration_text, re.DOTALL
                )
                if resp_m:
                    final_answer = "".join(user_facing_buffer) + resp_m.group(
                        1
                    )
                    async for line in self._finalize_response(
                        final_answer, relabeler, announced_refs
                    ):
                        yield line
                    return

            # 3) If there's no <Response>, store the user-facing text in conversation
            if user_facing_buffer:
                combined_text = "".join(user_facing_buffer).strip()
                if combined_text:
                    # Re-write bracket references and emit any citation SSE
                    rewritten_text, citation_sse = (
                        await self._rewrite_and_emit_citations(
                            combined_text, relabeler, announced_refs
                        )
                    )
                    # yield the SSE lines
                    for line in citation_sse:
                        yield line

                    # Add as an assistant message
                    await self.conversation.add_message(
                        Message(role="assistant", content=rewritten_text)
                    )

        # If we used all max_steps with no <Response>, fallback:
        async for line in self._finalize_response(
            COMPUTE_FAILURE, relabeler, announced_refs
        ):
            yield line

    async def _rewrite_and_emit_citations(
        self,
        text: str,
        # relabeler: CitationRelabeler,
        announced_refs: set[int],
    ) -> Tuple[str, list[str]]:
        """
        Detect bracket references [1], [2] in 'text', produce SSE lines for each new citation,
        then return (rewritten_text, sse_lines).
        """
        sse_lines = []
        # bracket_pattern = re.compile(r"\[\s*(\d+)\s*\]")
        bracket_pattern = re.compile(r"\[\s*(\d+)\s*\](?!\d)")

        for match in bracket_pattern.finditer(text):
            old_ref = int(match.group(1))
            new_ref = relabeler.get_or_assign_newref(old_ref)
            if old_ref not in announced_refs:
                announced_refs.add(old_ref)
                all_results = self.search_results_collector.get_all_results()
                if 1 <= old_ref <= len(all_results):
                    (src_type, result_obj, agg_index) = all_results[
                        old_ref - 1
                    ]
                    citation_evt_payload = CitationData(
                        id=f"cit_{old_ref}",
                        object="agent.citation",
                        raw_index=old_ref,
                        new_index=new_ref,
                        agg_index=agg_index,
                        source_type=src_type,
                        source_title=getattr(result_obj, "title", None),
                    )
                    # Collect SSE lines
                    async for line in yield_sse_event(
                        "citation", citation_evt_payload.dict()
                    ):
                        sse_lines.append(line)

        rewritten = relabeler.rewrite_with_newrefs(text)
        return rewritten, sse_lines

    async def _finalize_response(
        self,
        final_text: str,
        # relabeler: CitationRelabeler,
        announced_refs: set[int],
    ) -> AsyncGenerator[str, None]:
        """
        Called when we see a <Response> or when we hit max_steps with no response.
        1) Re-write bracket references => yield any 'citation' SSE lines.
        2) Add final text as assistant message.
        3) SSE 'final_answer'
        4) SSE 'done'
        """
        rewritten_text, citation_sse = await self._rewrite_and_emit_citations(
            final_text, relabeler, announced_refs
        )
        # yield the citation SSE lines
        for line in citation_sse:
            yield line

        # Now store the final text in conversation
        await self.conversation.add_message(
            Message(role="assistant", content=rewritten_text)
        )

        # Build final_answer SSE
        raw_citations = extract_citations(rewritten_text)
        mapped_citations = map_citations_to_collector(
            raw_citations, self.search_results_collector
        )
        final_evt_payload = FinalAnswerData(
            generated_answer=relabeler.finalize_all_citations(rewritten_text),
            citations=[c.model_dump() for c in mapped_citations],
        )
        async for line in yield_sse_event(
            "final_answer", final_evt_payload.dict()
        ):
            yield line

        # SSE "done"
        yield "event: done\n"
        yield "data: [DONE]\n\n"
        self._completed = True

    def _split_thought_tags(self, text: str) -> list[tuple[str, bool]]:
        """
        Splits out <Thought>...</Thought> from normal text.
        Returns a list of (segment, is_thought) pairs.
        Also handle <think> as <Thought> if needed.
        """
        text = text.replace("<think>", "<Thought>").replace(
            "</think>", "</Thought>"
        )
        pattern = re.compile(r"(<Thought>.*?</Thought>)", re.DOTALL)
        parts = pattern.split(text)

        result = []
        for p in parts:
            if not p:
                continue
            if p.startswith("<Thought>") and p.endswith("</Thought>"):
                content = p[len("<Thought>") : -len("</Thought>")]
                result.append((content, True))
            else:
                result.append((p, False))
        return result

    def _parse_action_blocks(self, text: str) -> list[dict]:
        """
        Parse <Action> blocks from the iteration text, extracting <ToolCall> and <Response>.
        Returns a list of dicts with shape: {"tool_calls": [...], "response": <str or None>}
        """
        action_pattern = re.compile(
            r"<Action>(.*?)</Action>", re.DOTALL | re.IGNORECASE
        )
        toolcall_pattern = re.compile(
            r"<ToolCall>(.*?)</ToolCall>", re.DOTALL | re.IGNORECASE
        )
        name_pattern = re.compile(
            r"<Name>(.*?)</Name>", re.DOTALL | re.IGNORECASE
        )
        params_pattern = re.compile(
            r"<Parameters>(.*?)</Parameters>", re.DOTALL | re.IGNORECASE
        )
        response_pattern = re.compile(
            r"<Response>(.*?)</Response>", re.DOTALL | re.IGNORECASE
        )

        actions = []
        for ablock in action_pattern.findall(text):
            block_data = {"tool_calls": [], "response": None}

            # <ToolCall>
            for tcall in toolcall_pattern.findall(ablock):
                name_m = name_pattern.search(tcall)
                params_m = params_pattern.search(tcall)
                tool_name = (
                    name_m.group(1).strip() if name_m else "unknown_tool"
                )

                if params_m:
                    raw_params = params_m.group(1).strip()
                    try:
                        tool_params = json.loads(raw_params)
                    except json.JSONDecodeError:
                        tool_params = {"raw_params": raw_params}
                else:
                    tool_params = {}

                block_data["tool_calls"].append(
                    {"name": tool_name, "params": tool_params}
                )

            # <Response>
            resp_match = response_pattern.search(ablock)
            if resp_match:
                block_data["response"] = resp_match.group(1).strip()

            actions.append(block_data)

        return actions


