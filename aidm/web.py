"""
FastAPI web backend for AI Dungeon Master.
Serves the chat UI and handles WebSocket gameplay.
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import load_config, get_ollama_settings
from .dm import UniversalDM
from .gamestate import Character, GameState

log = logging.getLogger("aidm.web")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="AI Dungeon Master")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- Input validation ---

MAX_NAME_LEN = 50
MAX_DESC_LEN = 500
MAX_TEXT_LEN = 2000
MAX_LOC_LEN = 200


def _validate_ws_field(value, max_len: int, default: str = "") -> str:
    """Sanitise a WebSocket input field: strip, truncate, or return default."""
    if not value or not isinstance(value, str):
        return default
    value = value.strip()
    if not value:
        return default
    return value[:max_len]


def _create_dm() -> UniversalDM:
    """Create a DM instance from config.ini."""
    config = load_config()
    settings = get_ollama_settings(config)
    log.info("Creating DM: %s @ %s", settings["model"], settings["host"])
    t0 = time.time()
    dm = UniversalDM(**settings)
    log.info("DM created in %.1fs: %s", time.time() - t0, dm.get_display_name())
    return dm


# DM instance — created lazily on first request so the server starts immediately
dm: UniversalDM | None = None


async def _get_dm() -> UniversalDM:
    global dm
    if dm is None:
        log.info("First request — initializing DM (model will load now)...")
        dm = await asyncio.to_thread(_create_dm)
        log.info("DM ready.")
    return dm


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok", "dm_loaded": dm is not None}


def _state_snapshot(game: UniversalDM) -> dict:
    """Return a JSON-safe snapshot of the current game state."""
    return {
        "characters": {
            name: char.to_dict() for name, char in game.state.characters.items()
        },
        "location": game.state.current_location,
        "in_combat": game.state.in_combat,
        "session": game.state.session_number,
        "has_save": os.path.exists(game.state.filename),
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    log.info("WebSocket connected")
    game = await _get_dm()

    # Send initial state
    await ws.send_json({"type": "state", "data": _state_snapshot(game)})

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")
            log.info("Received message: %s", msg_type)

            if msg_type == "load_game":
                if game.state.load():
                    await ws.send_json({"type": "state", "data": _state_snapshot(game)})
                    await ws.send_json({"type": "system", "text": "Game loaded."})
                else:
                    await ws.send_json({"type": "system", "text": "No saved game found."})

            elif msg_type == "new_game":
                name = _validate_ws_field(msg.get("name"), MAX_NAME_LEN, "Hero")
                desc = _validate_ws_field(msg.get("description"), MAX_DESC_LEN)
                # Reset DM state
                game.state = GameState()
                game.conversation = []
                game.turns = []
                player = Character(
                    name,
                    stats={"strength": 12, "dexterity": 14, "constitution": 13,
                           "intelligence": 10, "wisdom": 11, "charisma": 12},
                    hp=23, max_hp=23, is_player=True, description=desc,
                )
                game.state.add_character(player)
                location = _validate_ws_field(msg.get("location"), MAX_LOC_LEN, "Unknown Lands")
                location_desc = _validate_ws_field(
                    msg.get("location_description"), MAX_LOC_LEN,
                    "A mysterious place where your adventure begins.",
                )
                game.state.add_location(location, location_desc, npcs=[], exits={})
                game.state.current_location = location
                await ws.send_json({"type": "state", "data": _state_snapshot(game)})
                await ws.send_json({"type": "system", "text": f"New game started for {name}."})

            elif msg_type == "save":
                game.state.save()
                await ws.send_json({"type": "system", "text": "Game saved."})

            elif msg_type == "action":
                text = _validate_ws_field(msg.get("text"), MAX_TEXT_LEN)
                if not text:
                    continue
                # Stream events from the DM
                try:
                    async for event in game.get_response_events(text):
                        await ws.send_json(event)
                except Exception as e:
                    log.exception("Error in action handler")
                    await ws.send_json({"type": "error", "text": str(e)})

            elif msg_type == "edit_action":
                turn_index = msg.get("turn_index")
                new_text = _validate_ws_field(msg.get("text"), MAX_TEXT_LEN)
                if turn_index is None or not new_text:
                    continue
                game.truncate_to_turn(turn_index)
                try:
                    async for event in game.get_response_events(new_text):
                        await ws.send_json(event)
                except Exception as e:
                    log.exception("Error in edit_action handler")
                    await ws.send_json({"type": "error", "text": str(e)})

            elif msg_type == "edit_response":
                turn_index = msg.get("turn_index")
                new_text = _validate_ws_field(msg.get("text"), MAX_TEXT_LEN)
                if turn_index is None or not new_text:
                    continue
                game.edit_turn(turn_index, new_text)
                await ws.send_json({"type": "system", "text": "Response updated. History truncated."})
                await ws.send_json({"type": "state", "data": _state_snapshot(game)})

    except WebSocketDisconnect:
        log.info("WebSocket disconnected")
