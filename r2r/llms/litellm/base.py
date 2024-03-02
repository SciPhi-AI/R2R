import logging
from dataclasses import dataclass
from typing import Any, Generator, Union

from openai.types import Completion
from openai.types.chat import ChatCompletion

from r2r.core import GenerationConfig, LLMConfig, LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class LiteLLMConfig(LLMConfig):
    """Configuration for LiteLLM models."""

    provider_name: str = "litellm"


class LiteLLM(LLMProvider):
    """A concrete class for creating LiteLLM models."""

    def __init__(
        self,
        config: LiteLLMConfig,
        *args,
        **kwargs,
    ) -> None:
        logger.info(f"Initializing `LiteLLM` with config: {config}")
        super().__init__()
        if not isinstance(config, LiteLLMConfig):
            raise ValueError(
                "The provided config must be an instance of LiteLLMConfig."
            )
        self.config: LiteLLMConfig = config

    def get_chat_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> Union[Generator[str, None, None], ChatCompletion]:
        """Get a completion from the LiteLLM based on the provided messages and generation config."""
        try:
            from litellm import completion
        except ImportError:
            raise ImportError(
                "Error, `litellm` is required to run a LiteLLM. Please install it using `pip install litellm`."
            )
        # Create a dictionary with the default arguments
        args = self._get_base_args(generation_config)

        args["messages"] = messages

        # Conditionally add the 'functions' argument if it's not None
        if generation_config.functions is not None:
            args["functions"] = generation_config.functions

        args = {**args, **kwargs}

        response = completion(**args)
        if not generation_config.stream:
            return ChatCompletion(**response.dict())
        else:
            return self._get_chat_completion(response)

    # TODO - Find the correct return type for this
    def _get_chat_completion(
        self, response: Any
    ) -> Generator[str, None, None]:
        for part in response:
            yield part

    def get_instruct_completion(
        self,
        prompt: str,
        generation_config: GenerationConfig,
        **kwargs,
    ) -> Union[Generator[str, None, None], Completion]:
        """Get an instruction completion from the LiteLLM based on the provided prompt and generation config."""
        try:
            from litellm import completion
        except ImportError:
            raise ImportError(
                "Error, `litellm` is required to run a LiteLLM. Please install it using `pip install litellm`."
            )
        args = self._get_base_args(generation_config)

        args["prompt"] = prompt

        response = completion(**args)
        if not generation_config.stream:
            return Completion(**response.dict())
        else:
            return self._get_instruct_completion(response)

    # TODO - Find the correct return type for this
    def _get_instruct_completion(
        self, response: Any
    ) -> Generator[str, None, None]:
        for part in response:
            yield part

    def _get_base_args(
        self,
        generation_config: GenerationConfig,
        prompt=None,
    ) -> dict:
        """Get the base arguments for the OpenAI API."""

        args = {
            "model": generation_config.model,
            "temperature": generation_config.temperature,
            "top_p": generation_config.top_p,
            "stream": generation_config.stream,
            # TODO - We need to cap this to avoid potential errors when exceed max allowable context
            "max_tokens": generation_config.max_tokens_to_sample,
        }

        return args
