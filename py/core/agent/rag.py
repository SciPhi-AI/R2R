import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from typing import Any, AsyncGenerator, Callable, Optional, Tuple

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
    Message,
    SearchSettings,
    WebSearchResponse,
)
from core.base.agent import AgentConfig, Tool
from core.base.providers import DatabaseProvider
from core.providers import LiteLLMCompletionProvider, OpenAICompletionProvider

logger = logging.getLogger(__name__)


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
            context_document_results.append(
                ContextDocumentResult(
                    document=item["document"],
                    chunks=[
                        chunk.get("text", "")
                        for chunk in item.get("chunks", [])
                    ],
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


import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from typing import Any, AsyncGenerator, Callable, Optional

from core.agent import R2RStreamingAgent
from core.base.abstractions import (
    AggregateSearchResult,
    ContextDocumentResult,
    GenerationConfig,
    Message,
    SearchSettings,
)
from core.base.agent import AgentConfig, Tool
from core.base.providers import DatabaseProvider

logger = logging.getLogger(__name__)


class R2RXMLToolsStreamingRAGAgent(R2RStreamingRAGAgent):
    """
    Abstract base class for a streaming-capable RAG Agent that:
      - Streams chain-of-thought tokens vs. normal text
      - Accumulates final text for parsing <Action><ToolCalls>
      - Executes any requested tool calls (max_steps enforced)
      - Produces a final <Response> or failure if max steps are exceeded

    You must override:
      - _generate_thinking_response(user_prompt: str)
      - _generate_final_response(context: str, user_prompt: str)
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
        max_tool_context_length: int = 10_000,
        max_steps: int = 5,  # limit on number of tool calls
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

        # Build initial conversation context from all messages
        all_msgs = await self.conversation.get_messages()
        conversation_context = self._build_single_user_prompt(all_msgs)

        for step_i in range(self.max_steps):
            # We'll collect final text tokens to parse for <Action>/<Response>.
            assistant_text_buffer = []
            # Track whether we are “inside” a <Thought> block while streaming:
            inside_thought_block = False

            # Step 2) Single LLM call => yields (is_thought, text) pairs
            async for (is_thought, token_text) in self._generate_thinking_response(
                conversation_context, **kwargs
            ):
                if is_thought:
                    # Stream chain-of-thought text *inline*, but bracket with <Thought>...</Thought>
                    if not inside_thought_block:
                        inside_thought_block = True
                        yield "<Thought>"
                    yield token_text
                else:
                    # If we were inside a thought block, close it
                    if inside_thought_block:
                        yield "</Thought>"
                        inside_thought_block = False

                    # “Assistant text” is user-facing text that we
                    # will parse for <Action> or <Response>
                    assistant_text_buffer.append(token_text)

            # If the model ended while still in a thought block, close it
            if inside_thought_block:
                yield "</Thought>"

            # Step 3) Combine the final user-facing tokens
            iteration_text = "".join(assistant_text_buffer).strip()

            #
            # 3a) Parse out <Action> blocks
            #
            parsed_actions = self._parse_action_blocks(iteration_text)

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
                        result = await self.execute_tool(name, **params)
                        toolcall_with_result += f"<Result>{result}</Result></ToolCall>"

                        toolcalls_xml += toolcall_with_result

                    toolcalls_xml += "</ToolCalls>"
                    toolcalls_minus_results += "</ToolCalls>"

                    # Yield the no-results block so user sees the calls
                    yield toolcalls_minus_results

                    # If this <Action> has a <Response>, yield once and stop
                    if action_block["response"] is not None:
                        resp_str = action_block["response"]
                        yield f"<Response>{resp_str}</Response>"
                        return

                    # Otherwise, embed the <ToolCalls> with <Result> in conversation context
                    conversation_context += f"<Action>{toolcalls_xml}</Action>"

            else:
                #
                # 3b) If no <Action> blocks at all, check for a bare <Response>
                #
                response_text = self._extract_response_text(iteration_text)
                if response_text is not None:
                    # Found a top-level <Response>, yield it once and stop
                    yield f"<Response>{response_text}</Response>"
                    return

            #
            # 3c) If we did not return, it means no <Response> was found in this iteration.
            #     So append the entire iteration text to conversation_context and proceed.
            #
            conversation_context += "\n" + iteration_text

        # If we finish all steps with no <Response>, yield fallback:
        yield "<Response>I failed to reach a conclusion with my allowed compute.</Response>"


    # async def arun(
    #     self,
    #     system_instruction: Optional[str] = None,
    #     messages: Optional[list[Message]] = None,
    #     *args,
    #     **kwargs,
    # ) -> AsyncGenerator[str, None]:
    #     """
    #     Iterative approach with chain-of-thought wrapped in <Thought>...</Thought> each iteration.
    #     1) In each iteration (up to max_steps):
    #         a) Call _generate_thinking_response(conversation_context).
    #         b) Stream chain-of-thought tokens *inline* but enclosed by <Thought>...</Thought>.
    #         c) Collect "assistant" tokens (is_thought=False) in a buffer to parse after.
    #         d) Parse <Action> blocks; if any <Action> has <Response>, yield it & stop.
    #         e) Else, if there's a bare <Response> outside <Action>, yield & stop.
    #         f) If still no <Response>, append iteration text to context, move to next iteration.
    #     2) If we exhaust steps, yield fallback <Response>.
    #     """

    #     # Step 1) Setup conversation
    #     await self._setup(system_instruction=system_instruction)
    #     if messages:
    #         for msg in messages:
    #             await self.conversation.add_message(msg)

    #     # Build initial conversation context from all messages
    #     all_msgs = await self.conversation.get_messages()
    #     conversation_context = self._build_single_user_prompt(all_msgs)

    #     for step_i in range(self.max_steps):
    #         # We'll collect final text tokens to parse for <Action>/<Response>.
    #         assistant_text_buffer = []
    #         # Track whether we are “inside” a <Thought> block while streaming:
    #         inside_thought_block = False

    #         # Step 2) Single LLM call => yields (is_thought, text) pairs
    #         async for (
    #             is_thought,
    #             token_text,
    #         ) in self._generate_thinking_response(
    #             conversation_context, **kwargs
    #         ):
    #             if is_thought:
    #                 # Stream chain-of-thought text *inline*, but bracket with <Thought>...</Thought>
    #                 if not inside_thought_block:
    #                     inside_thought_block = True
    #                     yield "<Thought>"
    #                 yield token_text
    #             else:
    #                 # If we were inside a thought block, close it
    #                 if inside_thought_block:
    #                     yield "</Thought>"
    #                     inside_thought_block = False

    #                 # “Assistant text” is user-facing text that we
    #                 # will parse for <Action> or <Response>
    #                 assistant_text_buffer.append(token_text)

    #         # If the model ended while still in a thought block, close it
    #         if inside_thought_block:
    #             yield "</Thought>"

    #         # Step 3) Combine the final user-facing tokens
    #         iteration_text = "".join(assistant_text_buffer).strip()

    #         #
    #         # 3a) Parse out <Action> blocks
    #         #
    #         parsed_actions = self._parse_action_blocks(iteration_text)

    #         any_response_found = False

    #         if parsed_actions:
    #             # For each action block, see if it has <ToolCalls>, <Response>
    #             for action_block in parsed_actions:
    #                 toolcalls_xml = "<ToolCalls>"
    #                 toolcalls_minus_results = "<ToolCalls>"

    #                 # Execute any tool calls
    #                 for tc in action_block["tool_calls"]:
    #                     name = tc["name"]
    #                     params = tc["params"]
    #                     logger.info(f"Executing tool '{name}' with {params}")

    #                     toolcalls_xml += "<ToolCall>"
    #                     toolcalls_xml += f"<Name>{name}</Name>"
    #                     toolcalls_xml += (
    #                         f"<Parameters>{json.dumps(params)}</Parameters>"
    #                     )

    #                     result = await self.execute_tool(name, **params)
    #                     toolcalls_minus_results += (
    #                         toolcalls_xml + "</ToolCall>"
    #                     )
    #                     toolcalls_xml += f"<Result>{result}</Result>"
    #                     toolcalls_xml += "</ToolCall>"

    #                 toolcalls_xml += "</ToolCalls>"
    #                 toolcalls_minus_results += "</ToolCalls>"
    #                 yield toolcalls_minus_results

    #                 # If this <Action> has a <Response>, yield once and stop
    #                 if action_block["response"] is not None:
    #                     resp_str = action_block["response"]
    #                     yield f"<Response>{resp_str}</Response>"
    #                     return

    #                 # Otherwise, embed the <ToolCalls> in conversation context
    #                 # so it sees the results next iteration
    #                 conversation_context += f"<Action>{toolcalls_xml}</Action>"

    #         else:
    #             #
    #             # 3b) If no <Action> blocks at all, check for a bare <Response>
    #             #
    #             response_text = self._extract_response_text(iteration_text)
    #             if response_text is not None:
    #                 # Found a top-level <Response>, yield it once and stop
    #                 yield f"<Response>{response_text}</Response>"
    #                 return

    #         #
    #         # 3c) If we did not return, it means no <Response> was found in this iteration.
    #         #     So append the entire iteration text to conversation_context and proceed.
    #         #
    #         conversation_context += "\n" + iteration_text

    #     # If we finish all steps with no <Response>, yield fallback:
    #     yield "<Response>I failed to reach a conclusion with my allowed compute.</Response>"

    def _parse_action_blocks(self, text: str) -> list[dict]:
        """
        Attempt to find zero or more <Action> blocks in text.
        For each block, parse any <ToolCalls> and <Response>.
        Return a list of dicts: [ { "tool_calls": [...], "response": <str or None> }, ... ]

        Each 'tool_calls' entry is a list of { "name": <tool_name>, "params": <dict> }.
        'response' is either a string if <Response> block is found, or None if absent.
        """
        # A naive approach is to split on <Action>...</Action> if multiple appear.
        # We'll do that with a simple loop using xml.etree, ignoring text outside <Action>.
        # Adjust to your actual patterns if your LLM can produce multiple <Action> blocks in one pass.
        results = []

        try:
            # We attempt to parse the entire text and look for top-level <Action> blocks
            # or repeated <Action> blocks. Because xml.etree won't parse multiple top-level
            # elements easily, we can wrap them in a dummy root if we want to handle multiples.
            # For simplicity, let's do a quick iteration:
            import re

            pattern = re.compile(
                r"(<Action>.*?</Action>)", re.DOTALL | re.IGNORECASE
            )
            matches = pattern.findall(text)
            for match in matches:
                # parse each <Action>...</Action> snippet individually
                # to handle multiple blocks in a single step
                block_data = {
                    "tool_calls": [],
                    "response": None,
                }
                try:
                    root = ET.fromstring(match)
                    # parse <ToolCalls>
                    tc_element = root.find("ToolCalls")
                    if tc_element is not None:
                        for tc_el in tc_element.findall("ToolCall"):
                            name_el = tc_el.find("Name")
                            params_el = tc_el.find("Parameters")
                            if name_el is not None and params_el is not None:
                                tool_name = name_el.text.strip()
                                try:
                                    tool_params = json.loads(
                                        params_el.text.strip()
                                    )
                                except:
                                    tool_params = {}
                                block_data["tool_calls"].append(
                                    {"name": tool_name, "params": tool_params}
                                )
                    # parse <Response>
                    resp_el = root.find("Response")
                    if resp_el is not None and resp_el.text is not None:
                        block_data["response"] = resp_el.text.strip()

                except ET.ParseError:
                    pass  # skip invalid block
                results.append(block_data)

        except Exception as e:
            logger.warning(f"Action block parsing error: {e}")

        return results

    def _extract_response_text(self, text: str) -> Optional[str]:
        """
        If the raw text contains a bare <Response>...</Response> block (outside <Action>),
        we can parse it here. Return the string or None if not present.
        """
        import re

        match = re.search(
            r"<Response>(.*?)</Response>", text, re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        return None

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

    def _parse_action_xml(self, text: str) -> list[dict]:
        """
        Attempt to parse <Action><ToolCalls><ToolCall> from XML in text.
        Return a list of { "name": <tool_name>, "params": <dict> }.
        """
        tool_calls = []
        if not text.strip():
            return tool_calls

        try:
            # For safety, parse only the portion in ```xml``` if present
            if "```xml" in text and "```" in text.split("```xml")[-1]:
                extracted = text.split("```xml")[-1].split("```")[0]
            else:
                extracted = text

            root = ET.fromstring(extracted)
            if root.tag.lower() == "action":
                tool_calls_el = root.find("ToolCalls")
                if tool_calls_el is not None:
                    for tc_el in tool_calls_el.findall("ToolCall"):
                        name_el = tc_el.find("Name")
                        params_el = tc_el.find("Parameters")

                        if name_el is not None and params_el is not None:
                            t_name = name_el.text.strip()

                            # parse JSON in <Parameters>
                            try:
                                params_text = params_el.text.strip()
                                t_params = json.loads(params_text)
                                tool_calls.append(
                                    {"name": t_name, "params": t_params}
                                )
                            except json.JSONDecodeError:
                                logger.warning(
                                    f"Invalid JSON in <Parameters> for tool {t_name}"
                                )
        except ET.ParseError:
            logger.warning("Failed to parse <Action> XML block.")
        return tool_calls

    # ------------------------------------------------------------------------
    # ABSTRACT METHODS – must be implemented by a subclass
    # ------------------------------------------------------------------------
    async def _generate_thinking_response(
        self, user_prompt: str, **kwargs
    ) -> AsyncGenerator[tuple[bool, str], None]:
        """
        Should yield (is_thought, text) pairs from the LLM's first pass.
          - is_thought=True => chain-of-thought tokens
          - is_thought=False => final user-facing text (accumulated, then parsed)
        """
        raise NotImplementedError(
            "Subclasses must implement _generate_thinking_response."
        )

    async def _generate_final_response(
        self, context: str, user_prompt: str, **kwargs
    ) -> AsyncGenerator[tuple[bool, str], None]:
        """
        Given the context (including <ToolCalls> results) and original user_prompt,
        produce the final user-facing text. Should yield (is_thought, text).
        """
        raise NotImplementedError(
            "Subclasses must implement _generate_final_response."
        )


class GeminiXMLToolsStreamingRAGAgent(R2RXMLToolsStreamingRAGAgent):
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

    async def _generate_thinking_response(
        self, user_prompt: str, **kwargs
    ) -> AsyncGenerator[tuple[bool, str], None]:
        """
        1) Call Gemini with `include_thoughts=True`.
        2) For each part in `candidates[0].content.parts`, yield (True, text) if part.thought else (False, text).
        """
        config = {"thinking_config": {"include_thoughts": True}}

        # Gemini is a blocking call so you'll want to put it in a thread pool or adapt to async if possible.
        # We'll do a naive synchronous call in this example:
        response = self.gemini_client.models.generate_content(
            model=self.gemini_model_name,
            contents=user_prompt,
            config=config,
        )

        # No candidates => yield some minimal fallback
        if not response.candidates:
            yield (False, "I failed to retrieve a valid Gemini response.")
            return

        for part in response.candidates[0].content.parts:
            if part.thought:
                # chain-of-thought
                yield (True, part.text)
            else:
                yield (False, part.text)

    async def _generate_final_response(
        self, context: str, user_prompt: str, **kwargs
    ) -> AsyncGenerator[tuple[bool, str], None]:
        """
        A second LLM call with the current conversation + <Action> context,
        to produce the final user-facing answer.
        Yields chain-of-thought tokens as (True, text), and final user text as (False, text).
        """
        config = {"thinking_config": {"include_thoughts": True}}

        # Build final prompt
        final_prompt = (
            user_prompt
            + "\n\nAgent Reply:\n\n"
            + context
            + "\n\nNow, given the above, generate a coherent reply for the user."
        )

        response = self.gemini_client.models.generate_content(
            model=self.gemini_model_name,
            contents=final_prompt,
            config=config,
        )

        if not response.candidates:
            yield (
                False,
                "I failed to retrieve a final conclusion from Gemini.",
            )
            return

        final_parts = response.candidates[0].content.parts
        for part in final_parts:
            # If it's chain-of-thought => (True, text), else => (False, text)
            yield (part.thought, part.text)