"""A module for creating LlamaCpp model abstractions."""

import datetime
import logging
import os
from dataclasses import dataclass
from typing import Union

from openai.types.chat import ChatCompletion, ChatCompletionChunk

from r2r.core import GenerationConfig, LLMConfig, LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class LlamaCppConfig(LLMConfig):
    """Configuration for LlamaCpp models."""

    # Base
    provider_name: str = "llama-cpp"
    model_path: str = ""
    model_name: str = ""

    def __post_init__(self):
        if not self.model_path or self.model_path == "":
            self.model_path = os.path.join(
                os.path.expanduser("~"), ".cache", "models"
            )
        if not self.model_name or self.model_name == "":
            self.model_name = "tinyllama-1.1b-chat-v1.0.Q2_K.gguf"


class LlamaCPP(LLMProvider):
    """A concrete class for creating LlamaCpp models."""

    def __init__(
        self,
        config: LlamaCppConfig,
        *args,
        **kwargs,
    ) -> None:
        logger.info(f"Initializing `LlamaCPP` with config: {config}")
        super().__init__()

        if not isinstance(config, LlamaCppConfig):
            raise ValueError(
                "The provided config must be an instance of LlamaCppConfig."
            )

        self.config: LlamaCppConfig = config

        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError(
                "Error, `llama-cpp-python` is required to run a LlamaCPP. Please install it using `pip install llama-cpp-python`."
            )

        path = os.path.join(self.config.model_path, self.config.model_name)
        self.client = Llama(path, n_ctx=2048)

    def get_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> ChatCompletion:
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
    ) -> ChatCompletionChunk:
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
    ) -> Union[ChatCompletion, ChatCompletionChunk]:
        """Get a completion from the LlamaCpp model based on the provided messages."""

        args = self._get_base_args(generation_config)

        prompt = "\n".join([msg["content"] for msg in messages])

        response = self.client(prompt, **args)

        if not generation_config.stream:
            return ChatCompletion(
                # TODO - Set an intelligent id
                id="777",
                object="chat.completion",
                created=int(datetime.datetime.now().timestamp()),
                model=generation_config.model,
                choices=[
                    {
                        "message": {
                            "role": "assistant",
                            "content": str(response),
                        },
                        "index": 0,
                        "finish_reason": "stop",
                    }
                ],
            )
        else:
            return ChatCompletionChunk(
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
