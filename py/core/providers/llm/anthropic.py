import copy
import json
import logging
import os
import time
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Union

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import (
    ContentBlockStopEvent,
    Message,
    MessageStopEvent,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawMessageStartEvent,
    TextDelta,
    ToolUseBlock,
)

from core.base.abstractions import GenerationConfig, LLMChatCompletion
from core.base.providers.llm import CompletionConfig, CompletionProvider

logger = logging.getLogger(__name__)


def openai_message_to_anthropic_block(msg: dict) -> dict:
    """
    Converts a single OpenAI-style message (including function/tool calls)
    into one Anthropic-style message.

    Expected keys in `msg` can include:
      - role: "system" | "assistant" | "user" | "function" | "tool"
      - content: str (possibly JSON arguments or the final text)
      - name: str (tool/function name)
      - tool_call_id or function_call arguments
      - function_call: {"name": ..., "arguments": "..."}
    """
    role = msg.get("role", "")
    content = msg.get("content", "")
    name = msg.get("name")  # Tool or function name
    tool_call_id = msg.get("tool_call_id")

    # System -> store it for the Anthropic `system` param (handled separately).
    if role == "system":
        return msg

    # Basic user or assistant messages (with no function/tool call)
    if role in ["user", "assistant"]:
        # If an assistant message has function_call, treat as "tool_use"
        function_call = msg.get("function_call")
        if function_call:
            # This is the assistant calling a tool
            fn_name = function_call.get("name", "")
            raw_args = function_call.get("arguments", "{}")
            try:
                fn_args = json.loads(raw_args)
            except json.JSONDecodeError:
                # If the model produced invalid JSON, do your fallback
                fn_args = {"_raw": raw_args}

            return {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_call_id,  # If you track a unique call ID
                        "name": fn_name,
                        "input": fn_args,
                    }
                ],
            }
        else:
            # It's a normal user or assistant message
            return {"role": role, "content": content}

    # "function" or "tool" role => typically the result from that tool
    if role in ["function", "tool"]:
        # Return as "tool_result" from the user's perspective
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": content,
                }
            ],
        }

    # Default fallback (unrecognized role): pass it through
    return {"role": role, "content": content}


