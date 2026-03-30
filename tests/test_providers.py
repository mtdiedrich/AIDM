"""Tests for provider consolidation and config mapping."""

from unittest.mock import patch, MagicMock
import configparser
import pytest

from aidm.llm_providers import OpenAIProvider, create_provider
from aidm.config import create_provider_from_config


class TestOpenAIProviderBaseUrl:
    """OpenAIProvider should accept a base_url for local servers."""

    def test_base_url_stored(self):
        p = OpenAIProvider(api_key="test-key", model="gpt-4", base_url="http://localhost:11434/v1")
        assert p.base_url == "http://localhost:11434/v1"

    def test_base_url_default_is_none(self):
        p = OpenAIProvider(api_key="test-key")
        assert p.base_url is None

    @patch.dict("sys.modules", {"openai": MagicMock()})
    def test_base_url_passed_to_client(self):
        import sys
        mock_openai = sys.modules["openai"]
        mock_openai.OpenAI = MagicMock()
        p = OpenAIProvider(api_key="k", base_url="http://localhost:1234/v1")
        p._client_initialized = False  # reset since module was just injected
        p._ensure_client()
        mock_openai.OpenAI.assert_called_once_with(api_key="k", base_url="http://localhost:1234/v1")

    @patch.dict("sys.modules", {"openai": MagicMock()})
    def test_dummy_key_when_base_url_set_no_key(self):
        """When base_url is set but no api_key, use a dummy key so the client still initialises."""
        import sys
        mock_openai = sys.modules["openai"]
        mock_openai.OpenAI = MagicMock()
        p = OpenAIProvider(base_url="http://localhost:11434/v1")
        p._client_initialized = False
        p._ensure_client()
        assert p.client is not None
        call_kwargs = mock_openai.OpenAI.call_args[1]
        assert call_kwargs["api_key"] is not None  # should be a dummy value


class TestMaxTokens:
    """max_tokens should be configurable on providers."""

    def test_openai_default_max_tokens(self):
        p = OpenAIProvider(api_key="k")
        assert p.max_tokens == 1000

    def test_openai_custom_max_tokens(self):
        p = OpenAIProvider(api_key="k", max_tokens=2000)
        assert p.max_tokens == 2000


class TestConfigMapsOllamaToOpenAI:
    """config.py should map the 'ollama' provider to OpenAIProvider with base_url."""

    def test_ollama_creates_openai_provider(self):
        cfg = configparser.ConfigParser()
        cfg["ollama"] = {
            "host": "http://localhost:11434",
            "model": "qwen3.5:9b-q8_0",
        }
        provider = create_provider_from_config(cfg, "ollama")
        assert isinstance(provider, OpenAIProvider)
        assert "localhost:11434" in provider.base_url

    def test_lmstudio_creates_openai_provider(self):
        cfg = configparser.ConfigParser()
        cfg["lmstudio"] = {
            "host": "http://localhost:1234",
            "model": "local-model",
        }
        provider = create_provider_from_config(cfg, "lmstudio")
        assert isinstance(provider, OpenAIProvider)
        assert "localhost:1234" in provider.base_url

    def test_max_tokens_read_from_config(self):
        cfg = configparser.ConfigParser()
        cfg["ollama"] = {
            "host": "http://localhost:11434",
            "model": "qwen3.5:9b-q8_0",
            "max_tokens": "2048",
        }
        provider = create_provider_from_config(cfg, "ollama")
        assert provider.max_tokens == 2048


class TestProviderFactoryCleanup:
    """create_provider should no longer accept 'ollama', 'lmstudio', or 'llamacpp'."""

    def test_ollama_not_in_factory(self):
        with pytest.raises(ValueError):
            create_provider("ollama")

    def test_lmstudio_not_in_factory(self):
        with pytest.raises(ValueError):
            create_provider("lmstudio")

    def test_llamacpp_not_in_factory(self):
        with pytest.raises(ValueError):
            create_provider("llamacpp")

    def test_openai_still_works(self):
        p = create_provider("openai", api_key="test")
        assert isinstance(p, OpenAIProvider)
