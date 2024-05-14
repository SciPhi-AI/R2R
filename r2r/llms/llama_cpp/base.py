"""A module for creating LlamaCpp model abstractions."""

import datetime
import logging
import os
from typing import Union

from r2r.core import (
    GenerationConfig,
    LLMChatCompletion,
    LLMChatCompletionChunk,
    LLMConfig,
    LLMProvider,
)

logger = logging.getLogger(__name__)


class LlamaCppConfig(LLMConfig):
    """Configuration for LlamaCpp models."""

    # Base
    provider: str = "llama-cpp"
    model: str = ""
    model_path: str = ""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        if not self.model_path or self.model_path == "":
            self.model_path = os.path.join(
                os.path.expanduser("~"), ".cache", "models"
            )
            print('self.model_path = ', self.model_path)
        if not self.model or self.model == "":
            self.model = "tinyllama-1.1b-chat-v1.0.Q2_K.gguf"


class LlamaCPP(LLMProvider):
    """A concrete class for creating LlamaCpp models."""

    def __init__(
        self,
        config: LlamaCppConfig,
        *args,
        **kwargs,
    ) -> None:
        logger.info(f"Initializing `LlamaCPP` with config: {config}")
        if not isinstance(config, LlamaCppConfig):
            raise ValueError(
                "The provided config must be an instance of LlamaCppConfig."
            )
        super().__init__(config)
        self.config: LlamaCppConfig = config

        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError(
                "Error, `llama-cpp-python` is required to run a LlamaCPP. Please install it using `pip install llama-cpp-python`."
            )

        path = os.path.join(self.config.model_path, self.config.model)
        print('path = ', path)
        self.client = Llama(path, n_ctx=2048)

    def get_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> LLMChatCompletion:
        if generation_config.stream:
            raise ValueError(
                "Stream must be set to False to use the `get_completion` method."
            )
        return self._get_completion(messages, generation_config, **kwargs)

    def get_completion_stream(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> LLMChatCompletionChunk:
        if not generation_config.stream:
            raise ValueError(
                "Stream must be set to True to use the `get_completion_stream` method."
            )
        return self._get_completion(messages, generation_config, **kwargs)

    def _get_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> Union[LLMChatCompletion, LLMChatCompletionChunk]:
        """Get a completion from the LlamaCpp model based on the provided messages."""

        args = self._get_base_args(generation_config)

        prompt = "\n".join([msg["content"] for msg in messages])

        response = self.client(prompt, **args)

        if not generation_config.stream:
            return response
        else:
            return LLMChatCompletionChunk(
                choices=[
                    {
                        "message": {
                            "role": "assistant",
                            "content": str(response),
                        },
                        "index": 0,
                        "finish_reason": None,
                    }
                ],
                **kwargs,
            )

    def _get_base_args(
        self,
        generation_config: GenerationConfig,
    ) -> dict:
        """Get the base arguments for the LlamaCpp model."""
        args = {
            "temperature": generation_config.temperature,
            "top_p": generation_config.top_p,
            "max_tokens": generation_config.max_tokens_to_sample,
        }
        return args


    def extract_content(self, response: LLMChatCompletion) -> str:
        return response.choices[0].message.content
