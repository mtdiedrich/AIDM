# Copilot Instructions — AI Dungeon Master (AIDM)

## Project Summary

AIDM is a local AI-powered text RPG (tabletop-style dungeon master) with a FastAPI/WebSocket web UI. It uses Ollama for LLM inference — no external API keys required. The codebase is small (~1,500 lines of Python + one HTML file) and has zero heavy dependencies beyond FastAPI/uvicorn.

- **Language:** Python 3.10+ (uses `X | Y` union syntax)
- **Framework:** FastAPI + uvicorn (web), WebSocket for gameplay
- **LLM Backend:** Ollama via native HTTP API (urllib, no SDK)
- **Build:** setuptools via `pyproject.toml`
- **Tests:** pytest
- **Linting:** black (line-length 100), flake8

## CRITICAL: Test-Driven Development (TDD)

All development MUST follow TDD. No exceptions.

1. **Red** — Write a failing test first for any new feature or bug fix
2. **Green** — Write the minimum code to make the test pass
3. **Refactor** — Clean up while keeping tests green

Run tests frequently: `python -m pytest tests/ -v`

Never write production code without a failing test that requires it.

## Build & Run Commands

Always run commands from the project root (`AIDM/`).

| Task | Command |
|------|---------|
| Install (editable) | `pip install -e ".[dev]"` |
| Run tests | `python -m pytest tests/ -v` |
| Run single test file | `python -m pytest tests/test_npc_creation.py -v` |
| Run single test | `python -m pytest tests/test_npc_creation.py::TestNpcParsingExisting::test_single_npc_parsed -v` |
| Lint (black) | `black --check aidm/ tests/ run.py` |
| Format (black) | `black aidm/ tests/ run.py` |
| Lint (flake8) | `flake8 aidm/ tests/ run.py` |
| Start web server | `python run.py` |
| Start with setup | `python run.py --setup` |

**Important:** Always install with `pip install -e ".[dev]"` before running tests or linting. The `[dev]` extra pulls in pytest, black, and flake8.

## Project Layout

```
AIDM/
├── run.py                  # Entry point — starts FastAPI/uvicorn web server
├── config.ini              # Runtime config (Ollama host, model aliases, game settings)
├── pyproject.toml          # Project metadata, dependencies, tool config (black, pytest)
├── aidm/                   # Main package
│   ├── __init__.py         # Exports: UniversalDM, GameState, Character, DiceRoller
│   ├── dm.py               # Core DM class — LLM interaction, command parsing, streaming
│   ├── dice.py             # DiceRoller — roll(), d20(), d6(), check()
│   ├── gamestate.py        # Character and GameState classes — persistence via JSON
│   ├── llm_providers.py    # LLMProvider ABC, OllamaProvider, MockProvider, create_provider()
│   ├── config.py           # Config loading, model alias resolution, get_ollama_settings()
│   ├── setup.py            # Ollama auto-setup: install, server start, model pull, GGUF import
│   ├── web.py              # FastAPI app, WebSocket handler, input validation
│   └── static/
│       └── index.html      # Single-page web UI (HTML + CSS + JS, all in one file)
├── tests/                  # Unit tests (pytest)
│   ├── test_npc_creation.py      # NPC parsing, creation, follow-up mechanism
│   ├── test_providers.py         # DM init, config helpers, model resolution
│   ├── test_setup.py             # Ollama setup: install, pull, config update, GGUF import
│   ├── test_think.py             # THINK command parsing and execution
│   ├── test_turns.py             # Turn-based system: turn order, thoughts, events
│   └── test_web_validation.py    # WebSocket input sanitization
├── docs/specs/             # Feature/refactor specs (design docs, not runnable)
└── models/                 # Local GGUF model files (gitignored, large)
```

## Architecture

### Core Flow
`run.py` → `uvicorn` → `aidm.web:app` (FastAPI) → WebSocket `/ws` → `UniversalDM`

### Key Classes
- **`UniversalDM`** (`dm.py`): The main game engine. Builds context, streams LLM responses, parses structured commands (ROLL, NPC, DAMAGE, HEAL, THINK), executes them against game state. Uses turn-based flow: planning call → per-character turns with optional NPC thinking → streamed narration. Has `get_response_events()` async generator for the web UI.
- **`GameState`** (`gamestate.py`): Manages characters, locations, quests, history, combat state. Persists to `gamestate.json`.
- **`Character`** (`gamestate.py`): PC/NPC with D&D-style stats, HP, inventory, motivations.
- **`DiceRoller`** (`dice.py`): True random dice rolls with modifiers and DC checks.
- **`LLMProvider`** (`llm_providers.py`): ABC with `generate()` and `generate_stream()`. Implementations: `OllamaProvider` (HTTP to Ollama), `MockProvider` (testing).

### Command Format (LLM ↔ Game Engine)
The DM class parses these structured commands from LLM output:
- `ROLL: [character] [stat] DC [number] | [reason]`
- `NPC: [name] | [description] | [motivation]`
- `DAMAGE: [character] [amount]`
- `HEAL: [character] [amount]`
- `THINK: [character] | [inner thought]`

### WebSocket Protocol
Messages are JSON with a `type` field. Inbound: `new_game`, `load_game`, `save`, `action`, `edit_action`, `edit_response`. Outbound: `loading`, `turn_start`, `thinking`, `thinking_done`, `token`, `narrative_replace`, `narrative_done`, `command`, `thought`, `state`, `system`, `error`, `done`.

### Turn-Based Flow
Each player action triggers a turn-based round:
1. `loading` — hourglass indicator
2. LLM planning call determines turn order (player first, then NPCs)
3. Per character: `turn_start` → (NPCs: `thinking` → LLM thought call → `thinking_done`) → streamed `token`s → `narrative_replace` → `narrative_done` → `command`s
4. `state` + `done` — finalize round

### Input Validation
All WebSocket string inputs go through `_validate_ws_field()` with length limits: name (50), description (500), text (2000), location (200).

## Testing Conventions

- Test files: `tests/test_*.py` (configured in `pyproject.toml`)
- Test classes: `Test*`, test functions: `test_*`
- Tests use `unittest.mock.patch` to mock Ollama/network calls — no live LLM needed
- Use `UniversalDM()` with default args for unit tests (it doesn't connect until a call is made)
- Use `MockProvider` or patch `generate_stream`/`generate_sync` for LLM-dependent tests
- Use `tmp_path` fixture for tests that write files (config, game saves)

## Configuration

`config.ini` has three sections:
- `[ollama]`: `host`, `max_tokens`
- `[models]`: `default` (alias name), plus alias→model mappings
- `[game]`: `save_file`, `auto_save`

Model resolution: `resolve_model()` in `config.py` checks aliases first, falls back to direct name, then legacy `[ollama] model` key, then hardcoded default `qwen3.5:9b-q8_0`.

## Dependencies

Runtime: `fastapi>=0.100.0`, `uvicorn[standard]>=0.20.0`, `websockets>=11.0`
Dev: `pytest>=7.0.0`, `black>=23.0.0`, `flake8>=6.0.0`

No external LLM SDK. All Ollama communication uses `urllib.request` from stdlib.

## Validation Checklist

Before considering any change complete:

1. `python -m pytest tests/ -v` — all tests pass
2. `black --check aidm/ tests/ run.py` — code is formatted
3. New features/fixes have corresponding tests written FIRST (TDD)
4. No new dependencies added without justification
5. WebSocket inputs validated through `_validate_ws_field()` with appropriate length limits

## Trust These Instructions

Use these instructions as the primary reference. Only search the codebase if the information here is incomplete or found to be incorrect.
