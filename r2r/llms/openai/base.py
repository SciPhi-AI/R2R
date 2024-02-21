"""A module for creating OpenAI model abstractions."""
import logging
import os
from dataclasses import dataclass

from openai.types import Completion
from openai.types.chat import ChatCompletion

from r2r.core import GenerationConfig, LLMConfig, LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class OpenAIConfig(LLMConfig):
    """Configuration for OpenAI models."""

    # Base
    provider_name: str = "openai"


class OpenAILLM(LLMProvider):
    """A concrete class for creating OpenAI models."""

    PROMPT_MEASUREMENT_PREFIX = (
        "<DUMMY PADDING, LOOKUP ACTUAL STRUCTUER LATER>"
    )

    def __init__(
        self,
        config: OpenAIConfig,
        *args,
        **kwargs,
    ) -> None:
        logger.info(f"Initializing `OpenAILLM` with config: {config}")
        super().__init__()
        self.config: OpenAIConfig = config

        try:
            from openai import OpenAI  # noqa
        except ImportError:
            raise ImportError(
                "Please install the openai package before attempting to run with an OpenAI model. This can be accomplished via `pip install openai`."
            )
        if config.provider_name != "openai" or not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "OpenAI API key not found. Please set the OPENAI_API_KEY environment variable."
            )
        # set the config here, again, for typing purposes
        if not isinstance(self.config, OpenAIConfig):
            raise ValueError(
                "The provided config must be an instance of OpenAIConfig."
            )
        self.client = OpenAI()

    def get_chat_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> ChatCompletion:
        """Get a completion from the OpenAI API based on the provided messages."""

        # Create a dictionary with the default arguments
        args = self._get_base_args(
            generation_config,
            OpenAILLM.PROMPT_MEASUREMENT_PREFIX
            + f"{OpenAILLM.PROMPT_MEASUREMENT_PREFIX}\n\n".join(
                [m["content"] for m in messages]
            ),
        )

        args["messages"] = messages

        # Conditionally add the 'functions' argument if it's not None
        if generation_config.functions is not None:
            args["functions"] = generation_config.functions

        args = {**args, **kwargs}
        # Create the chat completion
        return self.client.chat.completions.create(**args)

    def get_instruct_completion(
        self,
        prompt: str,
        generation_config: GenerationConfig,
        **kwargs,
    ) -> Completion:
        """Get an instruction completion from the OpenAI API based on the provided prompt."""

        args = self._get_base_args(generation_config, prompt)

        args["prompt"] = prompt

        # Create the instruction completion
        return self.client.completions.create(**args)

    def _get_base_args(
        self,
        generation_config: GenerationConfig,
        prompt=None,
    ) -> dict:
        """Get the base arguments for the OpenAI API."""

        args = {
            "model": generation_config.model_name,
            "temperature": generation_config.temperature,
            "top_p": generation_config.top_p,
            "stream": generation_config.do_stream,
            # TODO - We need to cap this to avoid potential errors when exceed max allowable context
            "max_tokens": generation_config.max_tokens_to_sample,
        }

        return args
