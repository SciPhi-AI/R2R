import logging
from typing import Any, Generator, Union

from r2r.base import (
    LLMChatCompletion,
    LLMChatCompletionChunk,
    LLMConfig,
    LLMProvider,
)
from r2r.base.abstractions.llm import GenerationConfig

logger = logging.getLogger(__name__)


class LiteLLM(LLMProvider):
    """A concrete class for creating LiteLLM models."""

    def __init__(
        self,
        config: LLMConfig,
        *args,
        **kwargs,
    ) -> None:
        try:
            from litellm import acompletion, completion

            self.litellm_completion = completion
            self.litellm_acompletion = acompletion
        except ImportError:
            raise ImportError(
                "Error, `litellm` is required to run a LiteLLM. Please install it using `pip install litellm`."
            )
        super().__init__(config)

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
    ) -> Generator[LLMChatCompletionChunk, None, None]:
        if not generation_config.stream:
            raise ValueError(
                "Stream must be set to True to use the `get_completion_stream` method."
            )
        return self._get_completion(messages, generation_config, **kwargs)

    def extract_content(self, response: LLMChatCompletion) -> str:
        return response.choices[0].message.content

    def _get_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> Union[
        LLMChatCompletion, Generator[LLMChatCompletionChunk, None, None]
    ]:
        # Create a dictionary with the default arguments
        args = self._get_base_args(generation_config)
        args["messages"] = messages

        # Conditionally add the 'functions' argument if it's not None
        if generation_config.functions is not None:
            args["functions"] = generation_config.functions

        args = {**args, **kwargs}
        response = self.litellm_completion(**args)

        if not generation_config.stream:
            return LLMChatCompletion(**response.dict())
        else:
            return self._get_chat_completion(response)

    def _get_chat_completion(
        self,
        response: Any,
    ) -> Generator[LLMChatCompletionChunk, None, None]:
        for part in response:
            yield LLMChatCompletionChunk(**part.dict())

    def _get_base_args(
        self,
        generation_config: GenerationConfig,
        prompt=None,
    ) -> dict:
        """Get the base arguments for the LiteLLM API."""
        args = {
            "model": generation_config.model,
            "temperature": generation_config.temperature,
            "top_p": generation_config.top_p,
            "stream": generation_config.stream,
            # TODO - We need to cap this to avoid potential errors when exceed max allowable context
            "max_tokens": generation_config.max_tokens_to_sample,
        }
        return args

    async def aget_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> LLMChatCompletion:
        if generation_config.stream:
            raise ValueError(
                "Stream must be set to False to use the `aget_completion` method."
            )
        return await self._aget_completion(
            messages, generation_config, **kwargs
        )

    async def _aget_completion(
        self,
        messages: list[dict],
        generation_config: GenerationConfig,
        **kwargs,
    ) -> Union[LLMChatCompletion, LLMChatCompletionChunk]:
        """Asynchronously get a completion from the OpenAI API based on the provided messages."""

        # Create a dictionary with the default arguments
        args = self._get_base_args(generation_config)

        args["messages"] = messages

        # Conditionally add the 'functions' argument if it's not None
        if generation_config.functions is not None:
            args["functions"] = generation_config.functions

        args = {**args, **kwargs}
        # Create the chat completion
        return await self.litellm_acompletion(**args)
