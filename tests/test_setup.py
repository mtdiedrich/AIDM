"""Tests for aidm.setup module"""

import configparser
import os
import urllib.error
import pytest
from unittest.mock import patch, MagicMock


from aidm.setup import (
    check_ollama_installed,
    check_ollama_running,
    install_ollama,
    pull_model,
    update_config,
)

DEFAULT_HOST = "http://localhost:11434"


class TestCheckOllamaInstalled:
    def test_returns_true_when_available(self):
        with patch("aidm.setup.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert check_ollama_installed() is True

    def test_returns_false_when_not_found(self):
        with patch("aidm.setup.subprocess.run", side_effect=FileNotFoundError):
            assert check_ollama_installed() is False


class TestInstallOllama:
    @patch("aidm.setup.sys")
    @patch("aidm.setup.subprocess.run")
    @patch("aidm.setup.check_ollama_installed", return_value=True)
    @patch("aidm.setup._refresh_path_windows")
    def test_installs_via_winget_on_windows(self, mock_refresh, mock_check, mock_run, mock_sys):
        mock_sys.platform = "win32"
        mock_run.return_value = MagicMock(returncode=0)
        assert install_ollama() is True
        mock_run.assert_called_once()
        assert "winget" in mock_run.call_args[0][0]

    @patch("aidm.setup.sys")
    @patch("aidm.setup.subprocess.run", side_effect=FileNotFoundError)
    def test_returns_false_when_winget_missing(self, mock_run, mock_sys):
        mock_sys.platform = "win32"
        assert install_ollama() is False


class TestCheckOllamaRunning:
    def test_returns_true_when_server_up(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("aidm.setup.urllib.request.urlopen", return_value=mock_resp):
            assert check_ollama_running(DEFAULT_HOST) is True

    def test_returns_false_on_connection_error(self):
        with patch("aidm.setup.urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            assert check_ollama_running(DEFAULT_HOST) is False


class TestPullModel:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = lambda s: iter([
            b'{"status":"pulling manifest"}',
            b'{"status":"success"}',
        ])
        with patch("aidm.setup.urllib.request.urlopen", return_value=mock_resp):
            assert pull_model("qwen3.5:9b-q8_0", DEFAULT_HOST) is True

    def test_failure_on_error(self):
        with patch("aidm.setup.urllib.request.urlopen", side_effect=urllib.error.HTTPError(
            url="", code=404, msg="not found", hdrs=None, fp=None
        )):
            assert pull_model("nonexistent:model", DEFAULT_HOST) is False


class TestUpdateConfig:
    def test_creates_config_from_scratch(self, tmp_path):
        config_path = str(tmp_path / "config.ini")
        update_config("qwen3.5:9b-q8_0", DEFAULT_HOST, config_path)

        cfg = configparser.ConfigParser()
        cfg.read(config_path)
        assert cfg.get("DEFAULT", "default_provider") == "ollama"
        assert cfg.get("ollama", "model") == "qwen3.5:9b-q8_0"
        assert cfg.get("ollama", "host") == DEFAULT_HOST

    def test_updates_existing_config(self, tmp_path):
        config_path = str(tmp_path / "config.ini")
        # Write an existing config with openai default
        cfg = configparser.ConfigParser()
        cfg["DEFAULT"] = {"default_provider": "openai"}
        cfg["openai"] = {"api_key": "sk-test", "model": "gpt-4"}
        cfg["ollama"] = {"host": DEFAULT_HOST, "model": "llama2"}
        with open(config_path, "w") as f:
            cfg.write(f)

        update_config("qwen3.5:9b-q8_0", DEFAULT_HOST, config_path)

        cfg2 = configparser.ConfigParser()
        cfg2.read(config_path)
        assert cfg2.get("DEFAULT", "default_provider") == "ollama"
        assert cfg2.get("ollama", "model") == "qwen3.5:9b-q8_0"
        # OpenAI section preserved
        assert cfg2.get("openai", "api_key") == "sk-test"
