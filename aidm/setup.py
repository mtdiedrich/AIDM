"""
Automated setup for running AIDM with a local Ollama model.

Handles: checking Ollama availability, pulling a model, updating config.ini.
"""

import configparser
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Optional


DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3.5:9b-q8_0"
DEFAULT_CONFIG = "config.ini"


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
        req = urllib.request.Request(f"{host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
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

    for _ in range(30):
        time.sleep(0.5)
        if check_ollama_running():
            return True
    return False


def model_exists(model: str, host: str = DEFAULT_HOST) -> bool:
    """Check if a model is already pulled locally."""
    try:
        req = urllib.request.Request(f"{host}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read())
                for m in data.get("models", []):
                    if m.get("name", "").startswith(model):
                        return True
    except Exception:
        pass
    return False


def pull_model(model: str, host: str = DEFAULT_HOST) -> bool:
    """Pull a model from the Ollama registry with streaming progress."""
    try:
        body = json.dumps({"name": model}).encode()
        req = urllib.request.Request(
            f"{host}/api/pull",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            if resp.status != 200:
                print(f"  Error: server returned {resp.status}")
                return False

            last_status = ""
            for line in resp:
                if not line.strip():
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

    except urllib.error.HTTPError as e:
        print(f"  Error: server returned {e.code} — {e.reason}")
        return False
    except Exception as e:
        print(f"  Error pulling model: {e}")
        return False


def update_config(
    model: str,
    host: str = DEFAULT_HOST,
    config_path: str = DEFAULT_CONFIG,
    alias: str = "",
) -> None:
    """Write/update config.ini so the game uses Ollama with the given model.

    The model is added to [models] with the given *alias* (or derived from the
    model name).  It is also set as the default.
    """
    cfg = configparser.ConfigParser()
    if os.path.exists(config_path):
        cfg.read(config_path)

    if "ollama" not in cfg:
        cfg["ollama"] = {}
    cfg["ollama"]["host"] = host
    # Remove legacy 'model' key if present
    if cfg.has_option("ollama", "model"):
        cfg.remove_option("ollama", "model")

    if "models" not in cfg:
        cfg["models"] = {}

    if not alias:
        # Derive a short alias: take the part before ':'  or the whole name
        alias = model.split(":")[0] if ":" in model else model
    cfg["models"][alias] = model
    cfg["models"]["default"] = alias

    with open(config_path, "w") as f:
        cfg.write(f)


def run_setup(
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    config_path: str = DEFAULT_CONFIG,
    gguf_url: Optional[str] = None,
) -> bool:
    """Full setup flow: check Ollama → start server → pull/import model → update config."""
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

    # 3. Pull or import model
    if gguf_url:
        print(f"[3/4] Importing GGUF from URL...")
        try:
            gguf_path = download_gguf(gguf_url)
        except Exception as e:
            print(f"  Download failed: {e}")
            return False

        filename = os.path.basename(gguf_path)
        model = derive_model_name(filename)
        print(f"  Importing as '{model}'...")
        if not import_gguf_to_ollama(gguf_path, model):
            print("  Failed to import GGUF into Ollama.")
            return False
        print("  Model imported.")
    else:
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
    update_config(model, host, config_path, alias=model.split(":")[0] if ":" in model else model)
    print("  Config saved.")

    print("\n=== Setup complete! ===")
    print(f"  Provider : ollama")
    print(f"  Model    : {model}")
    print(f"  Host     : {host}\n")

    return True


# ------------------------------------------------------------------
# GGUF import from HuggingFace
# ------------------------------------------------------------------

def normalize_hf_url(url: str) -> str:
    """Convert a HuggingFace blob URL to a direct download (resolve) URL."""
    return url.replace("/blob/main/", "/resolve/main/")


def derive_model_name(filename: str) -> str:
    """Derive a short Ollama model name from a GGUF filename."""
    stem = filename.rsplit(".", 1)[0] if filename.endswith(".gguf") else filename
    return stem.lower().replace("_", "-")


def download_gguf(url: str, dest_dir: str = "models") -> str:
    """Download a GGUF file from a URL to dest_dir. Returns local path."""
    url = normalize_hf_url(url)
    filename = url.rsplit("/", 1)[-1]
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, filename)

    # Check remote size via initial request
    req = urllib.request.Request(url, method="GET")
    resp = urllib.request.urlopen(req)
    remote_size = int(resp.headers.get("Content-Length", 0))

    # Skip if local file already matches
    if os.path.exists(dest_path) and os.path.getsize(dest_path) == remote_size:
        resp.close()
        print(f"  {filename} already exists ({remote_size:,} bytes) — skipping download.")
        return dest_path

    # Stream download
    downloaded = 0
    last_pct = -1
    with open(dest_path, "wb") as f:
        while True:
            chunk = resp.read(1024 * 1024)  # 1 MB chunks
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if remote_size:
                pct = int(downloaded / remote_size * 100)
                if pct != last_pct:
                    print(f"\r  Downloading {filename}: {pct}%", end="", flush=True)
                    last_pct = pct

    resp.close()
    print()  # newline after progress
    return dest_path


def import_gguf_to_ollama(gguf_path: str, model_name: str) -> bool:
    """Import a local GGUF file into Ollama via `ollama create`."""
    abs_path = os.path.abspath(gguf_path)
    modelfile_path = abs_path + ".Modelfile"

    try:
        with open(modelfile_path, "w") as f:
            f.write(f"FROM {abs_path}\n")

        result = subprocess.run(
            ["ollama", "create", model_name, "-f", modelfile_path],
            timeout=300,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  Error importing GGUF: {e}")
        return False
    finally:
        if os.path.exists(modelfile_path):
            os.remove(modelfile_path)


def main():
    """CLI entry point for standalone usage: python -m aidm.setup"""
    import argparse

    parser = argparse.ArgumentParser(description="Set up Ollama for AIDM")
    parser.add_argument(
        "--model", "-m", default=DEFAULT_MODEL,
        help=f"Ollama model tag to pull (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--gguf", default=None,
        help="HuggingFace GGUF URL to download and import",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Ollama server URL (default: {DEFAULT_HOST})")
    parser.add_argument("--config", "-c", default=DEFAULT_CONFIG, help="Config file path")

    args = parser.parse_args()

    if args.gguf and args.model != DEFAULT_MODEL:
        print("Error: --gguf and --model are mutually exclusive.")
        sys.exit(1)

    success = run_setup(
        model=args.model, host=args.host,
        config_path=args.config,
        gguf_url=args.gguf,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
