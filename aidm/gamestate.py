import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

class Character:
    """Represents a game character (PC or NPC)"""
    
    def __init__(self, name: str, **kwargs):
        self.name = name
        self.stats = kwargs.get('stats', {
            'strength': 10,
            'dexterity': 10,
            'constitution': 10,
            'intelligence': 10,
            'wisdom': 10,
            'charisma': 10
        })
        self.hp = kwargs.get('hp', 20)
        self.max_hp = kwargs.get('max_hp', 20)
        self.inventory = kwargs.get('inventory', [])
        self.description = kwargs.get('description', '')
        self.motivations = kwargs.get('motivations', [])
        self.relationships = kwargs.get('relationships', {})
        self.notes = kwargs.get('notes', [])
        self.is_player = kwargs.get('is_player', False)
        
    def get_modifier(self, stat: str) -> int:
        """Calculate ability modifier from stat"""
        return (self.stats.get(stat, 10) - 10) // 2
    
    def take_damage(self, amount: int):
        """Reduce HP by amount"""
        self.hp = max(0, self.hp - amount)
        
    def heal(self, amount: int):
        """Increase HP by amount, up to max"""
        self.hp = min(self.max_hp, self.hp + amount)
        
    def add_item(self, item: str):
        """Add item to inventory"""
        self.inventory.append(item)
        
    def remove_item(self, item: str) -> bool:
        """Remove item from inventory, return success"""
        if item in self.inventory:
            self.inventory.remove(item)
            return True
        return False
    
    def add_note(self, note: str):
        """Add a note about this character"""
        self.notes.append({
            'timestamp': datetime.now().isoformat(),
            'note': note
        })
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'stats': self.stats,
            'hp': self.hp,
            'max_hp': self.max_hp,
            'inventory': self.inventory,
            'description': self.description,
            'motivations': self.motivations,
            'relationships': self.relationships,
            'notes': self.notes,
            'is_player': self.is_player
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Character':
        """Create character from dictionary"""
        return cls(data['name'], **{k: v for k, v in data.items() if k != 'name'})
    
    def __str__(self):
        modifiers = ', '.join([f"{k[:3].upper()}: {self.stats[k]} ({self.get_modifier(k):+d})" 
                               for k in ['strength', 'dexterity', 'constitution', 
                                        'intelligence', 'wisdom', 'charisma']])
        return f"{self.name} - HP: {self.hp}/{self.max_hp}\n{modifiers}"


class GameState:
    """Manages the entire game state including characters, locations, and history"""
    
    def __init__(self, filename: str = 'gamestate.json'):
        self.filename = filename
        self.characters: Dict[str, Character] = {}
        self.locations: Dict[str, Any] = {}
        self.current_location: Optional[str] = None
        self.quest_log: List[Dict] = []
        self.history: List[Dict] = []
        self.session_number: int = 1
        self.in_combat: bool = False
        self.combat_participants: List[str] = []  # Character names in combat
        self.turn_count: int = 0
        
    def add_character(self, character: Character):
        """Add a character to the game"""
        self.characters[character.name] = character
        
    def get_character(self, name: str) -> Optional[Character]:
        """Get character by name (case-insensitive, supports 'player' alias)"""
        # Exact match first
        if name in self.characters:
            return self.characters[name]
        # Case-insensitive match
        name_lower = name.lower()
        for char_name, char in self.characters.items():
            if char_name.lower() == name_lower:
                return char
        # "player" alias → find the PC
        if name_lower == "player":
            for char in self.characters.values():
                if char.is_player:
                    return char
        return None
    
    def remove_character(self, name: str):
        """Remove a character from the game"""
        if name in self.characters:
            del self.characters[name]
    
    def add_location(self, name: str, description: str, **kwargs):
        """Add a location to the world"""
        self.locations[name] = {
            'description': description,
            'npcs': kwargs.get('npcs', []),
            'items': kwargs.get('items', []),
            'exits': kwargs.get('exits', {}),
            **kwargs
        }
        
    def add_to_history(self, entry: str, roll_result: Optional[dict] = None):
        """Add an entry to the game history"""
        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'entry': entry,
            'roll': roll_result
        })
        
    def add_quest(self, title: str, description: str, status: str = 'active'):
        """Add a quest to the log"""
        self.quest_log.append({
            'title': title,
            'description': description,
            'status': status,
            'added': datetime.now().isoformat()
        })
        
    def update_quest_status(self, title: str, status: str):
        """Update quest status"""
        for quest in self.quest_log:
            if quest['title'] == title:
                quest['status'] = status
                break
    
    def start_combat(self, participants: List[str]):
        """Start combat with given participants"""
        self.in_combat = True
        self.combat_participants = participants
        self.turn_count = 0
        
    def end_combat(self):
        """End combat"""
        self.in_combat = False
        self.combat_participants = []
        self.turn_count = 0
        
    def next_turn(self):
        """Increment turn counter"""
        self.turn_count += 1
    
    def save(self):
        """Save game state to file"""
        data = {
            'characters': {name: char.to_dict() for name, char in self.characters.items()},
            'locations': self.locations,
            'current_location': self.current_location,
            'quest_log': self.quest_log,
            'history': self.history,
            'session_number': self.session_number,
            'in_combat': self.in_combat,
            'combat_participants': self.combat_participants,
            'turn_count': self.turn_count
        }
        
        with open(self.filename, 'w') as f:
            json.dump(data, f, indent=2)
            
    def load(self) -> bool:
        """Load game state from file, return success"""
        if not os.path.exists(self.filename):
            return False
            
        with open(self.filename, 'r') as f:
            data = json.load(f)
            
        self.characters = {name: Character.from_dict(char_data) 
                          for name, char_data in data.get('characters', {}).items()}
        self.locations = data.get('locations', {})
        self.current_location = data.get('current_location')
        self.quest_log = data.get('quest_log', [])
        self.history = data.get('history', [])
        self.session_number = data.get('session_number', 1)
        self.in_combat = data.get('in_combat', False)
        self.combat_participants = data.get('combat_participants', [])
        self.turn_count = data.get('turn_count', 0)
        
        return True
    
    def get_summary(self) -> str:
        """Get a summary of current game state"""
        lines = [f"=== Game State (Session {self.session_number}) ===\n"]
        
        if self.current_location:
            lines.append(f"Current Location: {self.current_location}")
        
        if self.in_combat:
            lines.append(f"⚔️  IN COMBAT (Turn {self.turn_count})")
            lines.append(f"Combatants: {', '.join(self.combat_participants)}")
            
        lines.append(f"\nCharacters ({len(self.characters)}):")
        for char in self.characters.values():
            lines.append(f"  - {char.name} ({'PC' if char.is_player else 'NPC'}) - HP: {char.hp}/{char.max_hp}")
            
        if self.quest_log:
            lines.append(f"\nActive Quests:")
            for quest in self.quest_log:
                if quest['status'] == 'active':
                    lines.append(f"  - {quest['title']}")
                    
        return '\n'.join(lines)
