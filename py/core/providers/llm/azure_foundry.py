import logging
import os
from typing import Any, Optional

from azure.ai.inference import (
    ChatCompletionsClient as AzureChatCompletionsClient,
)
from azure.ai.inference.aio import (
    ChatCompletionsClient as AsyncAzureChatCompletionsClient,
)
from azure.core.credentials import AzureKeyCredential

from core.base.abstractions import GenerationConfig
from core.base.providers.llm import CompletionConfig, CompletionProvider

logger = logging.getLogger(__name__)


class AzureFoundryCompletionProvider(CompletionProvider):
    def __init__(self, config: CompletionConfig, *args, **kwargs) -> None:
        super().__init__(config)
        self.azure_foundry_client: Optional[AzureChatCompletionsClient] = None
        self.async_azure_foundry_client: Optional[
            AsyncAzureChatCompletionsClient
        ] = None

        # Initialize Azure Foundry clients if credentials exist.
        azure_foundry_api_key = os.getenv("AZURE_FOUNDRY_API_KEY")
        azure_foundry_api_endpoint = os.getenv("AZURE_FOUNDRY_API_ENDPOINT")

        if azure_foundry_api_key and azure_foundry_api_endpoint:
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

    def _get_base_args(
        self, generation_config: GenerationConfig
    ) -> dict[str, Any]:
        # Construct arguments similar to the other providers.
        args: dict[str, Any] = {
            "top_p": generation_config.top_p,
            "stream": generation_config.stream,
            "max_tokens": generation_config.max_tokens_to_sample,
            "temperature": generation_config.temperature,
        }

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

        args = self._get_base_args(generation_config)
        # Azure Foundry does not require a "model" argument; the endpoint is fixed.
        args["messages"] = messages
        args = {**args, **kwargs}
        logger.debug(f"Executing async Azure Foundry task with args: {args}")

        try:
            if self.async_azure_foundry_client is None:
                raise ValueError("Azure Foundry client is not initialized")

            response = await self.async_azure_foundry_client.complete(**args)
            logger.debug("Async Azure Foundry task executed successfully")
            return response
        except Exception as e:
            logger.error(
                f"Async Azure Foundry task execution failed: {str(e)}"
            )
            raise

    def _execute_task_sync(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        args = self._get_base_args(generation_config)
        args["messages"] = messages
        args = {**args, **kwargs}
        logger.debug(f"Executing sync Azure Foundry task with args: {args}")

        try:
            if self.azure_foundry_client is None:
                raise ValueError("Azure Foundry client is not initialized")

            response = self.azure_foundry_client.complete(**args)
            logger.debug("Sync Azure Foundry task executed successfully")
            return response
        except Exception as e:
            logger.error(f"Sync Azure Foundry task execution failed: {str(e)}")
            raise
