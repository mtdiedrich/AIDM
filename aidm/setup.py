"""
Automated setup for running AIDM with a local Ollama model.

Handles: checking Ollama availability, pulling a model, updating config.ini,
and optionally updating config.ini.
"""

import configparser
import json
import os
import subprocess
import sys
import time
from typing import Optional

import requests
import shutil


DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3.5:9b-q8_0"
DEFAULT_CONFIG = "config.ini"

# llama-cpp / HuggingFace defaults
DEFAULT_HF_REPO = "bartowski/Qwen_Qwen3.5-27B-GGUF"
DEFAULT_HF_FILE = "Qwen_Qwen3.5-27B-IQ2_M.gguf"
DEFAULT_MODELS_DIR = "models"


def check_ollama_installed() -> bool:
    """Return True if the `ollama` CLI is on PATH."""
    try:
        subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            timeout=10,
        )
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def install_ollama() -> bool:
    """Install Ollama via winget (Windows) or curl (Linux/macOS)."""
    if sys.platform == "win32":
        print("  Installing via winget (this may take a while for the 1.8 GB download)...")
        try:
            result = subprocess.run(
                ["winget", "install", "--id", "Ollama.Ollama", "-e", "--accept-source-agreements", "--accept-package-agreements"],
                timeout=1800,
            )
            if result.returncode == 0:
                # winget installs to user's AppData — refresh PATH so we can find it
                _refresh_path_windows()
                return check_ollama_installed()
            print(f"  winget exited with code {result.returncode}.")
            return False
        except subprocess.TimeoutExpired:
            print("  Install timed out. The installer may still be running in the background.")
            print("  Wait for it to finish, then re-run: python run.py --setup")
            return False
        except FileNotFoundError:
            print("  winget not found. Install Ollama manually from https://ollama.com")
            return False
    elif sys.platform == "darwin":
        print("  Installing via brew...")
        try:
            result = subprocess.run(["brew", "install", "ollama"], timeout=300)
            return result.returncode == 0
        except FileNotFoundError:
            print("  brew not found. Install Ollama manually from https://ollama.com")
            return False
    else:
        # Linux — official install script
        print("  Installing via official install script...")
        try:
            result = subprocess.run(
                ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
                timeout=300,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"  Install failed: {e}")
            return False


def _refresh_path_windows():
    """Re-read the Windows PATH so a just-installed program is found."""
    import winreg
    dirs = []
    for root, key_name in [
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, r"Environment"),
    ]:
        try:
            with winreg.OpenKey(root, key_name) as key:
                val, _ = winreg.QueryValueEx(key, "Path")
                dirs.extend(val.split(";"))
        except OSError:
            pass
    if dirs:
        os.environ["PATH"] = ";".join(dirs)


