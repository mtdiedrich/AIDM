# Spec: Automated Ollama Setup

## Goal
Add a `setup` module and CLI command that checks for Ollama, pulls a specified model, configures `config.ini`, and optionally launches the game — all from code.

## Current Behavior
Users must manually install Ollama, run `ollama pull`, edit `config.ini`, and then run the game.

## Target Behavior
Running `python run.py --setup` (or `python -m aidm.setup`) will:
1. Check if Ollama CLI is installed and the server is reachable.
2. If the server isn't running, attempt to start it.
3. Pull the requested model (default: `qwen3.5:9b-q8_0`).
4. Update `config.ini` to set `default_provider = ollama` and `model = <model>`.
5. Optionally launch the game after setup completes.

## Files to Change
| File | Action | Summary |
|------|--------|---------|
| `aidm/setup.py` | Create | Core setup logic: check Ollama, pull model, update config |
| `tests/test_setup.py` | Create | Unit tests for setup functions |
| `run.py` | Modify | Add `--setup` flag |

## Step-by-Step

### 1. Create `aidm/setup.py`
- `check_ollama_installed() -> bool` — runs `ollama --version`, returns True if exit code 0.
- `check_ollama_running(host) -> bool` — GET `{host}/api/tags`, returns True if 200.
- `start_ollama_server() -> bool` — starts `ollama serve` in background, waits up to 10s for it to respond.
- `pull_model(model, host) -> bool` — POST `{host}/api/pull` with `{"name": model}`, streams progress to stdout.
- `update_config(model, host, config_path) -> None` — reads/writes `config.ini` to set ollama model & default provider.
- `run_setup(model, host, config_path, launch) -> bool` — orchestrates all steps; if `launch=True`, calls `main()` from `run.py` at the end.

### 2. Create `tests/test_setup.py`
- Test `check_ollama_installed` with mocked subprocess.
- Test `check_ollama_running` with mocked requests.
- Test `pull_model` with mocked requests.
- Test `update_config` writing correct ini.

### 3. Modify `run.py`
- Add `--setup` and `--model` args via argparse.
- When `--setup` is passed, call `run_setup()` then optionally continue to game.

## Test Plan
| Test | Expected |
|------|----------|
| `test_check_installed_success` | Returns True when subprocess exits 0 |
| `test_check_installed_missing` | Returns False when FileNotFoundError |
| `test_check_running_up` | Returns True when GET returns 200 |
| `test_check_running_down` | Returns False on ConnectionError |
| `test_pull_model_success` | Returns True on 200 response |
| `test_pull_model_failure` | Returns False on error response |
| `test_update_config_new` | Creates correct ini from scratch |
| `test_update_config_existing` | Updates existing ini preserving other sections |

## Out of Scope
- Installing Ollama itself (we detect and guide, not auto-install).
- Downloading GGUF from HuggingFace directly.
