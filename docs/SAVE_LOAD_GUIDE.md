# Save/Load and CLI Usage Guide

## Command Line Arguments

### Basic Usage

```bash
# Interactive provider selection
python universal_dm.py

# Specify provider directly
python universal_dm.py --provider claude
python universal_dm.py --provider openai
python universal_dm.py --provider ollama
python universal_dm.py --provider mock

# Short form
python universal_dm.py -p claude
```

### Custom Save Files

```bash
# Use a specific save file
python universal_dm.py --save-file my_campaign.json
python universal_dm.py -s dragon_quest.json

# Combine with provider
python universal_dm.py -p claude -s my_adventure.json
```

### Help

```bash
python universal_dm.py --help
```

## Save/Load System

### Automatic Saving

The game **auto-saves after every action** to `gamestate.json` (or your specified save file).

You don't need to manually save unless you want to force a save at a specific moment.

### Loading Games

When you start the game, it automatically checks for an existing save:

```
============================================================
UNIVERSAL AI DUNGEON MASTER
============================================================
Using: Claude (claude-sonnet-4-20250514)

📁 Saved game found!

=== Game State (Session 2) ===

Current Location: Dark Forest
⚔️  IN COMBAT (Turn 3)
Combatants: Thorin, Goblin Warrior

Characters (2):
  - Thorin (PC) - HP: 18/23
  - Goblin Warrior (NPC) - HP: 5/12

Continue this game? (y/n): 
```

**Type `y`** to resume where you left off
**Type `n`** to start a new game (overwrites the save)

### In-Game Commands

While playing:

```bash
save      # Manually save the game (though it auto-saves anyway)
state     # View current game state
quit      # Save and exit
```

### Multiple Save Files

Keep different campaigns separate:

```bash
# Campaign 1: Dragon quest
python universal_dm.py -s dragon_quest.json

# Campaign 2: Mystery investigation  
python universal_dm.py -s mystery.json

# Campaign 3: Dungeon crawl
python universal_dm.py -s dungeon.json
```

Each maintains its own independent game state.

### Backing Up Saves

```bash
# Backup before a risky decision
cp gamestate.json gamestate_backup.json

# Restore if things go badly
cp gamestate_backup.json gamestate.json
```

### What Gets Saved

Everything:
- All characters (PCs and NPCs) with full stats
- Character HP, inventory, motivations
- All locations and descriptions
- Quest log
- Complete action history
- Combat state (in combat, participants, turn count)
- Conversation history with the AI
- Session number

### Save File Format

Saves are JSON files you can view:

```bash
cat gamestate.json
```

Example structure:
```json
{
  "characters": {
    "Thorin": {
      "name": "Thorin",
      "stats": {"strength": 14, "dexterity": 12, ...},
      "hp": 18,
      "max_hp": 23,
      "inventory": ["longsword", "rope"],
      "is_player": true
    }
  },
  "current_location": "Dark Forest",
  "in_combat": true,
  "combat_participants": ["Thorin", "Goblin"],
  "turn_count": 3,
  ...
}
```

### Manual Editing

You can manually edit save files if needed:
- Fix typos in character names
- Adjust HP
- Add/remove items
- Change locations

**Be careful** - invalid JSON will break the save.

### Starting Fresh

```bash
# Delete the save to start over
rm gamestate.json

# Or just say 'n' when prompted to continue
```

## Complete Examples

### Example 1: Start New Game with Claude

```bash
python universal_dm.py -p claude
```

No save exists → Creates character → Begins adventure

### Example 2: Continue Existing Game

```bash
python universal_dm.py -p claude
```

Save exists → Prompted to continue → Type `y` → Resume game

### Example 3: Multiple Campaigns

```bash
# Monday: Work on the dragon quest
python universal_dm.py -p claude -s dragon.json

# Wednesday: Play the mystery campaign
python universal_dm.py -p openai -s mystery.json

# Friday: Try the dungeon crawl with local AI
python universal_dm.py -p ollama -s dungeon.json
```

### Example 4: Experiment Safely

```bash
# Backup before dangerous choice
cp gamestate.json before_dragon_fight.json

# Fight the dragon
python universal_dm.py -p claude

# If you die, restore the backup
cp before_dragon_fight.json gamestate.json
python universal_dm.py -p claude
```

## Troubleshooting

**"No save found" but I saved before**
- Check you're in the same directory
- Check the filename matches (default is `gamestate.json`)
- Use `--save-file` to specify the exact file

**"Save file corrupted"**
- The JSON might be invalid
- Try opening in a text editor to see the error
- Restore from a backup if you have one

**Want to move saves between computers**
- Just copy the `.json` file
- Make sure you have the same game version

**Multiple people want to use the same computer**
- Use different save files for each person:
  ```bash
  python universal_dm.py -s alice_game.json
  python universal_dm.py -s bob_game.json
  ```

## Tips

- The auto-save means you can quit anytime with `Ctrl+C` and not lose progress
- Use `--save-file` for multiple campaigns or multiple players
- Back up before major story moments
- The save file is portable - copy it to play on different computers
- You can manually edit saves in a pinch, but be careful with the JSON format
