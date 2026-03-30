"""Tests for DM construction and config helpers."""

import configparser

from aidm.dm import UniversalDM
from aidm.config import get_ollama_settings


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


class TestOllamaSettings:
    """get_ollama_settings should read from config or return defaults."""

    def test_defaults_without_config(self):
        s = get_ollama_settings(None)
        assert s["host"] == "http://localhost:11434"
        assert s["model"] == "qwen3.5:9b-q8_0"
        assert s["max_tokens"] == 1000

    def test_reads_from_config(self):
        cfg = configparser.ConfigParser()
        cfg["ollama"] = {
            "host": "http://myhost:9999",
            "model": "llama3",
            "max_tokens": "2048",
        }
        s = get_ollama_settings(cfg)
        assert s["host"] == "http://myhost:9999"
        assert s["model"] == "llama3"
        assert s["max_tokens"] == 2048

    def test_partial_config_uses_defaults(self):
        cfg = configparser.ConfigParser()
        cfg["ollama"] = {"model": "custom-model"}
        s = get_ollama_settings(cfg)
        assert s["host"] == "http://localhost:11434"
        assert s["model"] == "custom-model"
        assert s["max_tokens"] == 1000
