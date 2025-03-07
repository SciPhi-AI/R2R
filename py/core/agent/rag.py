import asyncio
import json
import logging
import re
import uuid
from typing import Any, AsyncGenerator, Callable, Optional, Set, Tuple, Union

from core.agent import R2RAgent
from core.base import (
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
                "Search over the stored documents by title, metadata, or other document-level fields. "
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
                        "description": "Query string to match file/doc-level info. E.g., 'list documents about XYZ'.",
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


class R2RXMLToolsStreamingRAGAgent(R2RStreamingRAGAgent):
    """
    Abstract base class for a streaming-capable RAG Agent that:
      - Streams chain-of-thought tokens vs. normal text
      - Accumulates final text for parsing <Action><ToolCalls>
      - Executes any requested tool calls (max_steps enforced)
      - Produces a final <Response> or failure if max steps are exceeded

    You must override:
      - _generate_thinking_response(user_prompt: str)
    """

    async def arun(
        self,
        system_instruction: Optional[str] = None,
        messages: Optional[list[Message]] = None,
        *args,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Iterative approach with chain-of-thought wrapped in
        <Thought>...</Thought> each iteration.

        1) In each iteration (up to max_steps):
            a) Call _generate_thinking_response(conversation_context).
            b) Stream chain-of-thought tokens *inline* but enclosed by <Thought>...</Thought>.
            c) Collect "assistant" tokens (is_thought=False) in a buffer to parse after.
            d) Parse <Action> blocks; if any <Action> has <Response>, yield it & stop.
            e) Else, if there's a bare <Response> outside <Action>, yield & stop.
            f) If still no <Response>, append iteration text to context, move to next iteration.
        2) If we exhaust steps, yield fallback <Response>.
        """
        self.max_steps = 5
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

            llm_stream = self.llm_provider.aget_completion_stream(
                messages_list,
                generation_config,
            )
            thought_text, action_text, in_thought = "", "", True

            closing_detected = False
            async for chunk in llm_stream:
                # print(f"CHUNK: {chunk}")
                stream_delta = chunk.choices[0].delta.content
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
                yield (
                    "<Response>"
                    + action_text.split("<Response>")[-1].split("</Response>")[
                        0
                    ]
                    + "</Response>"
                )
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
                for call, result in zip(
                    parsed_tool_calls, results, strict=False
                ):
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
                iteration_text += "<Thought>No tool calls found in this step, trying again. If I have completed my response I should use the `result` tool.</Thought>"
                yield "<Thought>No tool calls found in this step, trying again. If I have completed my response I should use the `result` tool.</Thought>"

            await self.conversation.add_message(
                Message(role="assistant", content=iteration_text)
            )

            if step_i == self.max_steps - 1:
                yield COMPUTE_FAILURE
                return

    def _build_single_user_prompt(self, conversation_msgs: list[dict]) -> str:
        """Converts system+user+assistant messages into a single text prompt.

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
        """Parse tool calls from XML-like text.

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
