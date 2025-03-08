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
    ThinkingBlock,
    RedactedThinkingBlock,
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
        # Check if this message has structured content (with thinking blocks)
        if isinstance(content, list) and all(isinstance(block, dict) for block in content):
            return {"role": role, "content": content}

        # Check for function calls
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
                        args["tool_choice"] = {
                            "type": "function",
                            "name": tool_choice.get("name"),
                        }
                if hasattr(generation_config, "disable_parallel_tool_use"):
                    args["tool_choice"] = args.get("tool_choice", {})
                    args["tool_choice"][
                        "disable_parallel_tool_use"
                    ] = generation_config.disable_parallel_tool_use

        # --- Extended Thinking Support ---
        if getattr(generation_config, "extended_thinking", False):
            if (
                not hasattr(generation_config, "thinking_budget")
                or generation_config.thinking_budget is None
            ):
                raise ValueError(
                    "Extended thinking is enabled but no thinking_budget is provided."
                )
            if (
                generation_config.thinking_budget
                >= generation_config.max_tokens_to_sample
            ):
                raise ValueError(
                    "thinking_budget must be less than max_tokens_to_sample."
                )
            args["thinking"] = {
                "type": "enabled",
                "budget_tokens": generation_config.thinking_budget,
            }
        # -----------------------------------
        return args

    def _create_openai_style_message(self, content_blocks, tool_calls=None):
        """
        Create an OpenAI-style message from Anthropic content blocks
        while preserving the original structure.
        """
        display_content = ""
        structured_content = []
        
        for block in content_blocks:
            if block.type == "text":
                display_content += block.text
            elif block.type == "thinking" and hasattr(block, "thinking"):
                # Store the complete thinking block
                structured_content.append({
                    "type": "thinking",
                    "thinking": block.thinking,
                    "signature": block.signature
                })
                # For display/logging
                display_content += f"<think>{block.thinking}</think>"
            elif block.type == "redacted_thinking" and hasattr(block, "data"):
                # Store the complete redacted thinking block
                structured_content.append({
                    "type": "redacted_thinking",
                    "data": block.data
                })
                # Add a placeholder for display/logging
                display_content += "<redacted thinking block>"
            elif block.type == "tool_use":
                # Tool use blocks are handled separately via tool_calls
                pass
        
        # If we have structured content (thinking blocks), use that
        if structured_content:
            # Add any text block at the end if needed
            for block in content_blocks:
                if block.type == "text":
                    structured_content.append({
                        "type": "text",
                        "text": block.text
                    })
            
            return {
                "content": display_content or None,
                "structured_content": structured_content
            }
        else:
            # If no structured content, just return the display content
            return {
                "content": display_content or None
            }

    def _convert_to_chat_completion(self, anthropic_msg: Message) -> dict:
        """
        Convert a non-streaming Anthropic Message into an OpenAI-style dict.
        Preserves thinking blocks for proper handling.
        """
        tool_calls = []
        message_data = {"role": anthropic_msg.role}
        
        if anthropic_msg.content:
            # First, extract any tool use blocks
            for block in anthropic_msg.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_calls.append({
                        "index": len(tool_calls),
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        }
                    })
            
            # Then create the message with appropriate content
            message_data.update(self._create_openai_style_message(anthropic_msg.content, tool_calls))
            
            # If we have tool calls, add them
            if tool_calls:
                message_data["tool_calls"] = tool_calls

        finish_reason = (
            "stop"
            if anthropic_msg.stop_reason == "end_turn"
            else anthropic_msg.stop_reason
        )
        finish_reason = "tool_calls" if anthropic_msg.stop_reason == "tool_use" else finish_reason

        return {
            "id": anthropic_msg.id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": anthropic_msg.model.split("anthropic/")[-1],
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
                    "message": message_data,
                    "finish_reason": finish_reason,
                }
            ],
        }

    def _split_system_messages(
        self, messages: list[dict]
    ) -> (list[dict], Optional[str]):
        """
        Process messages for Anthropic API, ensuring proper format for tool use and thinking blocks.
        """
        system_msg = None
        filtered = []
        
        # Look for pairs of tool_use and tool_result
        i = 0
        while i < len(messages):
            m = copy.deepcopy(messages[i])
            
            # Handle system message
            if m["role"] == "system" and system_msg is None:
                system_msg = m["content"]
                i += 1
                continue
            
            # Case 1: Message with list format content (thinking blocks or tool blocks)
            if isinstance(m.get("content"), list) and len(m["content"]) > 0 and isinstance(m["content"][0], dict):
                filtered.append({"role": m["role"], "content": m["content"]})
                i += 1
                continue
            
            # Case 2: Message with structured_content field
            elif m.get("structured_content") and m["role"] == "assistant":
                filtered.append({"role": "assistant", "content": m["structured_content"]})
                i += 1
                continue
                
            # Case 3: Tool calls in an assistant message
            elif m.get("tool_calls") and m["role"] == "assistant":
                # Add content if it exists
                if m.get("content") and not isinstance(m["content"], list):
                    content_to_add = m["content"]
                    # Handle content with thinking tags
                    if "<think>" in content_to_add:
                        thinking_start = content_to_add.find("<think>")
                        thinking_end = content_to_add.find("</think>")
                        if thinking_start >= 0 and thinking_end > thinking_start:
                            thinking_content = content_to_add[thinking_start + 7:thinking_end]
                            text_content = content_to_add[thinking_end + 8:].strip()
                            filtered.append({
                                "role": "assistant",
                                "content": [
                                    {
                                        "type": "thinking",
                                        "thinking": thinking_content,
                                        "signature": "placeholder_signature"  # This is a placeholder
                                    },
                                    {
                                        "type": "text",
                                        "text": text_content
                                    }
                                ]
                            })
                        else:
                            filtered.append({"role": "assistant", "content": content_to_add})
                    else:
                        filtered.append({"role": "assistant", "content": content_to_add})
                    
                # Add tool use blocks
                tool_uses = []
                for call in m["tool_calls"]:
                    tool_uses.append({
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["function"]["name"],
                        "input": json.loads(call["function"]["arguments"]),
                    })
                
                filtered.append({"role": "assistant", "content": tool_uses})
                
                # Check if next message is a tool result for this tool call
                if i + 1 < len(messages) and messages[i + 1]["role"] in ["function", "tool"]:
                    next_m = copy.deepcopy(messages[i + 1])
                    
                    # Make sure this is a tool result for the current tool use
                    if next_m.get("tool_call_id") in [call["id"] for call in m["tool_calls"]]:
                        # Add tool result as a user message
                        filtered.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": next_m["tool_call_id"],
                                "content": next_m["content"]
                            }]
                        })
                        i += 2  # Skip both the tool call and result
                        continue
                
                i += 1
                continue
                
            # Case 4: Direct tool result (might be missing its paired tool call)
            elif m["role"] in ["function", "tool"] and m.get("tool_call_id"):
                # Add a user message with the tool result
                filtered.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m["tool_call_id"],
                        "content": m["content"]
                    }]
                })
                i += 1
                continue
                
            # Default case: normal message
            else:
                filtered.append(openai_message_to_anthropic_block(m))
                i += 1
                
        # Final validation: ensure no tool_use is at the end without a tool_result
        if filtered and len(filtered) > 1:
            last_msg = filtered[-1]
            if (last_msg["role"] == "assistant" and 
                isinstance(last_msg.get("content"), list) and 
                any(block.get("type") == "tool_use" for block in last_msg["content"])):
                logger.warning("Found tool_use at end of conversation without tool_result - removing it")
                filtered.pop()  # Remove problematic message
        
        return filtered, system_msg

    async def _execute_task(self, task: dict[str, Any]):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("Missing ANTHROPIC_API_KEY in environment.")
            raise ValueError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY env var."
            )

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

    async def _execute_task_async_nonstreaming(
        self, args: dict
    ) -> LLMChatCompletion:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("Missing ANTHROPIC_API_KEY in environment.")
            raise ValueError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY env var."
            )

        try:
            logger.debug(f"Anthropic API request: {args}")
            print(f"MESSAGES = {args['messages']}")
            response = await self.async_client.messages.create(**args)
            logger.debug(f"Anthropic API response: {response}")
            return LLMChatCompletion(
                **self._convert_to_chat_completion(response)
            )
        except Exception as e:
            logger.error(f"Anthropic async non-stream call failed: {e}")
            raise

    async def _execute_task_async_streaming(
        self, args: dict
    ) -> AsyncGenerator[dict, None]:
        args.pop("stream", None)
        try:
            async with self.async_client.messages.stream(**args) as stream:
                buffer_data = {
                    "tool_json_buffer": "",
                    "tool_name": None,
                    "tool_id": None,
                    "is_collecting_tool": False,
                    "thinking_buffer": "",
                    "is_collecting_thinking": False,
                    "thinking_signature": None,
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
            return LLMChatCompletion(
                **self._convert_to_chat_completion(response)
            )
        except Exception as e:
            logger.error(f"Anthropic sync call failed: {e}")
            raise

    def _execute_task_sync_streaming(
        self, args: dict
    ) -> Generator[dict, None, None]:
        args.pop("stream", None)
        try:
            with self.client.messages.stream(**args) as stream:
                buffer_data = {
                    "tool_json_buffer": "",
                    "tool_name": None,
                    "tool_id": None,
                    "is_collecting_tool": False,
                    "thinking_buffer": "",
                    "is_collecting_thinking": False,
                    "thinking_signature": None,
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
                "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
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
            if hasattr(event.content_block, "type"):
                block_type = event.content_block.type
                if block_type == "thinking":
                    buffer_data["is_collecting_thinking"] = True
                    buffer_data["thinking_buffer"] = ""
                    # Don't emit anything yet
                elif block_type == "tool_use" or isinstance(
                    event.content_block, ToolUseBlock
                ):
                    buffer_data["tool_name"] = event.content_block.name
                    buffer_data["tool_id"] = event.content_block.id
                    buffer_data["tool_json_buffer"] = ""
                    buffer_data["is_collecting_tool"] = True

        elif isinstance(event, RawContentBlockDeltaEvent):
            delta_obj = getattr(event, "delta", None)
            delta_type = getattr(delta_obj, "type", None)
            
            # Handle thinking deltas
            if delta_type == "thinking_delta" and hasattr(delta_obj, "thinking"):
                thinking_chunk = delta_obj.thinking
                if buffer_data["is_collecting_thinking"]:
                    buffer_data["thinking_buffer"] += thinking_chunk
                    # Stream thinking chunks as they come in
                    chunk = make_base_chunk()
                    chunk["choices"][0]["delta"] = {"thinking": thinking_chunk}
                    chunks.append(chunk)
            
            # Handle signature deltas for thinking blocks
            elif delta_type == "signature_delta" and hasattr(delta_obj, "signature"):
                if buffer_data["is_collecting_thinking"]:
                    buffer_data["thinking_signature"] = delta_obj.signature
                    # No need to emit anything for the signature
            
            # Handle text deltas
            elif delta_type == "text_delta" and hasattr(delta_obj, "text"):
                text_chunk = delta_obj.text
                if not buffer_data["is_collecting_tool"]:
                    if text_chunk:
                        chunk = make_base_chunk()
                        chunk["choices"][0]["delta"] = {"content": text_chunk}
                        chunks.append(chunk)
            
            # Handle partial JSON for tools
            elif hasattr(delta_obj, "partial_json"):
                if buffer_data["is_collecting_tool"]:
                    buffer_data["tool_json_buffer"] += delta_obj.partial_json

        elif isinstance(event, ContentBlockStopEvent):
            # Handle the end of a thinking block
            if buffer_data.get("is_collecting_thinking"):
                # Emit a special "structured_content_delta" with the complete thinking block
                if buffer_data["thinking_buffer"] and buffer_data["thinking_signature"]:
                    chunk = make_base_chunk()
                    chunk["choices"][0]["delta"] = {
                        "structured_content": [{
                            "type": "thinking",
                            "thinking": buffer_data["thinking_buffer"],
                            "signature": buffer_data["thinking_signature"]
                        }]
                    }
                    chunks.append(chunk)
                
                # Reset thinking collection
                buffer_data["is_collecting_thinking"] = False
                buffer_data["thinking_buffer"] = ""
                buffer_data["thinking_signature"] = None
            
            # Handle the end of a tool use block
            elif buffer_data.get("is_collecting_tool"):
                try:
                    json.loads(buffer_data["tool_json_buffer"])
                    chunk = make_base_chunk()
                    chunk["choices"][0]["delta"] = {
                        "tool_calls": [
                            {
                                "index": 0,
                                "type": "function",
                                "id": buffer_data["tool_id"] or f"call_{generate_tool_id()}",
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
                    buffer_data["tool_id"] = None
                except json.JSONDecodeError:
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