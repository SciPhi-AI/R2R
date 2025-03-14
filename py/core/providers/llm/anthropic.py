import base64
import copy
import io
import json
import logging
import os
import time
import uuid
from typing import (
    Any,
    AsyncGenerator,
    Generator,
    Optional,
    Tuple,
)

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import (
    ContentBlockStopEvent,
    Message,
    MessageStopEvent,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawMessageStartEvent,
    ToolUseBlock,
)

from core.base.abstractions import GenerationConfig, LLMChatCompletion
from core.base.providers.llm import CompletionConfig, CompletionProvider

logger = logging.getLogger(__name__)

# Try to import PIL for image processing
try:
    from PIL import Image

    PILLOW_AVAILABLE = True
except ImportError:
    logger.warning(
        "PIL/Pillow not installed. Image resizing will be disabled."
    )
    PILLOW_AVAILABLE = False


def generate_tool_id() -> str:
    """Generate a unique tool ID using UUID4."""
    return f"tool_{uuid.uuid4().hex[:12]}"


def estimate_image_tokens(width: int, height: int) -> int:
    """
    Estimate the number of tokens an image will use based on Anthropic's formula.

    Args:
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Estimated number of tokens
    """
    return int((width * height) / 750)


def resize_base64_image(
    base64_string: str,
    max_size: Tuple[int, int] = (512, 512),
    max_megapixels: float = 0.25,
) -> str:
    """Aggressively resize images with better error handling and debug output"""
    logger.debug(
        f"RESIZING NOW!!! Original length: {len(base64_string)} chars"
    )

    if not PILLOW_AVAILABLE:
        logger.warning("PIL/Pillow not available, skipping image resize")
        return base64_string[
            :50000
        ]  # Emergency truncation if PIL not available

    # Decode base64 string to bytes
    try:
        image_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_data))
        logger.debug(f"Image opened successfully: {image.format} {image.size}")
    except Exception as e:
        logger.debug(f"Failed to decode/open image: {e}")
        # Emergency fallback - truncate the base64 string to reduce tokens
        if len(base64_string) > 50000:
            return base64_string[:50000]
        return base64_string

    try:
        width, height = image.size
        current_megapixels = (width * height) / 1_000_000
        logger.debug(
            f"Original dimensions: {width}x{height} ({current_megapixels:.2f} MP)"
        )

        # MUCH more aggressive resizing for large images
        if current_megapixels > 0.5:
            max_size = (384, 384)
            max_megapixels = 0.15
            logger.debug("Large image detected! Using more aggressive limits")

        # Calculate new dimensions with strict enforcement
        # Always resize if the image is larger than we want
        scale_factor = min(
            max_size[0] / width,
            max_size[1] / height,
            (max_megapixels / current_megapixels) ** 0.5,
        )

        if scale_factor >= 1.0:
            # No resize needed, but still compress
            new_width, new_height = width, height
        else:
            # Apply scaling
            new_width = max(int(width * scale_factor), 64)  # Min width
            new_height = max(int(height * scale_factor), 64)  # Min height

        # Always resize/recompress the image
        logger.debug(f"Resizing to: {new_width}x{new_height}")
        resized_image = image.resize((new_width, new_height), Image.LANCZOS)  # type: ignore

        # Convert back to base64 with strong compression
        buffer = io.BytesIO()
        if image.format == "JPEG" or image.format is None:
            # Apply very aggressive JPEG compression
            quality = 50  # Very low quality to reduce size
            resized_image.save(
                buffer, format="JPEG", quality=quality, optimize=True
            )
        else:
            # For other formats
            resized_image.save(
                buffer, format=image.format or "PNG", optimize=True
            )

        resized_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        logger.debug(
            f"Resized base64 length: {len(resized_base64)} chars (reduction: {100 * (1 - len(resized_base64) / len(base64_string)):.1f}%)"
        )
        return resized_base64

    except Exception as e:
        logger.debug(f"Error during resize: {e}")
        # If anything goes wrong, truncate the base64 to a reasonable size
        if len(base64_string) > 50000:
            return base64_string[:50000]
        return base64_string


