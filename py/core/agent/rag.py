import asyncio
import json
import logging
import random
import re
import xml.etree.ElementTree as ET
from typing import Any, AsyncGenerator, Callable, Optional

import tiktoken
from google.genai.errors import ServerError

from core.agent import R2RAgent, R2RStreamingAgent, R2RStreamingReasoningAgent
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
from core.providers import (
    AnthropicCompletionProvider,
    LiteLLMCompletionProvider,
    OpenAICompletionProvider,
    R2RCompletionProvider,
)

logger = logging.getLogger(__name__)

COMPUTE_FAILURE = "<Response>I failed to reach a conclusion with my allowed compute.</Response>"


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
        context_tokens = num_tokens(context) + 1
        frac_to_return = self.max_tool_context_length / (
            num_tokens(context) + 1
        )

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
