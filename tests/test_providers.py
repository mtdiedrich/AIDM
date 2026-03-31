"""Tests for DM construction and config helpers."""

import configparser

from aidm.dm import UniversalDM
from aidm.config import get_ollama_settings, get_models, resolve_model


class TestDMInit:
    """UniversalDM should store host, model, max_tokens."""

    def test_defaults(self):
        dm = UniversalDM()
        assert dm.host == "http://localhost:11434"
        assert dm.model == "qwen3.5:9b-q8_0"
        assert dm.max_tokens == 1000

    def test_custom_values(self):
        dm = UniversalDM(host="http://myhost:9999", model="llama3", max_tokens=2048)
        assert dm.host == "http://myhost:9999"
        assert dm.model == "llama3"
        assert dm.max_tokens == 2048

    def test_trailing_slash_stripped(self):
        dm = UniversalDM(host="http://localhost:11434/")
        assert dm.host == "http://localhost:11434"

    def test_display_name(self):
        dm = UniversalDM(model="qwen3.5:9b-q8_0")
        assert "Ollama" in dm.get_display_name()
        assert "qwen3.5:9b-q8_0" in dm.get_display_name()


class TestGetModels:
    def test_returns_empty_without_config(self):
        assert get_models(None) == {}

    def test_returns_aliases_excluding_default(self):
        cfg = configparser.ConfigParser()
        cfg["models"] = {"default": "qwen", "qwen": "qwen3.5:9b-q8_0", "anubis": "anubis-8b"}
        models = get_models(cfg)
        assert "default" not in models
        assert models["qwen"] == "qwen3.5:9b-q8_0"
        assert models["anubis"] == "anubis-8b"


class TestResolveModel:
    def test_no_config_returns_default(self):
        assert resolve_model(None) == "qwen3.5:9b-q8_0"

    def test_alias_lookup(self):
        cfg = configparser.ConfigParser()
        cfg["models"] = {"default": "qwen", "qwen": "qwen3.5:9b-q8_0"}
        assert resolve_model(cfg, "qwen") == "qwen3.5:9b-q8_0"

    def test_direct_name_passthrough(self):
        cfg = configparser.ConfigParser()
        cfg["models"] = {"default": "qwen", "qwen": "qwen3.5:9b-q8_0"}
        assert resolve_model(cfg, "llama3:8b") == "llama3:8b"

    def test_default_alias_resolved(self):
        cfg = configparser.ConfigParser()
        cfg["models"] = {"default": "anubis", "anubis": "anubis-8b", "qwen": "qwen3.5:9b-q8_0"}
        assert resolve_model(cfg) == "anubis-8b"

    def test_legacy_ollama_model_fallback(self):
        cfg = configparser.ConfigParser()
        cfg["ollama"] = {"model": "old-model"}
        assert resolve_model(cfg) == "old-model"


class TestOllamaSettings:
    """get_ollama_settings should read from config or return defaults."""

    def test_defaults_without_config(self):
        s = get_ollama_settings(None)
        assert s["host"] == "http://localhost:11434"
        assert s["model"] == "qwen3.5:9b-q8_0"
        assert s["max_tokens"] == 1000

    def test_reads_model_from_models_section(self):
        cfg = configparser.ConfigParser()
        cfg["ollama"] = {
            "host": "http://myhost:9999",
            "max_tokens": "2048",
        }
        cfg["models"] = {"default": "llama3", "llama3": "llama3:8b"}
        s = get_ollama_settings(cfg)
        assert s["host"] == "http://myhost:9999"
        assert s["model"] == "llama3:8b"
        assert s["max_tokens"] == 2048

    def test_model_override_by_alias(self):
        cfg = configparser.ConfigParser()
        cfg["models"] = {"default": "qwen", "qwen": "qwen3.5:9b-q8_0", "anubis": "anubis-8b"}
        s = get_ollama_settings(cfg, model="anubis")
        assert s["model"] == "anubis-8b"

    def test_model_override_direct_name(self):
        cfg = configparser.ConfigParser()
        cfg["models"] = {"default": "qwen", "qwen": "qwen3.5:9b-q8_0"}
        s = get_ollama_settings(cfg, model="mistral:7b")
        assert s["model"] == "mistral:7b"

    def test_partial_config_uses_defaults(self):
        cfg = configparser.ConfigParser()
        cfg["ollama"] = {}
        s = get_ollama_settings(cfg)
        assert s["host"] == "http://localhost:11434"
        assert s["model"] == "qwen3.5:9b-q8_0"
        assert s["max_tokens"] == 1000
