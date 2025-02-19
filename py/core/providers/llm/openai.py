import logging
import os
from typing import Any

from openai import AsyncAzureOpenAI, AsyncOpenAI, OpenAI

from core.base.abstractions import GenerationConfig
from core.base.providers.llm import CompletionConfig, CompletionProvider

logger = logging.getLogger()


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
        if os.getenv("AZURE_API_KEY") and os.getenv("AZURE_API_BASE"):
            self.azure_client = AsyncAzureOpenAI(
                api_key=os.getenv("AZURE_API_KEY"),
                api_version=os.getenv(
                    "AZURE_API_VERSION", "2024-02-15-preview"
                ),
                azure_endpoint=os.getenv("AZURE_API_BASE"),
            )
            self.async_azure_client = AsyncAzureOpenAI(
                api_key=os.getenv("AZURE_API_KEY"),
                api_version=os.getenv(
                    "AZURE_API_VERSION", "2024-02-15-preview"
                ),
                azure_endpoint=os.getenv("AZURE_API_BASE"),
            )
            logger.debug("Azure OpenAI clients initialized successfully")

        # Initialize Deepseek clients if credentials exist
        if os.getenv("DEEPSEEK_API_KEY") and os.getenv(
            "DEEPSEEK_API_BASE", "https://api.deepseek.com"
        ):
            self.deepseek_client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv(
                    "DEEPSEEK_API_BASE", "https://api.deepseek.com"
                ),
            )
            self.async_deepseek_client = AsyncOpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv(
                    "DEEPSEEK_API_BASE", "https://api.deepseek.com"
                ),
            )
            logger.debug("Deepseek OpenAI clients initialized successfully")

        # Initialize Ollama clients with default API key
        if os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1"):
            self.ollama_client = OpenAI(
                api_key=os.getenv("OLLAMA_API_KEY", "dummy"),
                base_url=os.getenv(
                    "OLLAMA_API_BASE", "http://localhost:11434/v1"
                ),
            )
            self.async_ollama_client = AsyncOpenAI(
                api_key=os.getenv("OLLAMA_API_KEY", "dummy"),
                base_url=os.getenv(
                    "OLLAMA_API_BASE", "http://localhost:11434/v1"
                ),
            )
            logger.debug("Ollama OpenAI clients initialized successfully")

        # Initialize LMStudio clients
        if os.getenv("LMSTUDIO_API_BASE", "http://localhost:1234/v1"):
            self.lmstudio_client = OpenAI(
                api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio"),
                base_url=os.getenv(
                    "LMSTUDIO_API_BASE", "http://localhost:1234/v1"
                ),
            )
            self.async_lmstudio_client = AsyncOpenAI(
                api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio"),
                base_url=os.getenv(
                    "LMSTUDIO_API_BASE", "http://localhost:1234/v1"
                ),
            )
            logger.debug("LMStudio OpenAI clients initialized successfully")

        # Initialize Azure Foundry clients if credentials exist.
        # These use the Azure Inference API (currently pasted into this handler).
        if os.getenv("AZURE_FOUNDRY_API_KEY") and os.getenv(
            "AZURE_FOUNDRY_API_ENDPOINT"
        ):
            from azure.ai.inference import (
                ChatCompletionsClient as AzureChatCompletionsClient,
            )
            from azure.ai.inference.aio import (
                ChatCompletionsClient as AsyncAzureChatCompletionsClient,
            )
            from azure.core.credentials import AzureKeyCredential

            self.azure_foundry_client = AzureChatCompletionsClient(
                endpoint=os.getenv("AZURE_FOUNDRY_API_ENDPOINT"),
                credential=AzureKeyCredential(
                    os.getenv("AZURE_FOUNDRY_API_KEY")
                ),
                api_version=os.getenv(
                    "AZURE_FOUNDRY_API_VERSION", "2024-05-01-preview"
                ),
            )
            self.async_azure_foundry_client = AsyncAzureChatCompletionsClient(
                endpoint=os.getenv("AZURE_FOUNDRY_API_ENDPOINT"),
                credential=AzureKeyCredential(
                    os.getenv("AZURE_FOUNDRY_API_KEY")
                ),
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

    def _get_base_args(self, generation_config: GenerationConfig) -> dict:
        args = {
            "model": generation_config.model,
            "top_p": generation_config.top_p,
            "stream": generation_config.stream,
        }
        if (
            "o1" not in generation_config.model
            and "o3" not in generation_config.model
        ):
            args["max_tokens"] = generation_config.max_tokens_to_sample
            args["temperature"] = generation_config.temperature
        else:
            args["max_completion_tokens"] = (
                generation_config.max_tokens_to_sample
            )

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
        client, model_name = self._get_async_client_and_model(args["model"])
        args["model"] = model_name
        args["messages"] = messages
        args = {**args, **kwargs}
        logger.debug(f"Executing async task with args: {args}")
        try:
            # For Azure Foundry, use the `complete` method; otherwise, use the OpenAI-style method.
            if client == self.async_azure_foundry_client:
                args.pop("model")
                response = await client.complete(**args)
            else:
                response = await client.chat.completions.create(**args)
            logger.debug("Async task executed successfully")
            return response
        except Exception as e:
            logger.error(f"Async task execution failed: {str(e)}")
            raise

    def _execute_task_sync(self, task: dict[str, Any]):
        messages = task["messages"]
        generation_config = task["generation_config"]
        kwargs = task["kwargs"]

        args = self._get_base_args(generation_config)
        client, model_name = self._get_client_and_model(args["model"])
        args["model"] = model_name
        args["messages"] = messages
        args = {**args, **kwargs}

        logger.debug(f"Executing sync task with args: {args}")
        try:
            # For Azure Foundry, use `complete`; otherwise, use the standard method.
            if client == self.azure_foundry_client:
                response = client.complete(**args)
            else:
                response = client.chat.completions.create(**args)
            logger.debug("Sync task executed successfully")
            return response
        except Exception as e:
            logger.error(f"Sync task execution failed: {str(e)}")
            raise
