import copy
import json
import logging
import os
import time
import uuid
from typing import Any, AsyncGenerator, Generator, Optional

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


def generate_tool_id() -> str:
    """Generate a unique tool ID using UUID4."""
    return f"tool_{uuid.uuid4().hex[:12]}"


def openai_message_to_anthropic_block(msg: dict) -> dict:
    """
    Converts a single OpenAI-style message (including function/tool calls)
    into one Anthropic-style message.
    """
    role = msg.get("role", "")
    content = msg.get("content", "")
    tool_call_id = msg.get("tool_call_id")

    if role == "system":
        return msg

    if role in ["user", "assistant"]:
        function_call = msg.get("function_call")
        if function_call:
            fn_name = function_call.get("name", "")
            raw_args = function_call.get("arguments", "{}")
            try:
                fn_args = json.loads(raw_args)
            except json.JSONDecodeError:
                fn_args = {"_raw": raw_args}

            return {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_call_id,
                        "name": fn_name,
                        "input": fn_args,
                    }
                ],
            }
        else:
            return {"role": role, "content": content}

    if role in ["function", "tool"]:
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

    return {"role": role, "content": content}


class AnthropicCompletionProvider(CompletionProvider):
    def __init__(self, config: CompletionConfig, *args, **kwargs) -> None:
        super().__init__(config)
        self.client = Anthropic()  # Synchronous client
        self.async_client = AsyncAnthropic()  # Asynchronous client
        logger.debug("AnthropicCompletionProvider initialized successfully")

    def _get_base_args(self, generation_config: GenerationConfig) -> dict:
        """
        Build the arguments dictionary for Anthropic's messages.create(),
        including optional extended thinking parameters.
        """
        args = {
            "model": generation_config.model.split("anthropic/")[-1],
            "temperature": generation_config.temperature,
            "max_tokens": generation_config.max_tokens_to_sample,
            "stream": generation_config.stream,
        }
        if generation_config.top_p:
            args["top_p"] = generation_config.top_p

        if generation_config.tools is not None:
            anthropic_tools = []
            for tool in generation_config.tools:
                tool_def = {
                    "name": tool["function"]["name"],
                    "description": tool["function"]["description"],
                    "input_schema": tool["function"]["parameters"],
                }
                anthropic_tools.append(tool_def)
            args["tools"] = anthropic_tools

            if hasattr(generation_config, "tool_choice"):
                tool_choice = generation_config.tool_choice
                if isinstance(tool_choice, str):
                    if tool_choice == "auto":
                        args["tool_choice"] = {"type": "auto"}
                    elif tool_choice == "any":
                        args["tool_choice"] = {"type": "any"}
                elif isinstance(tool_choice, dict):
                    if tool_choice.get("type") == "function":
                        args["tool_choice"] = {"type": "function", "name": tool_choice.get("name")}
                if hasattr(generation_config, "disable_parallel_tool_use"):
                    args["tool_choice"] = args.get("tool_choice", {})
                    args["tool_choice"]["disable_parallel_tool_use"] = generation_config.disable_parallel_tool_use

        # --- Extended Thinking Support ---
        if getattr(generation_config, "extended_thinking", False):
            if not hasattr(generation_config, "thinking_budget") or generation_config.thinking_budget is None:
                raise ValueError("Extended thinking is enabled but no thinking_budget is provided.")
            if generation_config.thinking_budget >= generation_config.max_tokens_to_sample:
                raise ValueError("thinking_budget must be less than max_tokens_to_sample.")
            args["thinking"] = {
                "type": "enabled",
                "budget_tokens": generation_config.thinking_budget,
            }
        # -----------------------------------
        return args

    def _convert_to_chat_completion(self, anthropic_msg: Message) -> dict:
        """
        Convert a non-streaming Anthropic Message into an OpenAI-style dict.
        This implementation gathers text blocks as the final output.
        (Internal thinking blocks are used only for reasoning and may be omitted.)
        """
        content_text = ""
        if anthropic_msg.content:
            text_pieces = []
            for block in anthropic_msg.content:
                if hasattr(block, "type") and block.type == "thinking":
                    text_pieces.append("<think>")
                    text_pieces.append(block.thinking)
                    text_pieces.append("</think>")
                if hasattr(block, "type") and block.type == "text":
                    text_pieces.append(block.text)
            content_text = "".join(text_pieces)

        finish_reason = (
            "stop" if anthropic_msg.stop_reason == "end_turn" else anthropic_msg.stop_reason
        )

        return {
            "id": anthropic_msg.id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": anthropic_msg.model.split("anthropic/")[-1],
            "usage": {
                "prompt_tokens": anthropic_msg.usage.input_tokens if anthropic_msg.usage else 0,
                "completion_tokens": anthropic_msg.usage.output_tokens if anthropic_msg.usage else 0,
                "total_tokens": (
                    (anthropic_msg.usage.input_tokens if anthropic_msg.usage else 0)
                    + (anthropic_msg.usage.output_tokens if anthropic_msg.usage else 0)
                ),
            },
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": anthropic_msg.role,
                        "content": content_text,
                    },
                    "finish_reason": finish_reason,
                }
            ],
        }

    def _split_system_messages(self, messages: list[dict]) -> (list[dict], Optional[str]):
        system_msg = None
        filtered = []
        pending_tool_results = []

        for m in copy.deepcopy(messages):
            if m["role"] == "system" and system_msg is None:
                system_msg = m["content"]
                continue

            if m.get("tool_calls"):
                if m.get("content"):
                    filtered.append({"role": "assistant", "content": m["content"]})
                filtered.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": call["id"],
                            "name": call["function"]["name"],
                            "input": json.loads(call["function"]["arguments"]),
                        }
                        for call in m["tool_calls"]
                    ],
                })
            elif m["role"] in ["function", "tool"]:
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id"),
                    "content": m["content"],
                })
                if len(pending_tool_results) == len(filtered[-1]["content"]):
                    filtered.append({"role": "user", "content": pending_tool_results})
                    pending_tool_results = []
            else:
                filtered.append(openai_message_to_anthropic_block(m))

        return filtered, system_msg

    async def _execute_task(self, task: dict[str, Any]):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("Missing ANTHROPIC_API_KEY in environment.")
            raise ValueError("Anthropic API key not found. Set ANTHROPIC_API_KEY env var.")

        messages = task["messages"]
        generation_config = task["generation_config"]
        extra_kwargs = task["kwargs"]

        base_args = self._get_base_args(generation_config)
        filtered_messages, system_msg = self._split_system_messages(messages)
        base_args["messages"] = filtered_messages
        if system_msg:
            base_args["system"] = system_msg

        args = {**base_args, **extra_kwargs}
        logger.debug(f"Anthropic async call with args={args}")

        if generation_config.stream:
            return self._execute_task_async_streaming(args)
        else:
            return await self._execute_task_async_nonstreaming(args)

    async def _execute_task_async_nonstreaming(self, args: dict) -> LLMChatCompletion:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("Missing ANTHROPIC_API_KEY in environment.")
            raise ValueError("Anthropic API key not found. Set ANTHROPIC_API_KEY env var.")

        try:
            response = await self.async_client.messages.create(**args)
            logger.debug("Anthropic async non-stream call succeeded.")
            return LLMChatCompletion(**self._convert_to_chat_completion(response))
        except Exception as e:
            logger.error(f"Anthropic async non-stream call failed: {e}")
            raise

    async def _execute_task_async_streaming(self, args: dict) -> AsyncGenerator[dict, None]:
        args.pop("stream", None)
        try:
            async with self.async_client.messages.stream(**args) as stream:
                buffer_data = {
                    "tool_json_buffer": "",
                    "tool_name": None,
                    "message_id": f"chatcmpl-{int(time.time())}",
                }
                model_name = args.get("model", "anthropic/claude-2")
                async for event in stream:
                    chunks = self._process_stream_event(
                        event=event,
                        buffer_data=buffer_data,
                        model_name=model_name.split("anthropic/")[-1],
                    )
                    for chunk in chunks:
                        yield chunk
        except Exception as e:
            logger.error(f"Failed to execute streaming Anthropic task: {e}")
            raise

    def _execute_task_sync(self, task: dict[str, Any]):
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
        try:
            response = self.client.messages.create(**args)
            logger.debug("Anthropic sync non-stream call succeeded.")
            return LLMChatCompletion(**self._convert_to_chat_completion(response))
        except Exception as e:
            logger.error(f"Anthropic sync call failed: {e}")
            raise

    def _execute_task_sync_streaming(self, args: dict) -> Generator[dict, None, None]:
        args.pop("stream", None)
        try:
            with self.client.messages.stream(**args) as stream:
                buffer_data = {
                    "tool_json_buffer": "",
                    "tool_name": None,
                    "message_id": f"chatcmpl-{int(time.time())}",
                }
                model_name = args.get("model", "anthropic/claude-2")
                for event in stream:
                    chunks = self._process_stream_event(
                        event=event,
                        buffer_data=buffer_data,
                        model_name=model_name.split("anthropic/")[-1],
                    )
                    for chunk in chunks:
                        yield chunk
        except Exception as e:
            logger.error(f"Anthropic sync streaming call failed: {e}")
            raise

    def _process_stream_event(self, event: Any, buffer_data: dict, model_name: str) -> list[dict]:
        print(f'raw event: {event}')
        chunks: list[dict] = []

        def make_base_chunk() -> dict:
            return {
                "id": buffer_data["message_id"],
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model_name,
                "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
            }

        if isinstance(event, RawMessageStartEvent):
            buffer_data["message_id"] = event.message.id
            chunk = make_base_chunk()
            input_tokens = event.message.usage.input_tokens if event.message.usage else 0
            chunk["usage"] = {
                "prompt_tokens": input_tokens,
                "completion_tokens": 0,
                "total_tokens": input_tokens,
            }
            chunks.append(chunk)

        elif isinstance(event, RawContentBlockStartEvent):
            if hasattr(event.content_block, "type"):
                if event.content_block.type == "thinking":
                    buffer_data["is_collecting_thinking"] = True
                    buffer_data["thinking_buffer"] = ""
                elif event.content_block.type == "tool_use" or isinstance(event.content_block, ToolUseBlock):
                    buffer_data["tool_name"] = event.content_block.name
                    buffer_data["tool_json_buffer"] = ""
                    buffer_data["is_collecting_tool"] = True
            else:
                if isinstance(event.content_block, ToolUseBlock):
                    buffer_data["tool_name"] = event.content_block.name
                    buffer_data["tool_json_buffer"] = ""
                    buffer_data["is_collecting_tool"] = True

        elif isinstance(event, RawContentBlockDeltaEvent):
            delta_obj = getattr(event, "delta", None)
            if hasattr(delta_obj, "text"):
                text_chunk = delta_obj.text
                if buffer_data.get("is_collecting_thinking"):
                    buffer_data["thinking_buffer"] += text_chunk
                elif buffer_data.get("is_collecting_tool"):
                    partial_json = getattr(delta_obj, "partial_json", None)
                    if partial_json:
                        buffer_data["tool_json_buffer"] += partial_json
                else:
                    if text_chunk:
                        chunk = make_base_chunk()
                        chunk["choices"][0]["delta"] = {"content": text_chunk}
                        chunks.append(chunk)

        elif isinstance(event, ContentBlockStopEvent):
            if buffer_data.get("is_collecting_thinking"):
                thinking_text = buffer_data.get("thinking_buffer", "")
                chunk = make_base_chunk()
                # Include the accumulated thinking text in a separate key.
                chunk["choices"][0]["delta"] = {"thinking": thinking_text}
                chunks.append(chunk)
                buffer_data["is_collecting_thinking"] = False
                buffer_data["thinking_buffer"] = ""
            elif buffer_data.get("is_collecting_tool"):
                try:
                    json.loads(buffer_data["tool_json_buffer"])
                    chunk = make_base_chunk()
                    chunk["choices"][0]["delta"] = {
                        "tool_calls": [
                            {
                                "index": 0,
                                "type": "function",
                                "id": f"call_{generate_tool_id()}",
                                "function": {
                                    "name": buffer_data["tool_name"],
                                    "arguments": buffer_data["tool_json_buffer"],
                                },
                            }
                        ]
                    }
                    chunks.append(chunk)
                    buffer_data["is_collecting_tool"] = False
                    buffer_data["tool_json_buffer"] = ""
                    buffer_data["tool_name"] = None
                except json.JSONDecodeError:
                    logger.warning("Incomplete JSON in tool call, skipping chunk")

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
