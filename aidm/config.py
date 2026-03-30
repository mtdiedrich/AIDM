"""
Configuration management for AI Dungeon Master
"""

import configparser
import os
from typing import Optional


def load_config(config_file: str = 'config.ini') -> Optional[configparser.ConfigParser]:
    """Load configuration from file"""
    config = configparser.ConfigParser()
    
    if os.path.exists(config_file):
        config.read(config_file)
        return config
    
    return None


def get_ollama_settings(config: Optional[configparser.ConfigParser] = None) -> dict:
    """Return host, model, max_tokens from the [ollama] section (with defaults)."""
    host = "http://localhost:11434"
    model = "qwen3.5:9b-q8_0"
    max_tokens = 1000

    if config and config.has_section("ollama"):
        host = config.get("ollama", "host", fallback=host)
        model = config.get("ollama", "model", fallback=model)
        max_tokens = config.getint("ollama", "max_tokens", fallback=max_tokens)

    return {"host": host, "model": model, "max_tokens": max_tokens}


def get_save_file(config: Optional[configparser.ConfigParser] = None) -> str:
    """Get the save file path from config or default"""
    if config and config.has_option('game', 'save_file'):
        return config.get('game', 'save_file')
    return 'gamestate.json'
