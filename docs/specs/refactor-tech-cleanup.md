# Spec: Tech Stack Cleanup

## Goal

Remove redundant LLM providers and heavy dependencies, fix async blocking, and improve configuration — reducing ~300 lines of code and 4 dependencies while making the server non-blocking.

## Current Behavior

- `OllamaProvider` hand-rolls HTTP with `requests` against `/api/chat` (~80 lines).
- `LMStudioProvider` hand-rolls HTTP with `requests` against `/v1/chat/completions` (~80 lines).
- `LlamaCppProvider` wraps `llama-cpp-python` for direct GGUF loading (~60 lines).
- All three duplicate logic already available via the `openai` Python SDK (which supports arbitrary `base_url`).
- `llama-cpp-python`, `huggingface-hub`, and `hf_transfer` are heavy/fragile dependencies for a feature better served by Ollama.
- `requirements.txt` duplicates `pyproject.toml`.
- `requires-python = ">=3.8"` is wrong; code uses `X | Y` union syntax (3.10+).
- `max_tokens=1000` is hardcoded in every provider.
- `web.py` runs blocking sync generators on the async event loop.
- WebSocket messages have no input validation.

## Target Behavior

1. **Consolidated providers:** `OpenAIProvider` accepts an optional `base_url` param. Ollama and LM Studio configs just create an `OpenAIProvider` with the appropriate `base_url` and a dummy API key.
2. **No `llama-cpp-python`/`huggingface-hub`/`hf_transfer` deps.** Users wanting local inference use Ollama.
3. **No `requests` dep.** `setup.py` uses `urllib` for its HTTP calls instead.
4. **Single dep file:** `requirements.txt` deleted.
5. **Honest Python version:** `requires-python = ">=3.10"`.
6. **Configurable `max_tokens`:** Read from `config.ini` per-provider section (key: `max_tokens`, default: `1000`).
7. **Non-blocking web server:** `dm.get_response_events` already uses `run_in_executor` for the sync stream — verify this is correct and the DM init is also non-blocking.
8. **WebSocket validation:** Length limits on `name` (50 chars), `description` (500), `text` (2000), `location`/`location_description` (200).

## Files to Change

| File | Action | Summary |
|------|--------|---------|
| `aidm/llm_providers.py` | **Major edit** | Delete `OllamaProvider`, `LMStudioProvider`, `LlamaCppProvider`. Add `base_url`/`max_tokens` to `OpenAIProvider`. Add `max_tokens` to `ClaudeProvider`. Update factory. |
| `aidm/config.py` | **Edit** | Map `ollama`/`lmstudio` config sections to `OpenAIProvider` with `base_url`. Remove `llamacpp` case. Read `max_tokens` from each section. |
| `aidm/web.py` | **Edit** | Wrap `_get_dm()` / `_create_dm()` calls in `asyncio.to_thread`. Add input validation on WebSocket messages. |
| `aidm/setup.py` | **Edit** | Remove all `llamacpp`/HF functions. Replace `requests` usage with `urllib.request`. Remove `import requests`. |
| `aidm/__init__.py` | **Edit** | Remove `OllamaProvider`, `LMStudioProvider` from exports. |
| `config.ini` | **Edit** | Change `default_provider` to `ollama`. Remove `[llamacpp]` section. Add `max_tokens` examples. |
| `pyproject.toml` | **Edit** | Remove `llama-cpp-python`, `huggingface-hub`, `hf_transfer`, `requests`. Fix `requires-python`. Update `target-version`. |
| `requirements.txt` | **Delete** | Redundant with `pyproject.toml`. |
| `README.md` | **Edit** | Remove references to `requirements.txt`, `LlamaCppProvider`, `LMStudioProvider` class names. Update quick-start to use `pip install .`. |
| `tests/test_setup.py` | **Edit** | Update mocks from `requests` to `urllib`. |

## Step-by-Step Instructions

### 1. `aidm/llm_providers.py`
- Add `base_url: Optional[str] = None` and `max_tokens: int = 1000` params to `OpenAIProvider.__init__`.
- Pass `base_url` to `openai.OpenAI(base_url=...)` in `_ensure_client`.
- For `_ensure_client`: if `base_url` is set and no `api_key`, use a dummy key (`"not-needed"`).
- Use `self.max_tokens` in `generate()` and `generate_stream()` instead of hardcoded 1000.
- Add `max_tokens: int = 1000` to `ClaudeProvider.__init__`; use it in `generate()`.
- Delete `OllamaProvider` class entirely.
- Delete `LMStudioProvider` class entirely.
- Delete `LlamaCppProvider` class entirely.
- Update `create_provider` factory: remove `ollama`, `lmstudio`, `llamacpp` keys (only `claude`, `openai`, `mock` remain).
- Update `list_available_providers` to remove deleted classes.

