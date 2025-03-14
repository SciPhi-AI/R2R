import base64
import io
import logging
import os
from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI, OpenAI

from core.base.abstractions import GenerationConfig
from core.base.providers.llm import CompletionConfig, CompletionProvider

logger = logging.getLogger()

# Try to import PIL for image processing
try:
    from PIL import Image

    PILLOW_AVAILABLE = True
except ImportError:
    logger.warning(
        "PIL/Pillow not installed. Image resizing will be disabled."
    )
    PILLOW_AVAILABLE = False


def resize_base64_image(
    base64_string: str,
    max_size: tuple[int, int] = (512, 512),
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


def estimate_image_tokens(width: int, height: int) -> int:
    """
    Estimate the number of tokens an image will use based on Anthropic's formula.
    This is a rough estimate that can also be used for OpenAI models.

    Args:
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        Estimated number of tokens
    """
    return int((width * height) / 750)


class OpenAICompletionProvider(CompletionProvider):
    def __init__(self, config: CompletionConfig, *args, **kwargs) -> None:
        super().__init__(config)
        self.openai_client = None
        self.async_openai_client = None
        self.azure_client = None
        self.async_azure_client = None
        self.deepseek_client = None
        self.async_deepseek_client = None
        self.ollama_client = None
        self.async_ollama_client = None
        self.lmstudio_client = None
        self.async_lmstudio_client = None
        # NEW: Azure Foundry clients using the Azure Inference API
        self.azure_foundry_client = None
        self.async_azure_foundry_client = None

        # Initialize OpenAI clients if credentials exist
        if os.getenv("OPENAI_API_KEY"):
            self.openai_client = OpenAI()
            self.async_openai_client = AsyncOpenAI()
            logger.debug("OpenAI clients initialized successfully")

        # Initialize Azure OpenAI clients if credentials exist
        azure_api_key = os.getenv("AZURE_API_KEY")
        azure_api_base = os.getenv("AZURE_API_BASE")
        if azure_api_key and azure_api_base:
            self.azure_client = AsyncAzureOpenAI(
                api_key=azure_api_key,
                api_version=os.getenv(
                    "AZURE_API_VERSION", "2024-02-15-preview"
                ),
                azure_endpoint=azure_api_base,
            )
            self.async_azure_client = AsyncAzureOpenAI(
                api_key=azure_api_key,
                api_version=os.getenv(
                    "AZURE_API_VERSION", "2024-02-15-preview"
                ),
                azure_endpoint=azure_api_base,
            )
            logger.debug("Azure OpenAI clients initialized successfully")

        # Initialize Deepseek clients if credentials exist
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        deepseek_api_base = os.getenv(
            "DEEPSEEK_API_BASE", "https://api.deepseek.com"
        )
        if deepseek_api_key and deepseek_api_base:
            self.deepseek_client = OpenAI(
                api_key=deepseek_api_key,
                base_url=deepseek_api_base,
            )
            self.async_deepseek_client = AsyncOpenAI(
                api_key=deepseek_api_key,
                base_url=deepseek_api_base,
            )
            logger.debug("Deepseek OpenAI clients initialized successfully")

        # Initialize Ollama clients with default API key
        ollama_api_base = os.getenv(
            "OLLAMA_API_BASE", "http://localhost:11434/v1"
        )
        if ollama_api_base:
            self.ollama_client = OpenAI(
                api_key=os.getenv("OLLAMA_API_KEY", "dummy"),
                base_url=ollama_api_base,
            )
            self.async_ollama_client = AsyncOpenAI(
                api_key=os.getenv("OLLAMA_API_KEY", "dummy"),
                base_url=ollama_api_base,
            )
            logger.debug("Ollama OpenAI clients initialized successfully")

        # Initialize LMStudio clients
        lmstudio_api_base = os.getenv(
            "LMSTUDIO_API_BASE", "http://localhost:1234/v1"
        )
        if lmstudio_api_base:
            self.lmstudio_client = OpenAI(
                api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio"),
                base_url=lmstudio_api_base,
            )
            self.async_lmstudio_client = AsyncOpenAI(
                api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio"),
                base_url=lmstudio_api_base,
            )
            logger.debug("LMStudio OpenAI clients initialized successfully")

        # Initialize Azure Foundry clients if credentials exist.
        # These use the Azure Inference API (currently pasted into this handler).
        azure_foundry_api_key = os.getenv("AZURE_FOUNDRY_API_KEY")
        azure_foundry_api_endpoint = os.getenv("AZURE_FOUNDRY_API_ENDPOINT")
        if azure_foundry_api_key and azure_foundry_api_endpoint:
            from azure.ai.inference import (
                ChatCompletionsClient as AzureChatCompletionsClient,
            )
            from azure.ai.inference.aio import (
                ChatCompletionsClient as AsyncAzureChatCompletionsClient,
            )
            from azure.core.credentials import AzureKeyCredential

            self.azure_foundry_client = AzureChatCompletionsClient(
                endpoint=azure_foundry_api_endpoint,
                credential=AzureKeyCredential(azure_foundry_api_key),
                api_version=os.getenv(
                    "AZURE_FOUNDRY_API_VERSION", "2024-05-01-preview"
                ),
            )
            self.async_azure_foundry_client = AsyncAzureChatCompletionsClient(
                endpoint=azure_foundry_api_endpoint,
                credential=AzureKeyCredential(azure_foundry_api_key),
                api_version=os.getenv(
                    "AZURE_FOUNDRY_API_VERSION", "2024-05-01-preview"
                ),
            )
            logger.debug("Azure Foundry clients initialized successfully")

        if not any(
            [
                self.openai_client,
                self.azure_client,
                self.ollama_client,
                self.lmstudio_client,
                self.azure_foundry_client,
            ]
        ):
            raise ValueError(
                "No valid client credentials found. Please set either OPENAI_API_KEY, "
                "both AZURE_API_KEY and AZURE_API_BASE environment variables, "
                "OLLAMA_API_BASE, LMSTUDIO_API_BASE, or AZURE_FOUNDRY_API_KEY and AZURE_FOUNDRY_API_ENDPOINT."
            )

    def _get_client_and_model(self, model: str):
        """Determine which client to use based on model prefix and return the
        appropriate client and model name."""
        if model.startswith("azure/"):
            if not self.azure_client:
                raise ValueError(
                    "Azure OpenAI credentials not configured but azure/ model prefix used"
                )
            return self.azure_client, model[6:]  # Strip 'azure/' prefix
        elif model.startswith("openai/"):
            if not self.openai_client:
                raise ValueError(
                    "OpenAI credentials not configured but openai/ model prefix used"
                )
            return self.openai_client, model[7:]  # Strip 'openai/' prefix
        elif model.startswith("deepseek/"):
            if not self.deepseek_client:
                raise ValueError(
                    "Deepseek OpenAI credentials not configured but deepseek/ model prefix used"
                )
            return self.deepseek_client, model[9:]  # Strip 'deepseek/' prefix
        elif model.startswith("ollama/"):
            if not self.ollama_client:
                raise ValueError(
                    "Ollama OpenAI credentials not configured but ollama/ model prefix used"
                )
            return self.ollama_client, model[7:]  # Strip 'ollama/' prefix
        elif model.startswith("lmstudio/"):
            if not self.lmstudio_client:
                raise ValueError(
                    "LMStudio credentials not configured but lmstudio/ model prefix used"
                )
            return self.lmstudio_client, model[9:]  # Strip 'lmstudio/' prefix
        elif model.startswith("azure-foundry/"):
            if not self.azure_foundry_client:
                raise ValueError(
                    "Azure Foundry credentials not configured but azure-foundry/ model prefix used"
                )
            return (
                self.azure_foundry_client,
                model[14:],
            )  # Strip 'azure-foundry/' prefix
        else:
            # Default to OpenAI if no prefix is provided.
            if self.openai_client:
                return self.openai_client, model
            elif self.azure_client:
                return self.azure_client, model
            elif self.ollama_client:
                return self.ollama_client, model
            elif self.lmstudio_client:
                return self.lmstudio_client, model
            elif self.azure_foundry_client:
                return self.azure_foundry_client, model
            else:
                raise ValueError("No valid client available for model prefix")

    def _get_async_client_and_model(self, model: str):
        """Get async client and model name based on prefix."""
        if model.startswith("azure/"):
            if not self.async_azure_client:
                raise ValueError(
                    "Azure OpenAI credentials not configured but azure/ model prefix used"
                )
            return self.async_azure_client, model[6:]
        elif model.startswith("openai/"):
            if not self.async_openai_client:
                raise ValueError(
                    "OpenAI credentials not configured but openai/ model prefix used"
                )
            return self.async_openai_client, model[7:]
        elif model.startswith("deepseek/"):
            if not self.async_deepseek_client:
                raise ValueError(
                    "Deepseek OpenAI credentials not configured but deepseek/ model prefix used"
                )
            return self.async_deepseek_client, model[9:].strip()
        elif model.startswith("ollama/"):
            if not self.async_ollama_client:
                raise ValueError(
                    "Ollama OpenAI credentials not configured but ollama/ model prefix used"
                )
            return self.async_ollama_client, model[7:]
        elif model.startswith("lmstudio/"):
            if not self.async_lmstudio_client:
                raise ValueError(
                    "LMStudio credentials not configured but lmstudio/ model prefix used"
                )
            return self.async_lmstudio_client, model[9:]
        elif model.startswith("azure-foundry/"):
            if not self.async_azure_foundry_client:
                raise ValueError(
                    "Azure Foundry credentials not configured but azure-foundry/ model prefix used"
                )
            return self.async_azure_foundry_client, model[14:]
        else:
            if self.async_openai_client:
                return self.async_openai_client, model
            elif self.async_azure_client:
                return self.async_azure_client, model
            elif self.async_ollama_client:
                return self.async_ollama_client, model
            elif self.async_lmstudio_client:
                return self.async_lmstudio_client, model
            elif self.async_azure_foundry_client:
                return self.async_azure_foundry_client, model
            else:
                raise ValueError(
                    "No valid async client available for model prefix"
                )

    def _process_messages_with_images(
        self, messages: list[dict]
    ) -> list[dict]:
        """
        Process messages that may contain image_url or image_data fields.
        Now includes aggressive image resizing similar to Anthropic provider.
        """
        processed_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                # System messages don't support content arrays in OpenAI
                processed_messages.append(msg)
                continue

            # Check if the message contains image data
            image_url = msg.pop("image_url", None)
            image_data = msg.pop("image_data", None)
            content = msg.get("content")

            if image_url or image_data:
                # Convert to content array format
                new_content = []

                # Add image content
                if image_url:
                    new_content.append(
                        {"type": "image_url", "image_url": {"url": image_url}}
                    )
                elif image_data:
                    # Resize the base64 image data if available
                    media_type = image_data.get("media_type", "image/jpeg")
                    data = image_data.get("data", "")

                    # Apply image resizing if PIL is available
                    if PILLOW_AVAILABLE and data:
                        data = resize_base64_image(data)
                        logger.debug(
                            f"Image resized, new size: {len(data)} chars"
                        )

                    # OpenAI expects base64 images in data URL format
                    data_url = f"data:{media_type};base64,{data}"
                    new_content.append(
                        {"type": "image_url", "image_url": {"url": data_url}}
                    )

                # Add text content if present
                if content:
                    new_content.append({"type": "text", "text": content})

                # Update the message
                new_msg = dict(msg)
                new_msg["content"] = new_content
                processed_messages.append(new_msg)
            else:
                processed_messages.append(msg)

        return processed_messages

    def _process_array_content_with_images(self, content: list) -> list:
        """
        Process content array that may contain image_url items.
        Used for messages that already have content in array format.
        """
        if not content or not isinstance(content, list):
            return content

        processed_content = []

        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "image_url":
                    # Process image URL if needed
                    processed_content.append(item)
                elif item.get("type") == "image" and item.get("source"):
                    # Convert Anthropic-style to OpenAI-style
                    source = item.get("source", {})
                    if source.get("type") == "base64" and source.get("data"):
                        # Resize the base64 image data
                        if PILLOW_AVAILABLE:
                            resized_data = resize_base64_image(
                                source.get("data")
                            )
                        else:
                            resized_data = source.get("data")

                        media_type = source.get("media_type", "image/jpeg")
                        data_url = f"data:{media_type};base64,{resized_data}"

                        processed_content.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            }
                        )
                    elif source.get("type") == "url" and source.get("url"):
                        processed_content.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": source.get("url")},
                            }
                        )
                else:
                    # Pass through other types
                    processed_content.append(item)
            else:
                processed_content.append(item)

        return processed_content

    def _preprocess_messages(self, messages: list[dict]) -> list[dict]:
        """
        Preprocess all messages to optimize images before sending to OpenAI API.
        """
        if not messages or not isinstance(messages, list):
            return messages

        processed_messages = []

        for msg in messages:
            # Skip system messages as they're handled separately
            if msg.get("role") == "system":
                processed_messages.append(msg)
                continue

            # Process array-format content (might contain images)
            if isinstance(msg.get("content"), list):
                new_msg = dict(msg)
                new_msg["content"] = self._process_array_content_with_images(
                    msg["content"]
                )
                processed_messages.append(new_msg)
            else:
                # Standard processing for non-array content
                processed_messages.append(msg)

        return processed_messages

    def _get_base_args(self, generation_config: GenerationConfig) -> dict:
        # Keep existing implementation...
        args: dict[str, Any] = {
            "model": generation_config.model,
            "stream": generation_config.stream,
        }

        model_str = generation_config.model or ""

        if "o1" not in model_str and "o3" not in model_str:
            args["max_tokens"] = generation_config.max_tokens_to_sample
            args["temperature"] = generation_config.temperature
            args["top_p"] = generation_config.top_p
        else:
            args["max_completion_tokens"] = (
                generation_config.max_tokens_to_sample
            )

        if generation_config.reasoning_effort is not None:
            args["reasoning_effort"] = generation_config.reasoning_effort
        if generation_config.functions is not None:
            args["functions"] = generation_config.functions
        if generation_config.tools is not None:
            args["tools"] = generation_config.tools
        if generation_config.response_format is not None:
            args["response_format"] = generation_config.response_format
        return args

    async def _execute_task(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        # First preprocess to handle any images in array format
        messages = self._preprocess_messages(messages)

        # Then process messages with direct image_url or image_data fields
        processed_messages = self._process_messages_with_images(messages)

        args = self._get_base_args(generation_config)
        client, model_name = self._get_async_client_and_model(args["model"])
        args["model"] = model_name
        args["messages"] = processed_messages
        args = {**args, **kwargs}

        # Check if we're using a vision-capable model when images are present
        contains_images = any(
            isinstance(msg.get("content"), list)
            and any(
                item.get("type") == "image_url"
                for item in msg.get("content", [])
            )
            for msg in processed_messages
        )

        if contains_images:
            vision_models = ["gpt-4-vision", "gpt-4o"]
            if not any(
                vision_model in model_name for vision_model in vision_models
            ):
                logger.warning(
                    f"Using model {model_name} with images, but it may not support vision"
                )

        logger.debug(f"Executing async task with args: {args}")
        try:
            # Same as before...
            if client == self.async_azure_foundry_client:
                model_value = args.pop(
                    "model"
                )  # Remove model before passing args
                response = await client.complete(**args)
            else:
                response = await client.chat.completions.create(**args)
            logger.debug("Async task executed successfully")
            return response
        except Exception as e:
            logger.error(f"Async task execution failed: {str(e)}")
            # HACK: print the exception to the console for debugging
            raise

    def _execute_task_sync(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        # First preprocess to handle any images in array format
        messages = self._preprocess_messages(messages)

        # Then process messages with direct image_url or image_data fields
        processed_messages = self._process_messages_with_images(messages)

        args = self._get_base_args(generation_config)
        client, model_name = self._get_client_and_model(args["model"])
        args["model"] = model_name
        args["messages"] = processed_messages
        args = {**args, **kwargs}

        # Same vision model check as in async version
        contains_images = any(
            isinstance(msg.get("content"), list)
            and any(
                item.get("type") == "image_url"
                for item in msg.get("content", [])
            )
            for msg in processed_messages
        )

        if contains_images:
            vision_models = ["gpt-4-vision", "gpt-4o"]
            if not any(
                vision_model in model_name for vision_model in vision_models
            ):
                logger.warning(
                    f"Using model {model_name} with images, but it may not support vision"
                )

        logger.debug(f"Executing sync OpenAI task with args: {args}")
        try:
            # Same as before...
            if client == self.azure_foundry_client:
                args.pop("model")
                response = client.complete(**args)
            else:
                response = client.chat.completions.create(**args)
            logger.debug("Sync task executed successfully")
            return response
        except Exception as e:
            logger.error(f"Sync task execution failed: {str(e)}")
            raise
