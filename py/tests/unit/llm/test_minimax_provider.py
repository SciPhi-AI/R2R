"""Tests for MiniMax LLM provider integration in OpenAICompletionProvider."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.base.abstractions import GenerationConfig
from core.base.providers.llm import CompletionConfig


class TestMiniMaxClientInitialization:
    """Test MiniMax client initialization in OpenAICompletionProvider."""

    @patch.dict(
        os.environ,
        {
            "MINIMAX_API_KEY": "test-minimax-key",
            "OPENAI_API_KEY": "",
            "AZURE_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
            "AZURE_FOUNDRY_API_KEY": "",
        },
        clear=False,
    )
    @patch("core.providers.llm.openai.OpenAI")
    @patch("core.providers.llm.openai.AsyncOpenAI")
    def test_minimax_client_initialized_with_api_key(
        self, mock_async_openai, mock_openai
    ):
        """MiniMax clients should be initialized when MINIMAX_API_KEY is set."""
        from core.providers.llm.openai import OpenAICompletionProvider

        config = CompletionConfig(provider="openai")
        provider = OpenAICompletionProvider(config)

        assert provider.minimax_client is not None
        assert provider.async_minimax_client is not None

    @patch.dict(
        os.environ,
        {
            "MINIMAX_API_KEY": "test-minimax-key",
            "MINIMAX_API_BASE": "https://custom.minimax.api/v1",
            "OPENAI_API_KEY": "",
            "AZURE_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
            "AZURE_FOUNDRY_API_KEY": "",
        },
        clear=False,
    )
    @patch("core.providers.llm.openai.OpenAI")
    @patch("core.providers.llm.openai.AsyncOpenAI")
    def test_minimax_custom_api_base(self, mock_async_openai, mock_openai):
        """MiniMax clients should use custom MINIMAX_API_BASE when set."""
        from core.providers.llm.openai import OpenAICompletionProvider

        config = CompletionConfig(provider="openai")
        provider = OpenAICompletionProvider(config)

        # Verify that the sync client was created with custom base_url
        calls = [
            c
            for c in mock_openai.call_args_list
            if c[1].get("base_url") == "https://custom.minimax.api/v1"
        ]
        assert len(calls) == 1

    @patch.dict(
        os.environ,
        {
            "MINIMAX_API_KEY": "",
            "OPENAI_API_KEY": "test-key",
            "AZURE_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
            "AZURE_FOUNDRY_API_KEY": "",
        },
        clear=False,
    )
    @patch("core.providers.llm.openai.OpenAI")
    @patch("core.providers.llm.openai.AsyncOpenAI")
    def test_minimax_not_initialized_without_key(
        self, mock_async_openai, mock_openai
    ):
        """MiniMax clients should not be initialized without MINIMAX_API_KEY."""
        from core.providers.llm.openai import OpenAICompletionProvider

        config = CompletionConfig(provider="openai")
        provider = OpenAICompletionProvider(config)

        assert provider.minimax_client is None
        assert provider.async_minimax_client is None

    @patch.dict(
        os.environ,
        {
            "MINIMAX_API_KEY": "test-minimax-key",
            "OPENAI_API_KEY": "",
            "AZURE_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
            "AZURE_FOUNDRY_API_KEY": "",
        },
        clear=False,
    )
    @patch("core.providers.llm.openai.OpenAI")
    @patch("core.providers.llm.openai.AsyncOpenAI")
    def test_minimax_only_credentials_passes_validation(
        self, mock_async_openai, mock_openai
    ):
        """Provider should not raise when only MINIMAX_API_KEY is set."""
        from core.providers.llm.openai import OpenAICompletionProvider

        config = CompletionConfig(provider="openai")
        # Should not raise ValueError
        provider = OpenAICompletionProvider(config)
        assert provider.minimax_client is not None


class TestMiniMaxClientRouting:
    """Test model prefix routing for MiniMax."""

    def _create_provider_with_minimax(self):
        """Helper to create a provider with MiniMax clients mocked."""
        from core.providers.llm.openai import OpenAICompletionProvider

        with patch.dict(
            os.environ,
            {
                "MINIMAX_API_KEY": "test-key",
                "OPENAI_API_KEY": "test-key",
                "AZURE_API_KEY": "",
                "DEEPSEEK_API_KEY": "",
                "AZURE_FOUNDRY_API_KEY": "",
            },
            clear=False,
        ), patch("core.providers.llm.openai.OpenAI") as mock_openai, patch(
            "core.providers.llm.openai.AsyncOpenAI"
        ) as mock_async_openai:
            config = CompletionConfig(provider="openai")
            provider = OpenAICompletionProvider(config)
            return provider

    def test_sync_routing_minimax_prefix(self):
        """minimax/ prefix should route to MiniMax sync client."""
        provider = self._create_provider_with_minimax()
        client, model_name = provider._get_client_and_model(
            "minimax/MiniMax-M2.7"
        )
        assert client == provider.minimax_client
        assert model_name == "MiniMax-M2.7"

    def test_async_routing_minimax_prefix(self):
        """minimax/ prefix should route to MiniMax async client."""
        provider = self._create_provider_with_minimax()
        client, model_name = provider._get_async_client_and_model(
            "minimax/MiniMax-M2.7"
        )
        assert client == provider.async_minimax_client
        assert model_name == "MiniMax-M2.7"

    def test_sync_routing_minimax_m25_highspeed(self):
        """minimax/ prefix should work with M2.5-highspeed model."""
        provider = self._create_provider_with_minimax()
        client, model_name = provider._get_client_and_model(
            "minimax/MiniMax-M2.5-highspeed"
        )
        assert client == provider.minimax_client
        assert model_name == "MiniMax-M2.5-highspeed"

    def test_sync_routing_minimax_raises_without_client(self):
        """Should raise ValueError when minimax/ prefix used without credentials."""
        from core.providers.llm.openai import OpenAICompletionProvider

        with patch.dict(
            os.environ,
            {
                "MINIMAX_API_KEY": "",
                "OPENAI_API_KEY": "test-key",
                "AZURE_API_KEY": "",
                "DEEPSEEK_API_KEY": "",
                "AZURE_FOUNDRY_API_KEY": "",
            },
            clear=False,
        ), patch("core.providers.llm.openai.OpenAI"), patch(
            "core.providers.llm.openai.AsyncOpenAI"
        ):
            config = CompletionConfig(provider="openai")
            provider = OpenAICompletionProvider(config)

            with pytest.raises(ValueError, match="MiniMax credentials"):
                provider._get_client_and_model("minimax/MiniMax-M2.7")

    def test_async_routing_minimax_raises_without_client(self):
        """Should raise ValueError when minimax/ prefix used without async credentials."""
        from core.providers.llm.openai import OpenAICompletionProvider

        with patch.dict(
            os.environ,
            {
                "MINIMAX_API_KEY": "",
                "OPENAI_API_KEY": "test-key",
                "AZURE_API_KEY": "",
                "DEEPSEEK_API_KEY": "",
                "AZURE_FOUNDRY_API_KEY": "",
            },
            clear=False,
        ), patch("core.providers.llm.openai.OpenAI"), patch(
            "core.providers.llm.openai.AsyncOpenAI"
        ):
            config = CompletionConfig(provider="openai")
            provider = OpenAICompletionProvider(config)

            with pytest.raises(ValueError, match="MiniMax credentials"):
                provider._get_async_client_and_model("minimax/MiniMax-M2.7")


class TestMiniMaxTemperatureClamping:
    """Test temperature clamping for MiniMax models."""

    def _create_provider_with_minimax(self):
        """Helper to create a provider with MiniMax clients mocked."""
        from core.providers.llm.openai import OpenAICompletionProvider

        with patch.dict(
            os.environ,
            {
                "MINIMAX_API_KEY": "test-key",
                "OPENAI_API_KEY": "test-key",
                "AZURE_API_KEY": "",
                "DEEPSEEK_API_KEY": "",
                "AZURE_FOUNDRY_API_KEY": "",
            },
            clear=False,
        ), patch("core.providers.llm.openai.OpenAI"), patch(
            "core.providers.llm.openai.AsyncOpenAI"
        ):
            config = CompletionConfig(provider="openai")
            provider = OpenAICompletionProvider(config)
            return provider

    def test_minimax_temperature_clamped_to_max_1(self):
        """Temperature above 1.0 should be clamped to 1.0 for MiniMax models."""
        provider = self._create_provider_with_minimax()
        gen_config = GenerationConfig(
            model="minimax/MiniMax-M2.7", temperature=1.5
        )
        args = provider._get_base_args(gen_config)
        assert args["temperature"] == 1.0

    def test_minimax_temperature_clamped_to_min_0(self):
        """Negative temperature should be clamped to 0.0 for MiniMax models."""
        provider = self._create_provider_with_minimax()
        gen_config = GenerationConfig(
            model="minimax/MiniMax-M2.7", temperature=-0.5
        )
        args = provider._get_base_args(gen_config)
        assert args["temperature"] == 0.0

    def test_minimax_temperature_within_range_unchanged(self):
        """Temperature within [0, 1] should remain unchanged for MiniMax."""
        provider = self._create_provider_with_minimax()
        gen_config = GenerationConfig(
            model="minimax/MiniMax-M2.7", temperature=0.7
        )
        args = provider._get_base_args(gen_config)
        assert args["temperature"] == 0.7

    def test_openai_temperature_not_clamped(self):
        """Temperature should not be clamped for non-MiniMax models."""
        provider = self._create_provider_with_minimax()
        gen_config = GenerationConfig(
            model="openai/gpt-4.1", temperature=1.5
        )
        args = provider._get_base_args(gen_config)
        assert args["temperature"] == 1.5


class TestMiniMaxBaseArgs:
    """Test _get_base_args for MiniMax models."""

    def _create_provider_with_minimax(self):
        from core.providers.llm.openai import OpenAICompletionProvider

        with patch.dict(
            os.environ,
            {
                "MINIMAX_API_KEY": "test-key",
                "OPENAI_API_KEY": "test-key",
                "AZURE_API_KEY": "",
                "DEEPSEEK_API_KEY": "",
                "AZURE_FOUNDRY_API_KEY": "",
            },
            clear=False,
        ), patch("core.providers.llm.openai.OpenAI"), patch(
            "core.providers.llm.openai.AsyncOpenAI"
        ):
            config = CompletionConfig(provider="openai")
            provider = OpenAICompletionProvider(config)
            return provider

    def test_minimax_base_args_include_standard_fields(self):
        """MiniMax should produce standard OpenAI-compatible args."""
        provider = self._create_provider_with_minimax()
        gen_config = GenerationConfig(
            model="minimax/MiniMax-M2.7",
            temperature=0.5,
            top_p=0.9,
            max_tokens_to_sample=2048,
            stream=False,
        )
        args = provider._get_base_args(gen_config)
        assert args["model"] == "minimax/MiniMax-M2.7"
        assert args["temperature"] == 0.5
        assert args["top_p"] == 0.9
        assert args["max_tokens"] == 2048
        assert args["stream"] is False

    def test_minimax_response_format_passed(self):
        """response_format should be passed through for MiniMax models."""
        provider = self._create_provider_with_minimax()
        gen_config = GenerationConfig(
            model="minimax/MiniMax-M2.7",
            response_format={"type": "json_object"},
        )
        args = provider._get_base_args(gen_config)
        assert args["response_format"] == {"type": "json_object"}

    def test_minimax_tools_passed(self):
        """Tools should be passed through for MiniMax models."""
        provider = self._create_provider_with_minimax()
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "parameters": {"type": "object"},
                },
            }
        ]
        gen_config = GenerationConfig(
            model="minimax/MiniMax-M2.7", tools=tools
        )
        args = provider._get_base_args(gen_config)
        assert args["tools"] == tools


class TestR2RRouterMiniMax:
    """Test that the R2R router correctly dispatches minimax/ prefix."""

    @patch.dict(
        os.environ,
        {
            "MINIMAX_API_KEY": "test-key",
            "OPENAI_API_KEY": "test-key",
            "ANTHROPIC_API_KEY": "test-key",
            "AZURE_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
            "AZURE_FOUNDRY_API_KEY": "",
        },
        clear=False,
    )
    @patch("core.providers.llm.openai.OpenAI")
    @patch("core.providers.llm.openai.AsyncOpenAI")
    @patch("core.providers.llm.anthropic.Anthropic")
    @patch("core.providers.llm.anthropic.AsyncAnthropic")
    def test_r2r_routes_minimax_to_openai_provider(
        self,
        mock_async_anthropic,
        mock_anthropic,
        mock_async_openai,
        mock_openai,
    ):
        """minimax/ prefix should be routed to the OpenAI sub-provider."""
        from core.providers.llm.r2r_llm import R2RCompletionProvider

        config = CompletionConfig(provider="r2r")
        provider = R2RCompletionProvider(config)

        sub = provider._choose_subprovider_by_model("minimax/MiniMax-M2.7")
        assert sub is provider._openai_provider


class TestMiniMaxConfigFile:
    """Test the MiniMax config TOML file."""

    def test_minimax_config_exists(self):
        """The minimax.toml config file should exist."""
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "core",
            "configs",
            "minimax.toml",
        )
        assert os.path.exists(config_path), f"minimax.toml not found at {config_path}"

    def test_minimax_config_valid_toml(self):
        """The minimax.toml config should be valid TOML."""
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]

        config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "core",
            "configs",
            "minimax.toml",
        )
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        assert data["app"]["quality_llm"] == "minimax/MiniMax-M2.7"
        assert (
            data["app"]["fast_llm"] == "minimax/MiniMax-M2.5-highspeed"
        )
        assert data["completion"]["provider"] == "openai"
