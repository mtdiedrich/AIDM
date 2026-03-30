# AI Dungeon Master

A flexible, provider-agnostic AI-powered text RPG system with true dice mechanics and persistent game state.

## Features

- **Multiple LLM Providers**: Works with Claude, OpenAI, Ollama, LM Studio, or any custom provider
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
│   └── config.py          # Configuration management
├── examples/              # Example implementations
│   ├── ai_dm.py          # Basic framework example
│   └── ai_integration.py  # Integration examples
├── docs/                  # Documentation
│   └── SAVE_LOAD_GUIDE.md
├── run.py                 # Main entry point (recommended)
├── quick_start.py         # Fast startup script
├── universal_dm_config.py # Config-based startup
├── config.ini.example     # Configuration template
├── requirements.txt       # Python dependencies
├── pyproject.toml        # Project metadata
└── README.md             # This file
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Provider

```bash
# Copy the example config
cp config.ini.example config.ini

# Edit config.ini and set your preferred provider
# Set default_provider = openai, claude, ollama, lmstudio, or mock
# Add your API keys if using Claude or OpenAI
```

### 3. Run the Game

**Fastest method (uses config.ini):**
```bash
python run.py
```

**Alternative methods:**
```bash
# Quick start with config
python quick_start.py

# With command line options
python universal_dm_config.py --provider claude

# Interactive provider selection
python universal_dm_config.py --interactive  
python universal_dm_config.py --provider openai

# Use local Ollama
python universal_dm_config.py --provider ollama

# Test without AI
python universal_dm_config.py --provider mock
```

### Method 3: Config File

```bash
cp config.ini.example config.ini
# Edit config.ini with your settings
python universal_dm_config.py
```

### Provider Setup

See `PROVIDERS.md` for detailed setup instructions for each provider:
- **Claude** - High quality, requires API key
- **OpenAI** - Various models (GPT-4, GPT-3.5), requires API key  
- **Ollama** - Free local models, no API key
- **LM Studio** - Free local models with GUI
- **Mock** - No AI, for testing mechanics

### Basic Framework (No AI)

Test the framework without AI integration:

```bash
python ai_dm.py
```

This gives you character creation, dice rolling, and state management with placeholder AI responses.

### Commands

In-game commands:
- Type actions naturally (placeholder response for now)
- `roll d20` - Roll a d20
- `roll 3d6+2` - Roll 3d6 with +2 modifier
- `check strength 15` - Make a strength check against DC 15
- `character` - View character sheet
- `state` - View game state
- `quit` - Save and exit

## Architecture

### Multi-Provider System
The system uses a provider abstraction that allows any LLM to act as DM:

```python
from llm_providers import create_provider
from universal_dm import UniversalDM

# Use any provider
provider = create_provider('claude')  # or 'openai', 'ollama', etc.
dm = UniversalDM(provider)
dm.run()
```

Providers implement a simple interface:
```python
class LLMProvider(ABC):
    def generate(self, system_prompt: str, user_message: str, 
                 conversation_history: Optional[List[Dict]] = None) -> str:
        pass
```

### Available Providers

**Cloud Providers:**
- `ClaudeProvider` - Anthropic Claude API
- `OpenAIProvider` - OpenAI GPT models

**Local Providers:**  
- `OllamaProvider` - Local Ollama models
- `LMStudioProvider` - LM Studio local server

**Testing:**
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
from llm_providers import LLMProvider

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

# Use it
from universal_dm import UniversalDM
provider = MyCustomProvider(api_key="...")
dm = UniversalDM(provider)
dm.run()
```

Then add it to `create_provider()` in `llm_providers.py` for easy access.

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
