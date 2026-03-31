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
    normalize_hf_url,
    derive_model_name,
    download_gguf,
    import_gguf_to_ollama,
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
        assert cfg.get("models", "qwen3.5") == "qwen3.5:9b-q8_0"
        assert cfg.get("models", "default") == "qwen3.5"
        assert cfg.get("ollama", "host") == DEFAULT_HOST

    def test_updates_existing_config(self, tmp_path):
        config_path = str(tmp_path / "config.ini")
        # Write an existing config with legacy model key
        cfg = configparser.ConfigParser()
        cfg["ollama"] = {"host": DEFAULT_HOST, "model": "llama2"}
        with open(config_path, "w") as f:
            cfg.write(f)

        update_config("qwen3.5:9b-q8_0", DEFAULT_HOST, config_path)

        cfg2 = configparser.ConfigParser()
        cfg2.read(config_path)
        assert cfg2.get("models", "qwen3.5") == "qwen3.5:9b-q8_0"
        assert cfg2.get("models", "default") == "qwen3.5"
        # legacy key should be removed
        assert not cfg2.has_option("ollama", "model")

    def test_preserves_existing_models(self, tmp_path):
        config_path = str(tmp_path / "config.ini")
        cfg = configparser.ConfigParser()
        cfg["models"] = {"default": "llama3", "llama3": "llama3:8b"}
        with open(config_path, "w") as f:
            cfg.write(f)

        update_config("qwen3.5:9b-q8_0", DEFAULT_HOST, config_path)

        cfg2 = configparser.ConfigParser()
        cfg2.read(config_path)
        assert cfg2.get("models", "llama3") == "llama3:8b"
        assert cfg2.get("models", "qwen3.5") == "qwen3.5:9b-q8_0"
        assert cfg2.get("models", "default") == "qwen3.5"

    def test_custom_alias(self, tmp_path):
        config_path = str(tmp_path / "config.ini")
        update_config("thedrummer-anubis-mini-8b-v1-q8-0", DEFAULT_HOST, config_path, alias="anubis")

        cfg = configparser.ConfigParser()
        cfg.read(config_path)
        assert cfg.get("models", "anubis") == "thedrummer-anubis-mini-8b-v1-q8-0"
        assert cfg.get("models", "default") == "anubis"


class TestNormalizeHfUrl:
    def test_blob_to_resolve(self):
        url = "https://huggingface.co/bartowski/TheDrummer_Anubis-Mini-8B-v1-GGUF/blob/main/TheDrummer_Anubis-Mini-8B-v1-Q8_0.gguf"
        expected = "https://huggingface.co/bartowski/TheDrummer_Anubis-Mini-8B-v1-GGUF/resolve/main/TheDrummer_Anubis-Mini-8B-v1-Q8_0.gguf"
        assert normalize_hf_url(url) == expected

    def test_already_resolve_unchanged(self):
        url = "https://huggingface.co/bartowski/TheDrummer_Anubis-Mini-8B-v1-GGUF/resolve/main/TheDrummer_Anubis-Mini-8B-v1-Q8_0.gguf"
        assert normalize_hf_url(url) == url

    def test_non_hf_url_unchanged(self):
        url = "https://example.com/models/my-model.gguf"
        assert normalize_hf_url(url) == url


class TestDeriveModelName:
    def test_basic_gguf_filename(self):
        name = derive_model_name("TheDrummer_Anubis-Mini-8B-v1-Q8_0.gguf")
        assert name == "thedrummer-anubis-mini-8b-v1-q8-0"

    def test_simple_filename(self):
        name = derive_model_name("llama3-8b.gguf")
        assert name == "llama3-8b"

    def test_preserves_lowercase(self):
        name = derive_model_name("already-lowercase.gguf")
        assert name == "already-lowercase"

    def test_underscores_become_hyphens(self):
        name = derive_model_name("my_cool_model.gguf")
        assert name == "my-cool-model"


class TestDownloadGguf:
    def test_downloads_file(self, tmp_path):
        url = "https://huggingface.co/owner/repo/resolve/main/model.gguf"
        fake_data = b"fake gguf data"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Length": str(len(fake_data))}
        mock_resp.read.side_effect = [fake_data, b""]
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("aidm.setup.urllib.request.urlopen", return_value=mock_resp):
            result = download_gguf(url, dest_dir=str(tmp_path))

        assert os.path.basename(result) == "model.gguf"
        assert os.path.exists(result)
        assert open(result, "rb").read() == fake_data

    def test_skips_existing_file_with_matching_size(self, tmp_path):
        url = "https://huggingface.co/owner/repo/resolve/main/model.gguf"
        existing = tmp_path / "model.gguf"
        existing.write_bytes(b"existing data")  # 13 bytes

        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": "13"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("aidm.setup.urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            result = download_gguf(url, dest_dir=str(tmp_path))

        assert result == str(existing)
        # urlopen called once for HEAD-like check, but read() should not be called
        assert open(result, "rb").read() == b"existing data"


class TestImportGgufToOllama:
    @patch("aidm.setup.subprocess.run")
    def test_creates_model_successfully(self, mock_run, tmp_path):
        gguf_path = str(tmp_path / "model.gguf")
        open(gguf_path, "w").close()  # create dummy file
        mock_run.return_value = MagicMock(returncode=0)

        result = import_gguf_to_ollama(gguf_path, "my-model")

        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ollama" in args
        assert "create" in args
        assert "my-model" in args

    @patch("aidm.setup.subprocess.run")
    def test_returns_false_on_failure(self, mock_run, tmp_path):
        gguf_path = str(tmp_path / "model.gguf")
        open(gguf_path, "w").close()
        mock_run.return_value = MagicMock(returncode=1)

        result = import_gguf_to_ollama(gguf_path, "my-model")
        assert result is False
