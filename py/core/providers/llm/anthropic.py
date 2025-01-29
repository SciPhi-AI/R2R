import logging
import os
import time
from typing import Any

from anthropic import Anthropic, AsyncAnthropic

from core.base.abstractions import GenerationConfig, LLMChatCompletion
from core.base.providers.llm import CompletionConfig, CompletionProvider

logger = logging.getLogger()


class AnthropicCompletionProvider(CompletionProvider):
    def __init__(self, config: CompletionConfig, *args, **kwargs) -> None:
        super().__init__(config)
        if config.provider != "anthropic":
            logger.error(f"Invalid provider: {config.provider}")
            raise ValueError(
                "AnthropicCompletionProvider must be initialized with config with `anthropic` provider."
            )
        if not os.getenv("ANTHROPIC_API_KEY"):
            logger.error("Anthropic API key not found")
            raise ValueError(
                "Anthropic API key not found. Please set the ANTHROPIC_API_KEY environment variable."
            )
        self.async_client = AsyncAnthropic()
        self.client = Anthropic()
        logger.debug("AnthropicCompletionProvider initialized successfully")

    def _get_base_args(self, generation_config: GenerationConfig) -> dict:
        args = {
            "model": generation_config.model,
            "temperature": generation_config.temperature,
            "top_p": generation_config.top_p,
            "stream": generation_config.stream,
            "max_tokens": generation_config.max_tokens_to_sample,
        }
        if generation_config.functions is not None:
            args["functions"] = generation_config.functions
        if generation_config.tools is not None:
            args["tools"] = generation_config.tools
        if generation_config.response_format is not None:
            args["response_format"] = generation_config.response_format
        return args

    def _convert_to_chat_completion(self, anthropic_response) -> dict:
        """
        Convert an Anthropic response into an OpenAI-compatible ChatCompletion.
        """
        content_text = (
            anthropic_response.content[0].text
            if anthropic_response.content
            else ""
        )

        finish_reason = (
            "stop"
            if anthropic_response.stop_reason == "end_turn"
            else anthropic_response.stop_reason
        )

        return {
            "id": anthropic_response.id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": anthropic_response.model,
            "usage": {
                "prompt_tokens": anthropic_response.usage.input_tokens,
                "completion_tokens": anthropic_response.usage.output_tokens,
                "total_tokens": anthropic_response.usage.input_tokens
                + anthropic_response.usage.output_tokens,
            },
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": anthropic_response.role,
                        "content": content_text,
                    },
                    "finish_reason": finish_reason,
                }
            ],
        }

    async def _execute_task(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        system_message = None
        filtered_messages = []
        for message in messages:
            if message["role"] == "system":
                system_message = message["content"]
            else:
                filtered_messages.append(message)

        args = self._get_base_args(generation_config)
        args["messages"] = filtered_messages
        if system_message:
            args["system"] = system_message
        args = {**args, **kwargs}

        logger.debug(f"Executing async Anthropic task with args: {args}")
        try:
            response = await self.async_client.messages.create(**args)
            logger.debug("Async Anthropic task executed successfully")
            return LLMChatCompletion(
                **self._convert_to_chat_completion(response)
            )
        except Exception as e:
            logger.error(f"Failed to execute async Anthropic task: {e}")
            raise e

    def _execute_task_sync(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        system_message = None
        filtered_messages = []
        for message in messages:
            if message["role"] == "system":
                system_message = message["content"]
            else:
                filtered_messages.append(message)

        args = self._get_base_args(generation_config)
        args["messages"] = filtered_messages
        if system_message:
            args["system"] = system_message
        args = {**args, **kwargs}

        logger.debug(f"Executing sync Anthropic task with args: {args}")
        try:
            response = self.client.messages.create(**args)
            logger.debug("Sync Anthropic task executed successfully")
            return LLMChatCompletion(
                **self._convert_to_chat_completion(response)
            )
        except Exception as e:
            logger.error(f"Failed to execute sync Anthropic task: {e}")
            raise e
