"""
Configuration management for AI Dungeon Master
"""

import configparser
import os
from typing import Optional

DEFAULT_MODEL = "qwen3.5:9b-q8_0"


def load_config(config_file: str = 'config.ini') -> Optional[configparser.ConfigParser]:
    """Load configuration from file"""
    config = configparser.ConfigParser()
    
    if os.path.exists(config_file):
        config.read(config_file)
        return config
    
    return None


def get_models(config: Optional[configparser.ConfigParser] = None) -> dict:
    """Return the alias→model mapping from [models], excluding the 'default' key."""
    if config and config.has_section("models"):
        return {k: v for k, v in config.items("models") if k != "default"}
    return {}


def resolve_model(config: Optional[configparser.ConfigParser] = None, name: Optional[str] = None) -> str:
    """Resolve a model name.

    If *name* is given, look it up as an alias in [models]; if not found use it
    directly (assumed to be a full Ollama model name).
    If *name* is None, use the ``default`` key in [models] and resolve that.
    """
    models = get_models(config)
    if name is None:
        # read the default alias
        default_alias = ""
        if config and config.has_section("models"):
            default_alias = config.get("models", "default", fallback="")
        if default_alias and default_alias in models:
            return models[default_alias]
        if default_alias:
            return default_alias  # treat as direct model name
        # legacy: fall back to [ollama] model key
        if config and config.has_option("ollama", "model"):
            return config.get("ollama", "model")
        return DEFAULT_MODEL

    # explicit name — resolve alias or pass through
    if name in models:
        return models[name]
    return name


def get_ollama_settings(config: Optional[configparser.ConfigParser] = None,
                        model: Optional[str] = None) -> dict:
    """Return host, model, max_tokens (with defaults).

    *model* overrides the configured default — it can be an alias from [models]
    or a full Ollama model name.
    """
    host = "http://localhost:11434"
    max_tokens = 1000

    if config and config.has_section("ollama"):
        host = config.get("ollama", "host", fallback=host)
        max_tokens = config.getint("ollama", "max_tokens", fallback=max_tokens)

    resolved = resolve_model(config, name=model)
    return {"host": host, "model": resolved, "max_tokens": max_tokens}


def get_save_file(config: Optional[configparser.ConfigParser] = None) -> str:
    """Get the save file path from config or default"""
    if config and config.has_option('game', 'save_file'):
        return config.get('game', 'save_file')
    return 'gamestate.json'
