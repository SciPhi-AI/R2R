import asyncio
import json
import logging
import re
from abc import ABCMeta
from typing import AsyncGenerator, Optional, Tuple

from core.base import AsyncSyncMeta, LLMChatCompletion, Message, syncable
from core.base.agent import Agent, Conversation
from core.utils import (
    CitationTracker,
    SearchResultsCollector,
    SSEFormatter,
    convert_nonserializable_objects,
    dump_obj,
    find_new_citation_spans,
)

logger = logging.getLogger()


class CombinedMeta(AsyncSyncMeta, ABCMeta):
    pass


def sync_wrapper(async_gen):
    loop = asyncio.get_event_loop()

    def wrapper():
        try:
            while True:
                try:
                    yield loop.run_until_complete(async_gen.__anext__())
                except StopAsyncIteration:
                    break
        finally:
            loop.run_until_complete(async_gen.aclose())

    return wrapper()


class R2RAgent(Agent, metaclass=CombinedMeta):
    def __init__(self, *args, **kwargs):
        self.search_results_collector = SearchResultsCollector()
        super().__init__(*args, **kwargs)
        self._reset()

    async def _generate_llm_summary(self, iterations_count: int) -> str:
        """
        Generate a summary of the conversation using the LLM when max iterations are exceeded.

        Args:
            iterations_count: The number of iterations that were completed

        Returns:
            A string containing the LLM-generated summary
        """
        try:
            # Get all messages in the conversation
            all_messages = await self.conversation.get_messages()

            # Create a prompt for the LLM to summarize
            summary_prompt = {
                "role": "user",
                "content": (
                    f"The conversation has reached the maximum limit of {iterations_count} iterations "
                    f"without completing the task. Please provide a concise summary of: "
                    f"1) The key information you've gathered that's relevant to the original query, "
                    f"2) What you've attempted so far and why it's incomplete, and "
                    f"3) A specific recommendation for how to proceed. "
                    f"Keep your summary brief (3-4 sentences total) and focused on the most valuable insights. If it is possible to answer the original user query, then do so now instead."
                    f"Start with '⚠️ **Maximum iterations exceeded**'"
                ),
            }

            # Create a new message list with just the conversation history and summary request
            summary_messages = all_messages + [summary_prompt]

            # Get a completion for the summary
            generation_config = self.get_generation_config(summary_prompt)
            response = await self.llm_provider.aget_completion(
                summary_messages,
                generation_config,
            )

            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating LLM summary: {str(e)}")
            # Fall back to basic summary if LLM generation fails
            return (
                "⚠️ **Maximum iterations exceeded**\n\n"
                "The agent reached the maximum iteration limit without completing the task. "
                "Consider breaking your request into smaller steps or refining your query."
            )

    def _reset(self):
        self._completed = False
        self.conversation = Conversation()

    @syncable
    async def arun(
        self,
        messages: list[Message],
        system_instruction: Optional[str] = None,
        *args,
        **kwargs,
    ) -> list[dict]:
        self._reset()
        await self._setup(system_instruction)

        if messages:
            for message in messages:
                await self.conversation.add_message(message)
        iterations_count = 0
        while (
            not self._completed
            and iterations_count < self.config.max_iterations
        ):
            iterations_count += 1
            messages_list = await self.conversation.get_messages()
            generation_config = self.get_generation_config(messages_list[-1])
            response = await self.llm_provider.aget_completion(
                messages_list,
                generation_config,
            )
            logger.debug(f"R2RAgent response: {response}")
            await self.process_llm_response(response, *args, **kwargs)

        if not self._completed:
            # Generate a summary of the conversation using the LLM
            summary = await self._generate_llm_summary(iterations_count)
            await self.conversation.add_message(
                Message(role="assistant", content=summary)
            )

        # Return final content
        all_messages: list[dict] = await self.conversation.get_messages()
        all_messages.reverse()

        output_messages = []
        for message_2 in all_messages:
            if (
                # message_2.get("content")
                message_2.get("content") != messages[-1].content
            ):
                output_messages.append(message_2)
            else:
                break
        output_messages.reverse()

        return output_messages

    async def process_llm_response(
        self, response: LLMChatCompletion, *args, **kwargs
    ) -> None:
        if not self._completed:
            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            if finish_reason == "stop":
                self._completed = True

            # Determine which provider we're using
            using_anthropic = (
                "anthropic" in self.rag_generation_config.model.lower()
            )

            # OPENAI HANDLING
            if not using_anthropic:
                if message.tool_calls:
                    assistant_msg = Message(
                        role="assistant",
                        content="",
                        tool_calls=[msg.dict() for msg in message.tool_calls],
                    )
                    await self.conversation.add_message(assistant_msg)

                    # If there are multiple tool_calls, call them sequentially here
                    for tool_call in message.tool_calls:
                        await self.handle_function_or_tool_call(
                            tool_call.function.name,
                            tool_call.function.arguments,
                            tool_id=tool_call.id,
                            *args,
                            **kwargs,
                        )
                else:
                    await self.conversation.add_message(
                        Message(role="assistant", content=message.content)
                    )
                    self._completed = True

            else:
                # First handle thinking blocks if present
                if (
                    hasattr(message, "structured_content")
                    and message.structured_content
                ):
                    # Check if structured_content contains any tool_use blocks
                    has_tool_use = any(
                        block.get("type") == "tool_use"
                        for block in message.structured_content
                    )

                    if not has_tool_use and message.tool_calls:
                        # If it has thinking but no tool_use, add a separate message with structured_content
                        assistant_msg = Message(
                            role="assistant",
                            structured_content=message.structured_content,  # Use structured_content field
                        )
                        await self.conversation.add_message(assistant_msg)

                        # Add explicit tool_use blocks in a separate message
                        tool_uses = []
                        for tool_call in message.tool_calls:
                            # Safely parse arguments if they're a string
                            try:
                                if isinstance(
                                    tool_call.function.arguments, str
                                ):
                                    input_args = json.loads(
                                        tool_call.function.arguments
                                    )
                                else:
                                    input_args = tool_call.function.arguments
                            except json.JSONDecodeError:
                                logger.error(
                                    f"Failed to parse tool arguments: {tool_call.function.arguments}"
                                )
                                input_args = {
                                    "_raw": tool_call.function.arguments
                                }

                            tool_uses.append(
                                {
                                    "type": "tool_use",
                                    "id": tool_call.id,
                                    "name": tool_call.function.name,
                                    "input": input_args,
                                }
                            )

                        # Add tool_use blocks as a separate assistant message with structured content
                        if tool_uses:
                            await self.conversation.add_message(
                                Message(
                                    role="assistant",
                                    structured_content=tool_uses,
                                    content="",
                                )
                            )
                    else:
                        # If it already has tool_use or no tool_calls, preserve original structure
                        assistant_msg = Message(
                            role="assistant",
                            structured_content=message.structured_content,
                        )
                        await self.conversation.add_message(assistant_msg)

                elif message.content:
                    # For regular text content
                    await self.conversation.add_message(
                        Message(role="assistant", content=message.content)
                    )

                    # If there are tool calls, add them as structured content
                    if message.tool_calls:
                        tool_uses = []
                        for tool_call in message.tool_calls:
                            # Same safe parsing as above
                            try:
                                if isinstance(
                                    tool_call.function.arguments, str
                                ):
                                    input_args = json.loads(
                                        tool_call.function.arguments
                                    )
                                else:
                                    input_args = tool_call.function.arguments
                            except json.JSONDecodeError:
                                logger.error(
                                    f"Failed to parse tool arguments: {tool_call.function.arguments}"
                                )
                                input_args = {
                                    "_raw": tool_call.function.arguments
                                }

                            tool_uses.append(
                                {
                                    "type": "tool_use",
                                    "id": tool_call.id,
                                    "name": tool_call.function.name,
                                    "input": input_args,
                                }
                            )

                        await self.conversation.add_message(
                            Message(
                                role="assistant", structured_content=tool_uses
                            )
                        )

                # NEW CASE: Handle tool_calls with no content or structured_content
                elif message.tool_calls:
                    # Create tool_uses for the message with only tool_calls
                    tool_uses = []
                    for tool_call in message.tool_calls:
                        try:
                            if isinstance(tool_call.function.arguments, str):
                                input_args = json.loads(
                                    tool_call.function.arguments
                                )
                            else:
                                input_args = tool_call.function.arguments
                        except json.JSONDecodeError:
                            logger.error(
                                f"Failed to parse tool arguments: {tool_call.function.arguments}"
                            )
                            input_args = {"_raw": tool_call.function.arguments}

                        tool_uses.append(
                            {
                                "type": "tool_use",
                                "id": tool_call.id,
                                "name": tool_call.function.name,
                                "input": input_args,
                            }
                        )

                    # Add tool_use blocks as a message before processing tools
                    if tool_uses:
                        await self.conversation.add_message(
                            Message(
                                role="assistant",
                                structured_content=tool_uses,
                            )
                        )

                # Process the tool calls
                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        await self.handle_function_or_tool_call(
                            tool_call.function.name,
                            tool_call.function.arguments,
                            tool_id=tool_call.id,
                            *args,
                            **kwargs,
                        )