### 2. `aidm/config.py`
- For `ollama`: create `OpenAIProvider` with `base_url=f"{host}/v1"`, `api_key="ollama"`, `model=...`, `max_tokens=...`.
- For `lmstudio`: create `OpenAIProvider` with `base_url=f"{host}/v1"`, `api_key="lm-studio"`, `model=...`, `max_tokens=...`.
- Remove entire `llamacpp` branch.
- Read `max_tokens` from each config section with fallback of 1000.

### 3. `aidm/web.py`
- Wrap `_create_dm()` call in `asyncio.to_thread` so model-loading doesn't block the loop.
- Add a `_validate_ws_field(value, max_len, default)` helper.
- Apply validation to `name`, `description`, `text`, `location`, `location_description` fields.

### 4. `aidm/setup.py`
- Replace `import requests` with `import urllib.request`, `import urllib.error`.
- Rewrite `check_ollama_running` to use `urllib.request.urlopen`.
- Rewrite `model_exists` to use `urllib`.
- Rewrite `pull_model` to use `urllib`.
- Delete all functions from `_find_hf_cli` through `run_setup_llamacpp`.
- Update `main()` to remove `llamacpp` sub-command; make `ollama` the default.
- Remove constants: `DEFAULT_HF_REPO`, `DEFAULT_HF_FILE`, `DEFAULT_MODELS_DIR`.
- Remove `import shutil`.

### 5. `aidm/__init__.py`
- Remove `OllamaProvider`, `LMStudioProvider` from imports and `__all__`.

### 6. `config.ini`
- Change `default_provider = llamacpp` to `default_provider = ollama`.
- Remove `[llamacpp]` section.
- Add `max_tokens = 1000` to each provider section.

### 7. `pyproject.toml`
- Remove `"llama-cpp-python>=0.3.0"`, `"huggingface-hub>=0.20.0"`, `"hf_transfer"`, `"requests>=2.31.0"` from dependencies.
- Change `requires-python = ">=3.8"` to `requires-python = ">=3.10"`.
- Change `target-version` to `['py310', 'py311', 'py312']`.

### 8. Delete `requirements.txt`.

### 9. `README.md`
- Replace `pip install -r requirements.txt` with `pip install -e .`.
- Remove `LMStudioProvider` from the Available Providers listing (keep LM Studio as a config option).
- Remove LlamaCppProvider mention.
- Update project structure to remove `requirements.txt`.

### 10. `tests/test_setup.py`
- Change `"aidm.setup.requests.get"` patches to `"aidm.setup.urllib.request.urlopen"`.
- Change `"aidm.setup.requests.post"` patches to `"aidm.setup.urllib.request.urlopen"` / `"aidm.setup.urllib.request.Request"`.
- Update mock return values to match urllib patterns.

## Test Plan

| Test | File | Expected Result |
|------|------|-----------------|
| OpenAIProvider accepts `base_url` and passes it to client | `tests/test_providers.py` | Provider `.client` created with custom base_url |
| OpenAIProvider uses dummy key when `base_url` set and no key | `tests/test_providers.py` | Client created without error |
| `max_tokens` flows from config to provider | `tests/test_providers.py` | Provider has `max_tokens` matching config value |
| `create_provider_from_config` maps `ollama` to OpenAIProvider with correct base_url | `tests/test_providers.py` | Returns OpenAIProvider, base_url ends with `/v1` |
| `create_provider_from_config` maps `lmstudio` to OpenAIProvider | `tests/test_providers.py` | Returns OpenAIProvider, base_url correct |
| WebSocket rejects oversized name | `tests/test_web_validation.py` | Name truncated to 50 chars |
| WebSocket rejects oversized action text | `tests/test_web_validation.py` | Text truncated to 2000 chars |
| `check_ollama_running` works with urllib | `tests/test_setup.py` | Existing tests pass with updated mocks |

## Out of Scope

- Migrating `config.ini` to TOML format (low priority, works fine).
- Changing the frontend (`index.html`).
- Modifying game logic in `dm.py` beyond what's needed for `max_tokens`.
- Adding new LLM providers.
