# Drop CLI — Web-only Entry Point

## Goal

Remove the CLI game loop and consolidate to a single `run.py` that starts the web UI, keeping the `--setup` flag for Ollama setup.

## Current behavior

- `run.py` — CLI entry point: loads config, creates provider, calls `dm.run()` (interactive stdin loop). Has `--setup` flag.
- `run_web.py` — Web entry point: starts FastAPI/uvicorn server. Has `--host`/`--port`.
- `dm.py` contains ~180 lines of CLI-only methods: `run()`, `game_loop()`, `get_response_streamed()`, `get_response()`, `_get_response_inner()`, `_stream_generate()`.
- `pyproject.toml` has two console_scripts: `aidm` → `run:main`, `aidm-web` → `run_web:main`.
- `docs/SAVE_LOAD_GUIDE.md` is entirely about the CLI workflow with references to a non-existent `universal_dm.py`.

## Target behavior

- Single `run.py` that starts the web server (uvicorn). Supports `--setup`, `--host`, `--port`.
- `run_web.py` deleted.
- CLI-only methods removed from `dm.py`.
- Unused imports (`sys`, `threading`, `time`) removed from `dm.py`.
- Single console_script `aidm` → `run:main`.
- `docs/SAVE_LOAD_GUIDE.md` deleted (obsolete).

## Files to change

| File | Action | Summary |
|------|--------|---------|
| `run.py` | **Rewrite** | Merge web entry point + `--setup` flag. Delete CLI game loop code. |
| `run_web.py` | **Delete** | Redundant. |
| `aidm/dm.py` | **Edit** | Remove `_stream_generate`, `get_response`, `get_response_streamed`, `_get_response_inner`, `run`, `game_loop`. Remove `import sys, threading, time`. |
| `pyproject.toml` | **Edit** | Remove `aidm-web` script. |
| `README.md` | **Edit** | Remove CLI-mode section, update run instructions to web-only. |
| `docs/SAVE_LOAD_GUIDE.md` | **Delete** | Entirely CLI-focused and references non-existent file. |

## Step-by-step instructions

1. **Rewrite `run.py`**: Combine `--setup` from current `run.py` with `--host`/`--port` + uvicorn launch from `run_web.py`. Remove all CLI game code.
2. **Delete `run_web.py`**.
3. **Edit `aidm/dm.py`**: Remove methods `_stream_generate`, `get_response`, `get_response_streamed`, `_get_response_inner`, `run`, `game_loop` (lines ~227–680). Remove `import sys`, `import threading`, `import time` from top.
4. **Edit `pyproject.toml`**: Remove `aidm-web = "run_web:main"` line.
5. **Edit `README.md`**: Replace CLI instructions with web-only instructions. Remove references to `run_web.py`.
6. **Delete `docs/SAVE_LOAD_GUIDE.md`**.

## Test plan

| Test | File | Expected |
|------|------|----------|
| Existing 33 tests still pass | All test files | Green |

No new tests needed — this is a deletion/consolidation change.

## Out of scope

- Changing the web UI itself.
- Modifying `web.py` or `get_response_events()`.
- Adding new features.