class R2RStreamingAgent(R2RAgent):
    """
    Base class for all streaming agents with core streaming functionality.
    Supports emitting messages, tool calls, and results as SSE events.
    """

    # These two regexes will detect bracket references and then find short IDs.
    BRACKET_PATTERN = re.compile(r"\[([^\]]+)\]")
    SHORT_ID_PATTERN = re.compile(
        r"[A-Za-z0-9]{7,8}"
    )  # 7-8 chars, for example

    def __init__(self, *args, **kwargs):
        # Force streaming on
        if hasattr(kwargs.get("config", {}), "stream"):
            kwargs["config"].stream = True
        super().__init__(*args, **kwargs)

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

        # Initialize citation tracker for this run
        citation_tracker = CitationTracker()

        # Dictionary to store citation payloads by ID
        citation_payloads = {}

        # Track all citations emitted during streaming for final persistence
        self.streaming_citations: list[dict] = []

        async def sse_generator() -> AsyncGenerator[str, None]:
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
                    thinking_signatures = {}  # Map thinking content to signatures

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

                            # (a) Now emit the newly streamed text as a "message" event
                            async for line in SSEFormatter.yield_message_event(
                                delta.content
                            ):
                                yield line

                            # (b) Find new citation spans in the accumulated text
                            new_citation_spans = find_new_citation_spans(
                                partial_text_buffer, citation_tracker
                            )

                            # Process each new citation span
                            for cid, spans in new_citation_spans.items():
                                for span in spans:
                                    # Check if this is the first time we've seen this citation ID
                                    is_new_citation = (
                                        citation_tracker.is_new_citation(cid)
                                    )

                                    # Get payload if it's a new citation
                                    payload = None
                                    if is_new_citation:
                                        source_obj = self.search_results_collector.find_by_short_id(
                                            cid
                                        )
                                        if source_obj:
                                            # Store payload for reuse
                                            payload = dump_obj(source_obj)
                                            citation_payloads[cid] = payload

                                    # Create citation event payload
                                    citation_data = {
                                        "id": cid,
                                        "object": "citation",
                                        "is_new": is_new_citation,
                                        "span": {
                                            "start": span[0],
                                            "end": span[1],
                                        },
                                    }

                                    # Only include full payload for new citations
                                    if is_new_citation and payload:
                                        citation_data["payload"] = payload

                                    # Add to streaming citations for final answer
                                    self.streaming_citations.append(
                                        citation_data
                                    )

                                    # Emit the citation event
                                    async for (
                                        line
                                    ) in SSEFormatter.yield_citation_event(
                                        citation_data
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
                                        pending_tool_calls[idx]["name"] = (
                                            tc.function.name
                                        )
                                    if tc.function.arguments:
                                        pending_tool_calls[idx][
                                            "arguments"
                                        ] += tc.function.arguments

                        # 5) If the stream signals we should handle "tool_calls"
                        if finish_reason == "tool_calls":
                            # Handle thinking if present
                            await self._handle_thinking(
                                thinking_signatures, accumulated_thinking
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
                                tc_data = self._create_tool_call_data(c)
                                async for (
                                    line
                                ) in SSEFormatter.yield_tool_call_event(
                                    tc_data
                                ):
                                    yield line

                            # (b) Add an assistant message capturing these calls
                            await self._add_tool_calls_message(
                                calls_list, partial_text_buffer
                            )

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

                            # Reset buffer & calls
                            pending_tool_calls.clear()
                            partial_text_buffer = ""

                        elif finish_reason == "stop":
                            # Handle thinking if present
                            await self._handle_thinking(
                                thinking_signatures, accumulated_thinking
                            )

                            # 6) The LLM is done. If we have any leftover partial text,
                            #    finalize it in the conversation
                            if partial_text_buffer:
                                # Create the final message with metadata including citations
                                final_message = Message(
                                    role="assistant",
                                    content=partial_text_buffer,
                                    metadata={
                                        "citations": self.streaming_citations
                                    },
                                )

                                # Add it to the conversation
                                await self.conversation.add_message(
                                    final_message
                                )

                            # (a) Prepare final answer with optimized citations
                            consolidated_citations = []
                            # Group citations by ID with all their spans
                            for (
                                cid,
                                spans,
                            ) in citation_tracker.get_all_spans().items():
                                if cid in citation_payloads:
                                    consolidated_citations.append(
                                        {
                                            "id": cid,
                                            "object": "citation",
                                            "spans": [
                                                {"start": s[0], "end": s[1]}
                                                for s in spans
                                            ],
                                            "payload": citation_payloads[cid],
                                        }
                                    )

                            # Create final answer payload
                            final_evt_payload = {
                                "id": "msg_final",
                                "object": "agent.final_answer",
                                "generated_answer": partial_text_buffer,
                                "citations": consolidated_citations,
                            }

                            # Emit final answer event
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

                # If we exit the while loop due to hitting max iterations
                if not self._completed:
                    # Generate a summary using the LLM
                    summary = await self._generate_llm_summary(
                        iterations_count
                    )

                    # Send the summary as a message event
                    async for line in SSEFormatter.yield_message_event(
                        summary
                    ):
                        yield line

                    # Add summary to conversation with citations metadata
                    await self.conversation.add_message(
                        Message(
                            role="assistant",
                            content=summary,
                            metadata={"citations": self.streaming_citations},
                        )
                    )

                    # Create and emit a final answer payload with the summary
                    final_evt_payload = {
                        "id": "msg_final",
                        "object": "agent.final_answer",
                        "generated_answer": summary,
                        "citations": consolidated_citations,
                    }

                    async for line in SSEFormatter.yield_final_answer_event(
                        final_evt_payload
                    ):
                        yield line

                    # Signal the end of the SSE stream
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

    async def _handle_thinking(
        self, thinking_signatures, accumulated_thinking
    ):
        """Process any accumulated thinking content"""
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
            await self.conversation.add_message(assistant_msg)

        elif thinking_signatures:
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
                await self.conversation.add_message(assistant_msg)

    async def _add_tool_calls_message(self, calls_list, partial_text_buffer):
        """Add a message with tool calls to the conversation"""
        assistant_msg = Message(
            role="assistant",
            content=partial_text_buffer or "",
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

    def _create_tool_call_data(self, call_info):
        """Create tool call data structure from call info"""
        return {
            "tool_call_id": call_info["tool_call_id"],
            "name": call_info["name"],
            "arguments": call_info["arguments"],
        }

    def _create_citation_payload(self, short_id, payload):
        """Create citation payload for a short ID"""
        # This will be overridden in RAG subclasses
        # check if as_dict is on payload
        if hasattr(payload, "as_dict"):
            payload = payload.as_dict()
        if hasattr(payload, "dict"):
            payload = payload.dict
        if hasattr(payload, "to_dict"):
            payload = payload.to_dict()

        return {
            "id": f"{short_id}",
            "object": "citation",
            "payload": dump_obj(payload),  # Will be populated in RAG agents
        }

    def _create_final_answer_payload(self, answer_text, citations):
        """Create the final answer payload"""
        # This will be extended in RAG subclasses
        return {
            "id": "msg_final",
            "object": "agent.final_answer",
            "generated_answer": answer_text,
            "citations": citations,
        }


class R2RXMLStreamingAgent(R2RStreamingAgent):
    """
    A streaming agent that parses XML-formatted responses with special handling for:
     - <think> or <Thought> blocks for chain-of-thought reasoning
     - <Action>, <ToolCalls>, <ToolCall> blocks for tool execution
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

        # Initialize citation tracker for this run
        citation_tracker = CitationTracker()

        # Dictionary to store citation payloads by ID
        citation_payloads = {}

        # Track all citations emitted during streaming for final persistence
        self.streaming_citations: list[dict] = []

        async def sse_generator() -> AsyncGenerator[str, None]:
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
                    accumulated_thinking = ""
                    thinking_signatures = {}

                    async for chunk in llm_stream:
                        delta = chunk.choices[0].delta
                        finish_reason = chunk.choices[0].finish_reason

                        # Handle thinking if present
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

                            # (b) Find new citation spans in the accumulated text
                            new_citation_spans = find_new_citation_spans(
                                iteration_buffer, citation_tracker
                            )

                            # Process each new citation span
                            for cid, spans in new_citation_spans.items():
                                for span in spans:
                                    # Check if this is the first time we've seen this citation ID
                                    is_new_citation = (
                                        citation_tracker.is_new_citation(cid)
                                    )

                                    # Get payload if it's a new citation
                                    payload = None
                                    if is_new_citation:
                                        source_obj = self.search_results_collector.find_by_short_id(
                                            cid
                                        )
                                        if source_obj:
                                            # Store payload for reuse
                                            payload = dump_obj(source_obj)
                                            citation_payloads[cid] = payload

                                    # Create citation event payload
                                    citation_data = {
                                        "id": cid,
                                        "object": "citation",
                                        "is_new": is_new_citation,
                                        "span": {
                                            "start": span[0],
                                            "end": span[1],
                                        },
                                    }

                                    # Only include full payload for new citations
                                    if is_new_citation and payload:
                                        citation_data["payload"] = payload

                                    # Add to streaming citations for final answer
                                    self.streaming_citations.append(
                                        citation_data
                                    )

                                    # Emit the citation event
                                    async for (
                                        line
                                    ) in SSEFormatter.yield_citation_event(
                                        citation_data
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

                    # Process any accumulated thinking
                    await self._handle_thinking(
                        thinking_signatures, accumulated_thinking
                    )

                    # 6) The LLM is done. If we have any leftover partial text,
                    #    finalize it in the conversation
                    if iteration_buffer:
                        # Create the final message with metadata including citations
                        final_message = Message(
                            role="assistant",
                            content=iteration_buffer,
                            metadata={"citations": self.streaming_citations},
                        )

                        # Add it to the conversation
                        await self.conversation.add_message(final_message)

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
                                        async for line in (
                                            SSEFormatter.yield_tool_call_event(
                                                call_evt_data
                                            )
                                        ):
                                            yield line

                                        try:
                                            tool_result = await self.handle_function_or_tool_call(
                                                tool_name,
                                                json.dumps(tool_params),
                                                tool_id=tool_call_id,
                                                save_messages=False,
                                            )
                                            result_content = tool_result.llm_formatted_result
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
                                        async for line in SSEFormatter.yield_tool_result_event(
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

                        # Update the conversation with tool results
                        await self.conversation.add_message(
                            Message(
                                role="assistant",
                                content=iteration_text,
                                metadata={
                                    "citations": self.streaming_citations
                                },
                            )
                        )
                    else:
                        # (a) Prepare final answer with optimized citations
                        consolidated_citations = []
                        # Group citations by ID with all their spans
                        for (
                            cid,
                            spans,
                        ) in citation_tracker.get_all_spans().items():
                            if cid in citation_payloads:
                                consolidated_citations.append(
                                    {
                                        "id": cid,
                                        "object": "citation",
                                        "spans": [
                                            {"start": s[0], "end": s[1]}
                                            for s in spans
                                        ],
                                        "payload": citation_payloads[cid],
                                    }
                                )

                        # Create final answer payload
                        final_evt_payload = {
                            "id": "msg_final",
                            "object": "agent.final_answer",
                            "generated_answer": iteration_buffer,
                            "citations": consolidated_citations,
                        }

                        # Emit final answer event
                        async for (
                            line
                        ) in SSEFormatter.yield_final_answer_event(
                            final_evt_payload
                        ):
                            yield line

                        # (b) Signal the end of the SSE stream
                        yield SSEFormatter.yield_done_event()
                        self._completed = True

                # If we exit the while loop due to hitting max iterations
                if not self._completed:
                    # Generate a summary using the LLM
                    summary = await self._generate_llm_summary(
                        iterations_count
                    )

                    # Send the summary as a message event
                    async for line in SSEFormatter.yield_message_event(
                        summary
                    ):
                        yield line

                    # Add summary to conversation with citations metadata
                    await self.conversation.add_message(
                        Message(
                            role="assistant",
                            content=summary,
                            metadata={"citations": self.streaming_citations},
                        )
                    )

                    # Create and emit a final answer payload with the summary
                    final_evt_payload = {
                        "id": "msg_final",
                        "object": "agent.final_answer",
                        "generated_answer": summary,
                        "citations": consolidated_citations,
                    }

                    async for line in SSEFormatter.yield_final_answer_event(
                        final_evt_payload
                    ):
                        yield line

                    # Signal the end of the SSE stream
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


class R2RXMLToolsAgent(R2RAgent):
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

    async def process_llm_response(self, response, *args, **kwargs):
        """
        Override the base process_llm_response to handle XML structured responses
        including thoughts and tool calls.
        """
        if self._completed:
            return

        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if not message.content:
            # If there's no content, let the parent class handle the normal tool_calls flow
            return await super().process_llm_response(
                response, *args, **kwargs
            )

        # Get the response content
        content = message.content

        # HACK for gemini
        content = content.replace("```action", "")
        content = content.replace("```tool_code", "")
        content = content.replace("```", "")

        if (
            not content.startswith("<")
            and "deepseek" in self.rag_generation_config.model
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

                                # Add tool result to XML
                                xml_toolcalls += (
                                    f"<ToolCall>"
                                    f"<Name>{tool_name}</Name>"
                                    f"<Parameters>{json.dumps(tool_params)}</Parameters>"
                                    f"<Result>{tool_result.llm_formatted_result}</Result>"
                                    f"</ToolCall>"
                                )

                            except Exception as e:
                                logger.error(f"Error in tool call: {str(e)}")
                                # Add error to XML
                                xml_toolcalls += (
                                    f"<ToolCall>"
                                    f"<Name>{tool_name}</Name>"
                                    f"<Parameters>{json.dumps(tool_params)}</Parameters>"
                                    f"<Result>Error: {str(e)}</Result>"
                                    f"</ToolCall>"
                                )

            xml_toolcalls += "</ToolCalls>"
            pre_action_text = content[: content.find(action_block)]
            post_action_text = content[
                content.find(action_block) + len(action_block) :
            ]
            iteration_text = pre_action_text + xml_toolcalls + post_action_text

            # Create the assistant message
            await self.conversation.add_message(
                Message(role="assistant", content=iteration_text)
            )
        else:
            # Create an assistant message with the content as-is
            await self.conversation.add_message(
                Message(role="assistant", content=content)
            )

        # Only mark as completed if the finish_reason is "stop" or there are no action calls
        # This allows the agent to continue the conversation when tool calls are processed
        if finish_reason == "stop":
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
