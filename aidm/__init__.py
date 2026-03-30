"""
AI Dungeon Master
A local AI-powered text RPG system (Ollama)
"""

__version__ = "1.0.0"

from .dm import UniversalDM
from .gamestate import GameState, Character
from .dice import DiceRoller

__all__ = [
    'UniversalDM',
    'GameState',
    'Character',
    'DiceRoller',
]
