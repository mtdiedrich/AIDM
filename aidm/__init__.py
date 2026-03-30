"""
AI Dungeon Master
A flexible, provider-agnostic AI-powered text RPG system
"""

__version__ = "1.0.0"

from .dm import UniversalDM
from .gamestate import GameState, Character
from .dice import DiceRoller
from .llm_providers import (
    LLMProvider,
    ClaudeProvider,
    OpenAIProvider,
    OllamaProvider,
    LMStudioProvider,
    MockProvider,
    create_provider
)

__all__ = [
    'UniversalDM',
    'GameState',
    'Character',
    'DiceRoller',
    'LLMProvider',
    'ClaudeProvider',
    'OpenAIProvider',
    'OllamaProvider',
    'LMStudioProvider',
    'MockProvider',
    'create_provider',
]