def check_ollama_running(host: str = DEFAULT_HOST) -> bool:
    """Return True if the Ollama HTTP server is responding."""
    try:
        resp = requests.get(f"{host}/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.ConnectionError:
        return False
    except Exception:
        return False


def start_ollama_server() -> bool:
    """Attempt to start `ollama serve` in the background and wait for it."""
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return False

    # Wait up to 15 seconds for the server to come online
    for _ in range(30):
        time.sleep(0.5)
        if check_ollama_running():
            return True
    return False


def model_exists(model: str, host: str = DEFAULT_HOST) -> bool:
    """Check if a model is already pulled locally."""
    try:
        resp = requests.get(f"{host}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            for m in models:
                if m.get("name", "").startswith(model):
                    return True
    except Exception:
        pass
    return False


def pull_model(model: str, host: str = DEFAULT_HOST) -> bool:
    """Pull a model from the Ollama registry with streaming progress."""
    try:
        resp = requests.post(
            f"{host}/api/pull",
            json={"name": model},
            stream=True,
            timeout=None,
        )
        if resp.status_code != 200:
            print(f"  Error: server returned {resp.status_code} — {resp.text}")
            return False

        last_status = ""
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            status = data.get("status", "")
            total = data.get("total", 0)
            completed = data.get("completed", 0)

            if total:
                pct = int(completed / total * 100)
                msg = f"\r  {status}: {pct}%"
            else:
                msg = f"\r  {status}"

            if msg != last_status:
                print(msg, end="", flush=True)
                last_status = msg

            if data.get("error"):
                print(f"\n  Error: {data['error']}")
                return False

        print()  # newline after progress
        return True

    except Exception as e:
        print(f"  Error pulling model: {e}")
        return False


def update_config(
    model: str,
    host: str = DEFAULT_HOST,
    config_path: str = DEFAULT_CONFIG,
) -> None:
    """Write/update config.ini so the game uses Ollama with the given model."""
    cfg = configparser.ConfigParser()
    if os.path.exists(config_path):
        cfg.read(config_path)

    cfg["DEFAULT"]["default_provider"] = "ollama"

    if "ollama" not in cfg:
        cfg["ollama"] = {}
    cfg["ollama"]["host"] = host
    cfg["ollama"]["model"] = model

    with open(config_path, "w") as f:
        cfg.write(f)


def run_setup(
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    config_path: str = DEFAULT_CONFIG,
) -> bool:
    """Full setup flow: check Ollama → start server → pull model → update config."""
    print("=== AIDM Ollama Setup ===\n")

    # 1. Check / install Ollama
    print("[1/4] Checking Ollama installation...")
    if not check_ollama_installed():
        print("  Ollama not found — attempting to install...")
        if install_ollama():
            print("  Ollama installed successfully.")
        else:
            print("  Automatic install failed.")
            print("  Install manually from https://ollama.com and try again.")
            return False
    else:
        print("  Ollama CLI found.")

    # 2. Check / start server
    print("[2/4] Checking Ollama server...")
    if check_ollama_running(host):
        print("  Server is running.")
    else:
        print("  Server not responding — starting it...")
        if start_ollama_server():
            print("  Server started.")
        else:
            print("  Could not start the Ollama server.")
            print("  Try running `ollama serve` manually in another terminal.")
            return False

    # 3. Pull model
    print(f"[3/4] Pulling model '{model}'...")
    if model_exists(model, host):
        print("  Model already available locally — skipping pull.")
    else:
        if not pull_model(model, host):
            print("  Failed to pull the model.")
            return False
        print("  Model ready.")

    # 4. Update config
    print(f"[4/4] Updating {config_path}...")
    update_config(model, host, config_path)
    print("  Config saved.")

    print("\n=== Setup complete! ===")
    print(f"  Provider : ollama")
    print(f"  Model    : {model}")
    print(f"  Host     : {host}\n")

    return True


# ---------------------------------------------------------------------------
# llama-cpp-python + HuggingFace setup
# ---------------------------------------------------------------------------

def _find_hf_cli() -> Optional[str]:
    """Find the HuggingFace CLI executable ('hf' or legacy 'huggingface-cli')."""
    # v1.8+ uses 'hf', older versions use 'huggingface-cli'
    for name in ("hf", "huggingface-cli"):
        path = shutil.which(name)
        if path:
            return path
        # Check Scripts dir next to the running Python (venv / conda)
        scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
        for ext in ("", ".exe"):
            candidate = os.path.join(scripts_dir, name + ext)
            if os.path.isfile(candidate):
                return candidate
    return None


def check_hf_hub() -> bool:
    """Return True if huggingface-cli is available."""
    return _find_hf_cli() is not None


def install_hf_hub() -> bool:
    """Install hf_transfer and huggingface_hub."""
    print("  Installing hf_transfer and huggingface_hub...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "hf_transfer", "huggingface_hub"],
        timeout=300,
    )
    return result.returncode == 0


def download_model_hf(
    repo: str = DEFAULT_HF_REPO,
    filename: str = DEFAULT_HF_FILE,
    local_dir: str = DEFAULT_MODELS_DIR,
) -> Optional[str]:
    """Download a GGUF file from HuggingFace using huggingface-cli.

    Returns the local file path on success, or None on failure.
    """
    os.makedirs(local_dir, exist_ok=True)
    dest = os.path.join(local_dir, filename)

    if os.path.isfile(dest):
        print(f"  Model already exists at {dest} — skipping download.")
        return dest

    hf_cli = _find_hf_cli()
    if not hf_cli:
        print("  huggingface-cli not found.")
        return None

    env = {**os.environ, "HF_HUB_ENABLE_HF_TRANSFER": "1"}
    cmd = [hf_cli, "download", repo, filename, "--local-dir", local_dir]
    print(f"  $ {' '.join(cmd)}")
    print("  (HF_HUB_ENABLE_HF_TRANSFER=1)\n")

    result = subprocess.run(cmd, env=env)
    if result.returncode == 0 and os.path.isfile(dest):
        return dest

    print(f"  Download failed (exit code {result.returncode}).")
    return None


def install_llama_cpp_python() -> bool:
    """Install llama-cpp-python."""
    print("  Installing llama-cpp-python...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "llama-cpp-python"],
        timeout=600,
    )
    return result.returncode == 0


def update_config_llamacpp(
    model_path: str,
    n_ctx: int = 4096,
    n_gpu_layers: int = -1,
    config_path: str = DEFAULT_CONFIG,
) -> None:
    """Write/update config.ini to use the llamacpp provider."""
    cfg = configparser.ConfigParser()
    if os.path.exists(config_path):
        cfg.read(config_path)

    cfg["DEFAULT"]["default_provider"] = "llamacpp"

    if "llamacpp" not in cfg:
        cfg["llamacpp"] = {}
    cfg["llamacpp"]["model_path"] = model_path
    cfg["llamacpp"]["n_ctx"] = str(n_ctx)
    cfg["llamacpp"]["n_gpu_layers"] = str(n_gpu_layers)

    with open(config_path, "w") as f:
        cfg.write(f)


def run_setup_llamacpp(
    repo: str = DEFAULT_HF_REPO,
    filename: str = DEFAULT_HF_FILE,
    local_dir: str = DEFAULT_MODELS_DIR,
    n_ctx: int = 4096,
    n_gpu_layers: int = -1,
    config_path: str = DEFAULT_CONFIG,
) -> bool:
    """Full setup flow: install deps → download GGUF via HF → update config."""
    print("=== AIDM llama-cpp Setup ===\n")

    # 1. Ensure HuggingFace CLI is available
    print("[1/4] Checking HuggingFace CLI...")
    if not check_hf_hub():
        print("  HF CLI not found — installing...")
        if not install_hf_hub():
            print("  Failed to install. Install manually:")
            print("    pip install hf_transfer huggingface_hub")
            return False
        if not check_hf_hub():
            print("  HF CLI still not found after install.")
            print("  Try manually: pip install hf_transfer huggingface_hub")
            return False
    print(f"  HF CLI ready: {_find_hf_cli()}")

    # 2. Ensure llama-cpp-python is installed
    print("[2/4] Checking llama-cpp-python...")
    try:
        import llama_cpp  # noqa: F401
        print("  llama-cpp-python already installed.")
    except ImportError:
        print("  llama-cpp-python not found — installing...")
        if not install_llama_cpp_python():
            print("  Failed to install llama-cpp-python. Install manually:")
            print("    pip install llama-cpp-python")
            return False
        print("  llama-cpp-python installed.")

    # 3. Download model
    print(f"[3/4] Downloading {filename} from {repo}...")
    model_path = download_model_hf(repo, filename, local_dir)
    if not model_path:
        return False
    print(f"  Model ready at {model_path}")

    # 4. Update config
    print(f"[4/4] Updating {config_path}...")
    update_config_llamacpp(model_path, n_ctx, n_gpu_layers, config_path)
    print("  Config saved.")

    print("\n=== Setup complete! ===")
    print(f"  Provider   : llamacpp")
    print(f"  Model      : {model_path}")
    print(f"  Context    : {n_ctx}")
    print(f"  GPU layers : {n_gpu_layers} (all)\n")

    return True


def main():
    """CLI entry point for standalone usage: python -m aidm.setup"""
    import argparse

    parser = argparse.ArgumentParser(description="Set up a local LLM for AIDM")
    sub = parser.add_subparsers(dest="backend", help="Backend to set up")

    # --- ollama sub-command (legacy default) ---
    ol = sub.add_parser("ollama", help="Set up with Ollama server")
    ol.add_argument(
        "--model", "-m", default=DEFAULT_MODEL,
        help=f"Ollama model tag to pull (default: {DEFAULT_MODEL})",
    )
    ol.add_argument("--host", default=DEFAULT_HOST, help=f"Ollama server URL (default: {DEFAULT_HOST})")
    ol.add_argument("--config", "-c", default=DEFAULT_CONFIG, help="Config file path")

    # --- llamacpp sub-command (new default) ---
    lc = sub.add_parser("llamacpp", help="Set up with llama-cpp-python + HuggingFace download")
    lc.add_argument("--repo", default=DEFAULT_HF_REPO, help=f"HuggingFace repo (default: {DEFAULT_HF_REPO})")
    lc.add_argument("--filename", default=DEFAULT_HF_FILE, help=f"GGUF filename (default: {DEFAULT_HF_FILE})")
    lc.add_argument("--models-dir", default=DEFAULT_MODELS_DIR, help="Local directory for models")
    lc.add_argument("--n-ctx", type=int, default=4096, help="Context window size")
    lc.add_argument("--n-gpu-layers", type=int, default=-1, help="GPU layers (-1 = all)")
    lc.add_argument("--config", "-c", default=DEFAULT_CONFIG, help="Config file path")

    args = parser.parse_args()

    if args.backend == "ollama":
        success = run_setup(
            model=args.model, host=args.host,
            config_path=args.config,
        )
    elif args.backend == "llamacpp":
        success = run_setup_llamacpp(
            repo=args.repo, filename=args.filename,
            local_dir=args.models_dir, n_ctx=args.n_ctx,
            n_gpu_layers=args.n_gpu_layers,
            config_path=args.config,
        )
    else:
        # Default to llamacpp if no sub-command given
        success = run_setup_llamacpp(config_path=DEFAULT_CONFIG)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
