# AI Dungeon Master

A flexible, provider-agnostic AI-powered text RPG system with true dice mechanics and persistent game state.

## Features

- **Local LLM**: Runs entirely on your machine via Ollama (no API keys needed)
- **Fast Startup**: Optimized lazy initialization for instant game start
- **True Random Dice Rolling**: Uses Python's random module for genuine randomness
- **Character Management**: Create and track PCs and NPCs with stats, HP, inventory, and motivations
- **Persistent State**: Game state saved to JSON, resume anytime
- **Flexible Dice System**: d20 checks, multi-dice rolls, modifiers
- **Player-Controlled Opening**: You describe the starting setting before the adventure begins

## Project Structure

```
AIDM/
├── aidm/                   # Main package
│   ├── __init__.py        # Package initialization
│   ├── dm.py              # Core DM class
│   ├── dice.py            # Dice rolling engine
│   ├── gamestate.py       # Character and world state
│   ├── llm_providers.py   # LLM provider abstraction
│   ├── config.py          # Configuration management
│   ├── setup.py           # Ollama setup helpers
│   └── web.py             # FastAPI web UI backend
├── docs/                  # Documentation
├── tests/                 # Unit tests
├── run.py                 # Entry point (web server)
├── config.ini             # Runtime configuration
├── pyproject.toml         # Project metadata & dependencies
└── README.md              # This file
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -e .
```

### 2. Configure Provider

```bash
# Copy the example config
cp config.ini.example config.ini

# Edit config.ini and set your preferred provider
# Set default_provider = ollama, lmstudio, or mock
```

### 3. Run the Game

```bash
python run.py                              # Start on http://localhost:8000
python run.py --port 3000                  # Custom port
python run.py --setup                      # Set up Ollama first, then start
python run.py --setup -m qwen3.5:9b-q8_0   # Specify model
python run.py --setup --gguf https://huggingface.co/.../model-Q8_0.gguf  # Import a HuggingFace GGUF
```

### Available Providers

- **Ollama** - Free local models, no API key (default)
- **LM Studio** - Free local models with GUI
- **Mock** - No AI, for testing mechanics

## Architecture

### Multi-Provider System
The system uses a provider abstraction that allows any LLM to act as DM:

Providers implement a simple interface:
```python
class LLMProvider(ABC):
    def generate(self, system_prompt: str, user_message: str, 
                 conversation_history: Optional[List[Dict]] = None) -> str:
        pass
```

### Available Providers

- `OllamaProvider` - Talks directly to Ollama/LM Studio via native HTTP API (no SDK needed)
- `MockProvider` - No AI, for testing mechanics

See `llm_providers.py` for implementation details.

### Dice System
The `DiceRoller` class provides:
- `roll(sides, count, modifier)` - Roll any dice
- `d20(modifier)` - Quick d20 roll
- `check(modifier, dc)` - Ability check with success/failure

### Character System
Characters have:
- Six stats (strength, dexterity, constitution, intelligence, wisdom, charisma)
- HP tracking
- Inventory
- Motivations and relationships
- Notes/history

### Game State
Manages:
- All characters (PCs and NPCs)
- Locations with descriptions, NPCs, items, exits
- Quest log
- Action history with timestamps
- Auto-save to JSON

### AI Integration
The `AIDungeonMaster` class:
- Builds context for the AI (game state + player action)
- Parses AI responses for game commands
- Executes dice rolls when requested
- Updates game state based on outcomes

## Example: Adding a Custom Provider

Want to integrate a different LLM? Just implement the `LLMProvider` interface:

```python
from aidm.llm_providers import LLMProvider

class MyCustomProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Initialize your LLM client
        
    def generate(self, system_prompt: str, user_message: str,
                 conversation_history: Optional[List[Dict]] = None) -> str:
        # Call your LLM API
        # Return the response text
        pass
        
    def is_available(self) -> bool:
        return self.api_key is not None
        
    def get_name(self) -> str:
        return "My Custom LLM"

```

Then add it to `create_provider()` in `aidm/llm_providers.py` for easy access.

## Customization

### Different Dice Systems
Modify `DiceRoller` to support:
- Percentile rolls
- Advantage/disadvantage (roll twice, take best/worst)
- Exploding dice
- Different DC calculation methods

### Different Stats
Edit the default stats in `Character.__init__()` to use:
- Different attribute names
- More or fewer attributes
- Different scales (3-18, 1-10, etc.)

### Game Mechanics
Add new methods to `GameState`:
- Experience/leveling
- Currency system
- Crafting
- Time tracking
- Weather/environment

## Save Format

Game state is saved as JSON:
```json
{
  "characters": {
    "Thorin": {
      "name": "Thorin",
      "stats": {"strength": 14, ...},
      "hp": 23,
      "max_hp": 23,
      "inventory": ["sword", "rope"],
      "is_player": true
    }
  },
  "locations": {...},
  "history": [...],
  "quest_log": [...]
}
```

## Extending the System

### Adding New Providers

1. Create a new class in `llm_providers.py` extending `LLMProvider`
2. Implement `generate()`, `is_available()`, and `get_name()`
3. Add to `create_provider()` factory function

### Adding Game Mechanics

Edit `gamestate.py` to add:
- Experience/leveling system
- Currency tracking
- Crafting system
- Time/calendar
- Reputation system
- Faction relationships

### Custom Dice Systems

Modify `dice.py` to add:
- Advantage/disadvantage
- Exploding dice
- Dice pools
- Different success mechanics

## License

This is a framework/example. Use and modify as needed.