def process_images_in_message(message: dict) -> dict:
    """
    Process all images in a message to ensure they're within Anthropic's recommended limits.
    """
    if not message or not isinstance(message, dict):
        return message

    # Handle nested image_data (old format)
    if (
        message.get("role")
        and message.get("image_data")
        and isinstance(message["image_data"], dict)
    ):
        if message["image_data"].get("data") and message["image_data"].get(
            "media_type"
        ):
            message["image_data"]["data"] = resize_base64_image(
                message["image_data"]["data"]
            )
        return message

    # Handle standard content list format
    if message.get("content") and isinstance(message["content"], list):
        for i, block in enumerate(message["content"]):
            if isinstance(block, dict) and block.get("type") == "image":
                if block.get("source", {}).get("type") == "base64" and block[
                    "source"
                ].get("data"):
                    message["content"][i]["source"]["data"] = (
                        resize_base64_image(block["source"]["data"])
                    )

    # Handle string content with base64 image detection (less common)
    elif (
        message.get("content")
        and isinstance(message["content"], str)
        and ";base64," in message["content"]
    ):
        # This is a basic detection for base64 images in text - might need more robust handling
        logger.warning(
            "Detected potential base64 image in string content - not auto-resizing"
        )

    return message


def openai_message_to_anthropic_block(msg: dict) -> dict:
    """Converts a single OpenAI-style message (including function/tool calls)
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
    tool_call_id = msg.get("tool_call_id")

    # Handle old-style image_data field
    image_data = msg.get("image_data")
    # Handle nested image_url (less common)
    image_url = msg.get("image_url")

    if role == "system":
        # System messages should not have images, extract any image to a separate user message
        if image_url or image_data:
            logger.warning(
                "Found image in system message - images should be in user messages only"
            )
        return msg

    if role in ["user", "assistant"]:
        # If content is already a list, assume it's properly formatted
        if isinstance(content, list):
            return {"role": role, "content": content}

        # Process old-style image_data or image_url
        if image_url or image_data:
            formatted_content = []

            # Add image content first (as recommended by Anthropic)
            if image_url:
                formatted_content.append(
                    {
                        "type": "image",
                        "source": {"type": "url", "url": image_url},
                    }
                )
            elif image_data:
                # Resize the image data if needed
                resized_data = image_data.get("data", "")
                if PILLOW_AVAILABLE and resized_data:
                    resized_data = resize_base64_image(resized_data)

                formatted_content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_data.get(
                                "media_type", "image/jpeg"
                            ),
                            "data": resized_data,
                        },
                    }
                )

            # Add text content after the image
            if content:
                if isinstance(content, str):
                    formatted_content.append({"type": "text", "text": content})
                elif isinstance(content, list):
                    # If it's already a list, extend with it
                    formatted_content.extend(content)

            return {"role": role, "content": formatted_content}

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

    # Default case - just return with string content
    if isinstance(content, str):
        return {"role": role, "content": content}
    return {"role": role, "content": content}


class AnthropicCompletionProvider(CompletionProvider):
    def __init__(self, config: CompletionConfig, *args, **kwargs) -> None:
        super().__init__(config)
        self.client = Anthropic()  # Synchronous client
        self.async_client = AsyncAnthropic()  # Asynchronous client
        logger.debug("AnthropicCompletionProvider initialized successfully")

    def _get_base_args(
        self, generation_config: GenerationConfig
    ) -> dict[str, Any]:
        """Build the arguments dictionary for Anthropic's messages.create().

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
        model_str = generation_config.model or ""
        model_name = (
            model_str.split("anthropic/")[-1]
            if model_str
            else "claude-3-opus-20240229"
        )

        args: dict[str, Any] = {
            "model": model_name,
            "temperature": generation_config.temperature,
            "max_tokens": generation_config.max_tokens_to_sample,
            "stream": generation_config.stream,
        }
        if generation_config.top_p:
            args["top_p"] = generation_config.top_p

        if generation_config.tools is not None:
            # Convert tools to Anthropic's format
            anthropic_tools: list[dict[str, Any]] = []
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
                    args["tool_choice"]["disable_parallel_tool_use"] = (
                        generation_config.disable_parallel_tool_use
                    )

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
        # elif generation_config.model == "anthropic/claude-3-7-sonnet-20250219":
        #     logger.warning("Claude 3.7 selected without extended thinking enabled. Enabling extended thinking with default budget of 2048 tokens.")
        #     generation_config.extended_thinking = True
        #     args["thinking"] = {
        #         "type": "enabled",
        #         "budget_tokens": 2048,
        #     }
        # -----------------------------------
        return args

    def _preprocess_messages(self, messages: list[dict]) -> list[dict]:
        """
        Preprocess all messages to optimize images before sending to Anthropic API.
        """
        if not messages or not isinstance(messages, list):
            return messages

        processed_messages = []
        for message in messages:
            processed_message = process_images_in_message(message)
            processed_messages.append(processed_message)

        return processed_messages

    def _create_openai_style_message(self, content_blocks, tool_calls=None):
        """
        Create an OpenAI-style message from Anthropic content blocks
        while preserving the original structure.
        """
        display_content = ""
        structured_content: list[Any] = []

        for block in content_blocks:
            if block.type == "text":
                display_content += block.text
            elif block.type == "thinking" and hasattr(block, "thinking"):
                # Store the complete thinking block
                structured_content.append(
                    {
                        "type": "thinking",
                        "thinking": block.thinking,
                        "signature": block.signature,
                    }
                )
                # For display/logging
                # display_content += f"<think>{block.thinking}</think>"
            elif block.type == "redacted_thinking" and hasattr(block, "data"):
                # Store the complete redacted thinking block
                structured_content.append(
                    {"type": "redacted_thinking", "data": block.data}
                )
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
                    structured_content.append(
                        {"type": "text", "text": block.text}
                    )

            return {
                "content": display_content or None,
                "structured_content": structured_content,
            }
        else:
            # If no structured content, just return the display content
            return {"content": display_content or None}

    def _convert_to_chat_completion(self, anthropic_msg: Message) -> dict:
        """
        Convert a non-streaming Anthropic Message into an OpenAI-style dict.
        Preserves thinking blocks for proper handling.
        """
        tool_calls: list[Any] = []
        message_data: dict[str, Any] = {"role": anthropic_msg.role}

        if anthropic_msg.content:
            # First, extract any tool use blocks
            for block in anthropic_msg.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_calls.append(
                        {
                            "index": len(tool_calls),
                            "id": block.id,
                            "type": "function",
                            "function": {
                                "name": block.name,
                                "arguments": json.dumps(block.input),
                            },
                        }
                    )

            # Then create the message with appropriate content
            message_data.update(
                self._create_openai_style_message(
                    anthropic_msg.content, tool_calls
                )
            )

            # If we have tool calls, add them
            if tool_calls:
                message_data["tool_calls"] = tool_calls

        finish_reason = (
            "stop"
            if anthropic_msg.stop_reason == "end_turn"
            else anthropic_msg.stop_reason
        )
        finish_reason = (
            "tool_calls"
            if anthropic_msg.stop_reason == "tool_use"
            else finish_reason
        )

        model_str = anthropic_msg.model or ""
        model_name = model_str.split("anthropic/")[-1] if model_str else ""

        return {
            "id": anthropic_msg.id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
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
    ) -> tuple[list[dict], Optional[str]]:
        """
        Process messages for Anthropic API, ensuring proper format for tool use and thinking blocks.
        Now with image optimization.
        """
        # First preprocess to resize any images
        messages = self._preprocess_messages(messages)

        system_msg = None
        filtered: list[dict[str, Any]] = []
        pending_tool_results: list[dict[str, Any]] = []

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
            if (
                isinstance(m.get("content"), list)
                and len(m["content"]) > 0
                and isinstance(m["content"][0], dict)
            ):
                filtered.append({"role": m["role"], "content": m["content"]})
                i += 1
                continue

            # Case 2: Message with structured_content field
            elif m.get("structured_content") and m["role"] == "assistant":
                filtered.append(
                    {"role": "assistant", "content": m["structured_content"]}
                )
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
                        if (
                            thinking_start >= 0
                            and thinking_end > thinking_start
                        ):
                            thinking_content = content_to_add[
                                thinking_start + 7 : thinking_end
                            ]
                            text_content = content_to_add[
                                thinking_end + 8 :
                            ].strip()
                            filtered.append(
                                {
                                    "role": "assistant",
                                    "content": [
                                        {
                                            "type": "thinking",
                                            "thinking": thinking_content,
                                            "signature": "placeholder_signature",  # This is a placeholder
                                        },
                                        {"type": "text", "text": text_content},
                                    ],
                                }
                            )
                        else:
                            filtered.append(
                                {
                                    "role": "assistant",
                                    "content": content_to_add,
                                }
                            )
                    else:
                        filtered.append(
                            {"role": "assistant", "content": content_to_add}
                        )

                # Add tool use blocks
                tool_uses = []
                for call in m["tool_calls"]:
                    tool_uses.append(
                        {
                            "type": "tool_use",
                            "id": call["id"],
                            "name": call["function"]["name"],
                            "input": json.loads(call["function"]["arguments"]),
                        }
                    )

                filtered.append({"role": "assistant", "content": tool_uses})

                # Check if next message is a tool result for this tool call
                if i + 1 < len(messages) and messages[i + 1]["role"] in [
                    "function",
                    "tool",
                ]:
                    next_m = copy.deepcopy(messages[i + 1])

                    # Make sure this is a tool result for the current tool use
                    if next_m.get("tool_call_id") in [
                        call["id"] for call in m["tool_calls"]
                    ]:
                        # Add tool result as a user message
                        filtered.append(
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "tool_result",
                                        "tool_use_id": next_m["tool_call_id"],
                                        "content": next_m["content"],
                                    }
                                ],
                            }
                        )
                        i += 2  # Skip both the tool call and result
                        continue

                i += 1
                continue

            # Case 4: Direct tool result (might be missing its paired tool call)
            elif m["role"] in ["function", "tool"] and m.get("tool_call_id"):
                # Add a user message with the tool result
                filtered.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m["tool_call_id"],
                                "content": m["content"],
                            }
                        ],
                    }
                )
                i += 1
                continue

            # Default case: normal message
            elif m["role"] in ["function", "tool"]:
                # Collect tool results to combine them
                pending_tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": m.get("tool_call_id"),
                        "content": m["content"],
                    }
                )

                # If we have all expected results, add them as one message
                if len(filtered) > 0 and len(
                    filtered[-1].get("content", [])
                ) == len(pending_tool_results):
                    filtered.append(
                        {"role": "user", "content": pending_tool_results}
                    )
                    pending_tool_results = []
            else:
                filtered.append(openai_message_to_anthropic_block(m))
                i += 1

        # Final validation: ensure no tool_use is at the end without a tool_result
        if filtered and len(filtered) > 1:
            last_msg = filtered[-1]
            if (
                last_msg["role"] == "assistant"
                and isinstance(last_msg.get("content"), list)
                and any(
                    block.get("type") == "tool_use"
                    for block in last_msg["content"]
                )
            ):
                logger.warning(
                    "Found tool_use at end of conversation without tool_result - removing it"
                )
                filtered.pop()  # Remove problematic message

        return filtered, system_msg

    async def _execute_task(self, task: dict[str, Any]):
        """Async entry point.

        Decide if streaming or not, then call the appropriate helper.
        """
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
        self, args: dict[str, Any]
    ) -> LLMChatCompletion:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("Missing ANTHROPIC_API_KEY in environment.")
            raise ValueError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY env var."
            )

        try:
            logger.debug(f"Anthropic API request: {args}")
            response = await self.async_client.messages.create(**args)
            logger.debug(f"Anthropic API response: {response}")

            return LLMChatCompletion(
                **self._convert_to_chat_completion(response)
            )
        except Exception as e:
            logger.error(f"Anthropic async non-stream call failed: {e}")
            logger.error("message payload = ", args)
            raise

    async def _execute_task_async_streaming(
        self, args: dict
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Streaming call (async): yields partial tokens in OpenAI-like SSE
        format."""
        # The `stream=True` is typically handled by Anthropics from the original args,
        # but we remove it to avoid conflicts and rely on `messages.stream()`.
        args.pop("stream", None)
        try:
            async with self.async_client.messages.stream(**args) as stream:
                # We'll track partial JSON for function calls in buffer_data
                buffer_data: dict[str, Any] = {
                    "tool_json_buffer": "",
                    "tool_name": None,
                    "tool_id": None,
                    "is_collecting_tool": False,
                    "thinking_buffer": "",
                    "is_collecting_thinking": False,
                    "thinking_signature": None,
                    "message_id": f"chatcmpl-{int(time.time())}",
                }
                model_name = args.get("model", "claude-2")
                if isinstance(model_name, str):
                    model_name = model_name.split("anthropic/")[-1]

                async for event in stream:
                    chunks = self._process_stream_event(
                        event=event,
                        buffer_data=buffer_data,
                        model_name=model_name,
                    )
                    for chunk in chunks:
                        yield chunk
        except Exception as e:
            logger.error(f"Failed to execute streaming Anthropic task: {e}")
            logger.error("message payload = ", args)

            raise

    def _execute_task_sync(self, task: dict[str, Any]):
        """Synchronous entry point."""
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

    def _execute_task_sync_nonstreaming(
        self, args: dict[str, Any]
    ) -> LLMChatCompletion:
        """Non-streaming synchronous call."""
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
        self, args: dict[str, Any]
    ) -> Generator[dict[str, Any], None, None]:
        """
        Synchronous streaming call: yields partial tokens in a generator.
        """
        args.pop("stream", None)
        try:
            with self.client.messages.stream(**args) as stream:
                buffer_data: dict[str, Any] = {
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
                if isinstance(model_name, str):
                    model_name = model_name.split("anthropic/")[-1]

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
        self, event: Any, buffer_data: dict[str, Any], model_name: str
    ) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []

        def make_base_chunk() -> dict[str, Any]:
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
                    buffer_data["tool_name"] = event.content_block.name  # type: ignore
                    buffer_data["tool_id"] = event.content_block.id  # type: ignore
                    buffer_data["tool_json_buffer"] = ""
                    buffer_data["is_collecting_tool"] = True

        elif isinstance(event, RawContentBlockDeltaEvent):
            delta_obj = getattr(event, "delta", None)
            delta_type = getattr(delta_obj, "type", None)

            # Handle thinking deltas
            if delta_type == "thinking_delta" and hasattr(
                delta_obj, "thinking"
            ):
                thinking_chunk = delta_obj.thinking  # type: ignore
                if buffer_data["is_collecting_thinking"]:
                    buffer_data["thinking_buffer"] += thinking_chunk
                    # Stream thinking chunks as they come in
                    chunk = make_base_chunk()
                    chunk["choices"][0]["delta"] = {"thinking": thinking_chunk}
                    chunks.append(chunk)

            # Handle signature deltas for thinking blocks
            elif delta_type == "signature_delta" and hasattr(
                delta_obj, "signature"
            ):
                if buffer_data["is_collecting_thinking"]:
                    buffer_data["thinking_signature"] = delta_obj.signature  # type: ignore
                    # No need to emit anything for the signature
                    chunk = make_base_chunk()
                    chunk["choices"][0]["delta"] = {
                        "thinking_signature": delta_obj.signature  # type: ignore
                    }
                    chunks.append(chunk)

            # Handle text deltas
            elif delta_type == "text_delta" and hasattr(delta_obj, "text"):
                text_chunk = delta_obj.text  # type: ignore
                if not buffer_data["is_collecting_tool"]:
                    if text_chunk:
                        chunk = make_base_chunk()
                        chunk["choices"][0]["delta"] = {"content": text_chunk}
                        chunks.append(chunk)

            # Handle partial JSON for tools
            elif hasattr(delta_obj, "partial_json"):
                if buffer_data["is_collecting_tool"]:
                    buffer_data["tool_json_buffer"] += delta_obj.partial_json  # type: ignore

        elif isinstance(event, ContentBlockStopEvent):
            # Handle the end of a thinking block
            if buffer_data.get("is_collecting_thinking"):
                # Emit a special "structured_content_delta" with the complete thinking block
                if (
                    buffer_data["thinking_buffer"]
                    and buffer_data["thinking_signature"]
                ):
                    chunk = make_base_chunk()
                    chunk["choices"][0]["delta"] = {
                        "structured_content": [
                            {
                                "type": "thinking",
                                "thinking": buffer_data["thinking_buffer"],
                                "signature": buffer_data["thinking_signature"],
                            }
                        ]
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
                                "id": buffer_data["tool_id"]
                                or f"call_{generate_tool_id()}",
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
                    buffer_data["is_collecting_tool"] = False
                    buffer_data["tool_json_buffer"] = ""
                    buffer_data["tool_name"] = None
                    buffer_data["tool_id"] = None
                except json.JSONDecodeError:
                    logger.warning(
                        "Incomplete JSON in tool call, skipping chunk"
                    )

        elif isinstance(event, MessageStopEvent):
            # Check if the event has a message attribute before accessing it
            stop_reason = getattr(event, "message", None)
            if stop_reason and hasattr(stop_reason, "stop_reason"):
                stop_reason = stop_reason.stop_reason
                chunk = make_base_chunk()
                if stop_reason == "tool_use":
                    chunk["choices"][0]["delta"] = {}
                    chunk["choices"][0]["finish_reason"] = "tool_calls"
                else:
                    chunk["choices"][0]["delta"] = {}
                    chunk["choices"][0]["finish_reason"] = "stop"
                chunks.append(chunk)
            else:
                # Handle the case where message is not available
                chunk = make_base_chunk()
                chunk["choices"][0]["delta"] = {}
                chunk["choices"][0]["finish_reason"] = "stop"
                chunks.append(chunk)

        return chunks