class AnthropicCompletionProvider(CompletionProvider):
    def __init__(self, config: CompletionConfig, *args, **kwargs) -> None:
        super().__init__(config)
        if config.provider != "anthropic":
            logger.error(f"Invalid provider: {config.provider}")
            raise ValueError(
                "AnthropicCompletionProvider must be used with provider='anthropic'."
            )

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("Missing ANTHROPIC_API_KEY in environment.")
            raise ValueError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY env var."
            )

        # Create sync + async clients
        self.client = Anthropic()  # for sync calls
        self.async_client = AsyncAnthropic()  # for async calls
        logger.debug("AnthropicCompletionProvider initialized successfully")

    def _get_base_args(self, generation_config: GenerationConfig) -> dict:
        """
        Build the arguments dictionary for Anthropic's messages.create().

        Handles tool configuration according to Anthropic's schema:
        {
            "type": "function",  # Use 'function' type for custom tools
            "name": "tool_name",
            "description": "tool description",
            "parameters": {  # Note: Anthropic expects 'parameters', not 'input_schema'
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
        """
        args = {
            "model": generation_config.model,
            "temperature": generation_config.temperature,
            "top_p": generation_config.top_p,
            "max_tokens": generation_config.max_tokens_to_sample,
            "stream": generation_config.stream,
        }

        if generation_config.tools is not None:
            # Convert tools to Anthropic's format
            anthropic_tools = []
            for tool in generation_config.tools:
                # required = parameters.pop("required", [])
                tool_def = {
                    "name": tool["function"]["name"],
                    "description": tool["function"]["description"],
                    "input_schema": tool["function"]["parameters"],
                }
                anthropic_tools.append(tool_def)

            args["tools"] = anthropic_tools

            # Handle tool_choice if specified
            if hasattr(generation_config, "tool_choice"):
                tool_choice = generation_config.tool_choice
                if isinstance(tool_choice, str):
                    if tool_choice == "auto":
                        args["tool_choice"] = {"type": "auto"}
                    elif tool_choice == "any":
                        args["tool_choice"] = {"type": "any"}
                elif isinstance(tool_choice, dict):
                    # For specific tool forcing
                    if tool_choice.get("type") == "function":
                        args["tool_choice"] = {
                            "type": "function",
                            "name": tool_choice.get("name"),
                        }

            # Handle parallel tool use setting
            if hasattr(generation_config, "disable_parallel_tool_use"):
                args["tool_choice"] = args.get("tool_choice", {})
                args["tool_choice"][
                    "disable_parallel_tool_use"
                ] = generation_config.disable_parallel_tool_use

        return args

    def _convert_to_chat_completion(self, anthropic_msg: Message) -> dict:
        """
        Convert a **non-streaming** Anthropic `Message` response into
        an OpenAI-style dict.
        """
        # anthropic_msg.content is a list of blocks; gather text from "text" blocks
        content_text = ""
        if anthropic_msg.content:
            text_pieces = []
            for block in anthropic_msg.content:
                # block might be a ToolUseBlock, or some text block
                if hasattr(block, "type") and block.type == "text":
                    text_pieces.append(block.text)
            content_text = "".join(text_pieces)

        finish_reason = (
            "stop"
            if anthropic_msg.stop_reason == "end_turn"
            else anthropic_msg.stop_reason
        )

        return {
            "id": anthropic_msg.id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": anthropic_msg.model,
            "usage": {
                "prompt_tokens": (
                    anthropic_msg.usage.input_tokens
                    if anthropic_msg.usage
                    else 0
                ),
                "completion_tokens": (
                    anthropic_msg.usage.output_tokens
                    if anthropic_msg.usage
                    else 0
                ),
                "total_tokens": (
                    (
                        anthropic_msg.usage.input_tokens
                        if anthropic_msg.usage
                        else 0
                    )
                    + (
                        anthropic_msg.usage.output_tokens
                        if anthropic_msg.usage
                        else 0
                    )
                ),
            },
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": anthropic_msg.role,  # "assistant" typically
                        "content": content_text,
                    },
                    "finish_reason": finish_reason,
                }
            ],
        }

    def _split_system_messages(
        self, messages: List[dict]
    ) -> (List[dict], Optional[str]):
        """
        Extract the system message (if any) from a combined list of messages.
        Return (filtered_messages, system_message).
        """
        system_msg = None
        filtered = []
        for m in copy.deepcopy(messages):
            if m["role"] == "system" and system_msg is None:
                system_msg = m["content"]
            else:

                m2 = None
                if m.get("tool_calls") != None:
                    m2 = {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": call["id"],
                                "name": call["function"]["name"],
                                "input": json.loads(
                                    call["function"]["arguments"]
                                ),
                            }
                            for call in m["tool_calls"]
                        ],
                    }
                    m.pop("tool_calls")

                m = openai_message_to_anthropic_block(m)
                filtered.append(m)
                if m2:
                    filtered.append(m2)
        return filtered, system_msg

    async def _execute_task(self, task: Dict[str, Any]):
        """
        Async entry point. Decide if streaming or not, then call the appropriate helper.
        """
        messages = task["messages"]
        generation_config = task["generation_config"]
        extra_kwargs = task["kwargs"]

        base_args = self._get_base_args(generation_config)
        filtered_messages, system_msg = self._split_system_messages(messages)
        base_args["messages"] = filtered_messages
        if system_msg:
            base_args["system"] = system_msg

        # Merge in additional user-supplied kwargs (if any)
        args = {**base_args, **extra_kwargs}
        logger.debug(f"Anthropic async call with args={args}")

        if generation_config.stream:
            # Return an async generator
            return self._execute_task_async_streaming(args)
        else:
            # Return a single LLMChatCompletion object
            return await self._execute_task_async_nonstreaming(args)

    async def _execute_task_async_nonstreaming(
        self, args: dict
    ) -> LLMChatCompletion:
        """
        Non-streaming call: returns the final LLMChatCompletion.
        """
        try:
            response = await self.async_client.messages.create(**args)
            logger.debug("Anthropic async non-stream call succeeded.")
            return LLMChatCompletion(
                **self._convert_to_chat_completion(response)
            )
        except Exception as e:
            logger.error(f"Anthropic async non-stream call failed: {e}")
            raise

    async def _execute_task_async_streaming(
        self, args: dict
    ) -> AsyncGenerator[dict, None]:
        """
        Streaming call (async): yields partial tokens in OpenAI-like SSE format.
        """
        # The `stream=True` is typically handled by Anthropics from the original args,
        # but we remove it to avoid conflicts and rely on `messages.stream()`.
        args.pop("stream", None)

        try:
            async with self.async_client.messages.stream(**args) as stream:
                # We'll track partial JSON for function calls in buffer_data
                buffer_data = {
                    "tool_json_buffer": "",
                    "tool_name": None,
                    "message_id": f"chatcmpl-{int(time.time())}",
                }
                model_name = args.get("model", "claude-2")

                async for event in stream:

                    # Process the event(s) in a shared function
                    chunks = self._process_stream_event(
                        event=event,
                        buffer_data=buffer_data,
                        model_name=model_name,
                    )
                    # The helper returns a list of chunk dicts
                    for chunk in chunks:
                        yield chunk

        except Exception as e:
            logger.error(f"Failed to execute streaming Anthropic task: {e}")
            raise

    def _execute_task_sync(self, task: Dict[str, Any]):
        """
        Synchronous entry point.
        """
        messages = task["messages"]
        generation_config = task["generation_config"]
        extra_kwargs = task["kwargs"]

        base_args = self._get_base_args(generation_config)
        filtered_messages, system_msg = self._split_system_messages(messages)
        base_args["messages"] = filtered_messages
        if system_msg:
            base_args["system"] = system_msg

        args = {**base_args, **extra_kwargs}
        logger.debug(f"Anthropic sync call with args={args}")

        if generation_config.stream:
            return self._execute_task_sync_streaming(args)
        else:
            return self._execute_task_sync_nonstreaming(args)

    def _execute_task_sync_nonstreaming(self, args: dict) -> LLMChatCompletion:
        """
        Non-streaming synchronous call.
        """
        try:
            response = self.client.messages.create(**args)
            logger.debug("Anthropic sync non-stream call succeeded.")
            return LLMChatCompletion(
                **self._convert_to_chat_completion(response)
            )
        except Exception as e:
            logger.error(f"Anthropic sync call failed: {e}")
            raise

    def _execute_task_sync_streaming(
        self, args: dict
    ) -> Generator[dict, None, None]:
        """
        Synchronous streaming call: yields partial tokens in a generator.
        """
        args.pop("stream", None)
        try:
            with self.client.messages.stream(**args) as stream:
                buffer_data = {
                    "tool_json_buffer": "",
                    "tool_name": None,
                    "message_id": f"chatcmpl-{int(time.time())}",
                }
                model_name = args.get("model", "claude-2")

                for event in stream:
                    # Same event-processing as async
                    chunks = self._process_stream_event(
                        event=event,
                        buffer_data=buffer_data,
                        model_name=model_name,
                    )
                    for chunk in chunks:
                        yield chunk

        except Exception as e:
            logger.error(f"Anthropic sync streaming call failed: {e}")
            raise

    def _process_stream_event(
        self, event: Any, buffer_data: dict, model_name: str
    ) -> list[dict]:
        chunks: list[dict] = []

        def make_base_chunk() -> dict:
            return {
                "id": buffer_data["message_id"],
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": None,
                    }
                ],
            }

        if isinstance(event, RawMessageStartEvent):
            buffer_data["message_id"] = event.message.id
            chunk = make_base_chunk()
            input_tokens = (
                event.message.usage.input_tokens if event.message.usage else 0
            )
            chunk["usage"] = {
                "prompt_tokens": input_tokens,
                "completion_tokens": 0,
                "total_tokens": input_tokens,
            }
            chunks.append(chunk)

        elif isinstance(event, RawContentBlockStartEvent):
            if isinstance(event.content_block, ToolUseBlock):
                buffer_data["tool_name"] = event.content_block.name
                buffer_data["tool_json_buffer"] = ""  # Reset buffer
                buffer_data["is_collecting_tool"] = (
                    True  # Flag to indicate we're collecting a tool call
                )

        elif isinstance(event, RawContentBlockDeltaEvent):
            delta_obj = getattr(event, "delta", None)
            if isinstance(delta_obj, TextDelta):
                # Regular text content - yield immediately
                text_chunk = delta_obj.text
                if text_chunk:
                    chunk = make_base_chunk()
                    chunk["choices"][0]["delta"] = {"content": text_chunk}
                    chunks.append(chunk)
            else:
                # Tool call JSON - accumulate in buffer
                partial_json = getattr(delta_obj, "partial_json", None)
                if partial_json and buffer_data.get("is_collecting_tool"):
                    buffer_data["tool_json_buffer"] += partial_json

        elif isinstance(event, ContentBlockStopEvent):
            # Tool collection is complete - yield the full tool call
            if buffer_data.get("is_collecting_tool"):
                try:
                    # Validate JSON is complete
                    json.loads(buffer_data["tool_json_buffer"])

                    chunk = make_base_chunk()
                    chunk["choices"][0]["delta"] = {
                        "tool_calls": [
                            {
                                "index": 0,
                                "type": "function",
                                "id": f"call_{buffer_data['message_id']}",
                                "function": {
                                    "name": buffer_data["tool_name"],
                                    "arguments": buffer_data[
                                        "tool_json_buffer"
                                    ],
                                },
                            }
                        ]
                    }
                    chunks.append(chunk)

                    # Reset tool collection state
                    buffer_data["is_collecting_tool"] = False
                    buffer_data["tool_json_buffer"] = ""
                    buffer_data["tool_name"] = None
                except json.JSONDecodeError:
                    # JSON is incomplete - don't yield anything
                    logger.warning(
                        "Incomplete JSON in tool call, skipping chunk"
                    )

        elif isinstance(event, MessageStopEvent):
            stop_reason = event.message.stop_reason
            chunk = make_base_chunk()
            if stop_reason == "tool_use":
                chunk["choices"][0]["delta"] = {}
                chunk["choices"][0]["finish_reason"] = "tool_calls"
            else:
                chunk["choices"][0]["delta"] = {}
                chunk["choices"][0]["finish_reason"] = "stop"
            chunks.append(chunk)

        return chunks
