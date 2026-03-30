"""
AI DM Integration - Connects the game system to Claude API
This allows Claude to act as the dungeon master with access to dice rolling and state management
"""

import json
from typing import Optional, Dict, Any, List
from dice import DiceRoller
from gamestate import GameState, Character

class AIDungeonMaster:
    """
    AI-powered dungeon master that can:
    - Generate narrative responses
    - Decide when to roll dice
    - Update game state
    - Manage NPCs and world
    """
    
    def __init__(self, state: GameState, dice: DiceRoller):
        self.state = state
        self.dice = dice
        self.conversation_history = []
        
    def build_system_prompt(self) -> str:
        """Build the system prompt for the AI DM"""
        return """You are a creative and fair dungeon master for a tabletop RPG.

Your role:
- Create engaging narratives and respond to player actions
- Describe scenes, NPCs, and outcomes
- Decide when dice rolls are needed for success/failure
- Say "no" when players attempt unreasonable actions
- Maintain consistent world logic and character behavior
- Create consequences for player choices

When you need a dice roll:
- For contested actions, challenges, or uncertain outcomes
- Respond with: ROLL_REQUEST: [character_name] [stat] DC [number] for [reason]
- Example: "ROLL_REQUEST: goblin dexterity DC 12 for dodging arrow"
- The system will make the roll and give you the result

When creating NPCs:
- Respond with: CREATE_NPC: [name] | [description] | [motivations]
- Give them stats appropriate to their role
- Example: "CREATE_NPC: Grimwald the Merchant | A rotund man with silver rings | Wants to maximize profit"

When updating character state:
- DAMAGE: [character] [amount] - Deal damage
- HEAL: [character] [amount] - Restore HP
- GIVE_ITEM: [character] [item] - Add item to inventory
- TAKE_ITEM: [character] [item] - Remove item from inventory

Rules:
- Be descriptive but concise
- Challenge the player appropriately
- NPCs have their own motivations and may refuse or betray the player
- Combat should be tactical and dangerous
- Social encounters should have multiple solutions
- The world responds logically to player actions
- Don't let players succeed at everything - failure creates stories

Current game state will be provided before each player action."""

    def build_context(self, player_action: str) -> str:
        """Build context including game state for the AI"""
        context_parts = []
        
        # Add game summary
        context_parts.append("=== CURRENT GAME STATE ===")
        context_parts.append(self.state.get_summary())
        
        # Add character details
        context_parts.append("\n=== CHARACTERS ===")
        for char in self.state.characters.values():
            context_parts.append(str(char))
            if char.description:
                context_parts.append(f"  Description: {char.description}")
            if char.motivations:
                context_parts.append(f"  Motivations: {', '.join(char.motivations)}")
        
        # Add current location
        if self.state.current_location and self.state.current_location in self.state.locations:
            loc = self.state.locations[self.state.current_location]
            context_parts.append(f"\n=== CURRENT LOCATION: {self.state.current_location} ===")
            context_parts.append(loc['description'])
            if loc.get('npcs'):
                context_parts.append(f"NPCs present: {', '.join(loc['npcs'])}")
        
        # Add recent history (last 5 entries)
        if self.state.history:
            context_parts.append("\n=== RECENT EVENTS ===")
            for entry in self.state.history[-5:]:
                context_parts.append(f"- {entry['entry']}")
                if entry.get('roll'):
                    context_parts.append(f"  Roll: {entry['roll']['details']}")
        
        context_parts.append(f"\n=== PLAYER ACTION ===")
        context_parts.append(player_action)
        
        return '\n'.join(context_parts)
    
    def process_action(self, player_action: str) -> str:
        """
        Process a player action and return the DM's response
        This is where you'd call the Claude API in a real implementation
        """
        
        # Build the full context
        context = self.build_context(player_action)
        
        # In a real implementation, you would:
        # 1. Call Claude API with system_prompt and context
        # 2. Parse the response for ROLL_REQUEST, CREATE_NPC, etc.
        # 3. Execute those commands
        # 4. Send results back to Claude if needed
        # 5. Return the final narrative response
        
        # For now, return a template response
        return f"""[This is where Claude's response would appear]

To integrate with Claude API, you would:

1. Make API call:
```python
import anthropic

client = anthropic.Anthropic(api_key="your-key")
message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1000,
    system=self.build_system_prompt(),
    messages=[
        {{"role": "user", "content": context}}
    ]
)
response = message.content[0].text
```

2. Parse response for commands like:
   - ROLL_REQUEST: goblin dexterity DC 12 for dodging
   - CREATE_NPC: name | description | motivations
   - DAMAGE: character 5
   
3. Execute commands and update state

4. Return narrative to player

Context sent to AI:
{context}
"""
    
    def execute_roll_request(self, request: str) -> Dict[str, Any]:
        """
        Parse and execute a roll request from the AI
        Format: ROLL_REQUEST: [character] [stat] DC [number] for [reason]
        """
        try:
            parts = request.replace('ROLL_REQUEST:', '').strip().split()
            character_name = parts[0]
            stat = parts[1]
            dc = int(parts[3])
            reason = ' '.join(parts[5:])
            
            character = self.state.get_character(character_name)
            if not character:
                return {"error": f"Character {character_name} not found"}
            
            modifier = character.get_modifier(stat)
            result = self.dice.check(modifier, dc)
            
            # Add to history
            self.state.add_to_history(
                f"{character_name} attempts {reason}",
                result
            )
            
            return {
                "character": character_name,
                "stat": stat,
                "dc": dc,
                "result": result,
                "success": result["success"]
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def create_npc(self, npc_data: str) -> Optional[Character]:
        """
        Create an NPC from AI request
        Format: CREATE_NPC: name | description | motivations
        """
        try:
            parts = npc_data.replace('CREATE_NPC:', '').strip().split('|')
            name = parts[0].strip()
            description = parts[1].strip() if len(parts) > 1 else ""
            motivations = [m.strip() for m in parts[2].split(',')] if len(parts) > 2 else []
            
            # Create NPC with average stats
            npc = Character(
                name,
                description=description,
                motivations=motivations,
                is_player=False
            )
            
            self.state.add_character(npc)
            return npc
            
        except Exception as e:
            print(f"Error creating NPC: {e}")
            return None
    
    def apply_damage(self, target: str, amount: int):
        """Apply damage to a character"""
        char = self.state.get_character(target)
        if char:
            char.take_damage(amount)
            self.state.add_to_history(f"{target} takes {amount} damage")
    
    def apply_healing(self, target: str, amount: int):
        """Heal a character"""
        char = self.state.get_character(target)
        if char:
            char.heal(amount)
            self.state.add_to_history(f"{target} heals {amount} HP")


def example_usage():
    """Example of how to use the AI DM"""
    from gamestate import GameState
    from dice import DiceRoller
    
    # Initialize
    state = GameState()
    dice = DiceRoller()
    dm = AIDungeonMaster(state, dice)
    
    # Create a player character
    player = Character(
        "Thorin",
        stats={'strength': 14, 'dexterity': 12, 'constitution': 13,
               'intelligence': 10, 'wisdom': 11, 'charisma': 8},
        hp=23,
        max_hp=23,
        is_player=True,
        description="A dwarf warrior with a thick beard"
    )
    state.add_character(player)
    
    # Create starting location
    state.add_location(
        "Tavern",
        "A smoky tavern filled with rough-looking patrons",
        npcs=["Bartender"],
        exits={'north': 'Street', 'east': 'Alley'}
    )
    state.current_location = "Tavern"
    
    # Process an action
    action = "I approach the bartender and ask about rumors"
    response = dm.process_action(action)
    print(response)

if __name__ == "__main__":
    example_usage()
