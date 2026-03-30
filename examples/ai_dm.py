#!/usr/bin/env python3
"""
AI Dungeon Master System
A text-based RPG with AI-driven storytelling, dice mechanics, and persistent character/world state
"""

import sys
import json
from dice import DiceRoller
from gamestate import GameState, Character

class AIDM:
    """Main AI Dungeon Master controller"""
    
    def __init__(self, save_file: str = 'gamestate.json'):
        self.dice = DiceRoller()
        self.state = GameState(save_file)
        self.running = False
        
    def start(self):
        """Start or resume a game"""
        print("=" * 60)
        print("AI DUNGEON MASTER")
        print("=" * 60)
        print()
        
        # Try to load existing game
        if self.state.load():
            print("Saved game found!")
            print(self.state.get_summary())
            print()
            response = input("Continue this game? (y/n): ").lower()
            if response != 'y':
                self.new_game()
        else:
            self.new_game()
            
        self.running = True
        self.game_loop()
        
    def new_game(self):
        """Start a new game"""
        print("\n=== NEW GAME ===")
        print("Let's create your character.\n")
        
        name = input("Character name: ")
        
        print("\nAssign your stats (you have 75 points total):")
        print("Recommended: 8-15 per stat, average of ~12-13")
        
        stats = {}
        total = 75
        for stat in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']:
            while True:
                try:
                    value = int(input(f"{stat.capitalize()} (points remaining: {total}): "))
                    if value < 3 or value > 18:
                        print("Stats must be between 3 and 18")
                        continue
                    if value > total:
                        print(f"Not enough points remaining ({total})")
                        continue
                    stats[stat] = value
                    total -= value
                    break
                except ValueError:
                    print("Please enter a number")
        
        # Create player character
        player = Character(
            name,
            stats=stats,
            hp=20 + stats.get('constitution', 10) - 10,
            max_hp=20 + stats.get('constitution', 10) - 10,
            is_player=True,
            description=input("\nBrief character description: ")
        )
        
        self.state.add_character(player)
        
        print(f"\n{player}\n")
        print("Character created! The adventure begins...\n")
        
    def game_loop(self):
        """Main game loop"""
        
        # Display initial context
        print("\n" + "=" * 60)
        print("COMMANDS:")
        print("  - Type your actions naturally")
        print("  - 'roll [dice]' - Roll dice (e.g., 'roll d20', 'roll 3d6')")
        print("  - 'check [stat] [dc]' - Make a skill check")
        print("  - 'character' - View your character")
        print("  - 'state' - View game state")
        print("  - 'quit' - Save and quit")
        print("=" * 60)
        print()
        
        while self.running:
            try:
                player_input = input("> ").strip()
                
                if not player_input:
                    continue
                    
                # Handle commands
                if player_input.lower() == 'quit':
                    self.quit()
                    break
                elif player_input.lower() == 'character':
                    self.show_character()
                elif player_input.lower() == 'state':
                    print(self.state.get_summary())
                elif player_input.lower().startswith('roll '):
                    self.handle_roll(player_input[5:])
                elif player_input.lower().startswith('check '):
                    self.handle_check(player_input[6:])
                else:
                    self.handle_action(player_input)
                    
            except KeyboardInterrupt:
                print("\n")
                self.quit()
                break
                
    def handle_roll(self, dice_str: str):
        """Handle manual dice roll command"""
        try:
            # Parse dice notation (e.g., "d20", "3d6", "d20+5")
            dice_str = dice_str.lower().strip()
            
            modifier = 0
            if '+' in dice_str:
                dice_str, mod = dice_str.split('+')
                modifier = int(mod)
            elif '-' in dice_str:
                dice_str, mod = dice_str.split('-')
                modifier = -int(mod)
                
            if dice_str.startswith('d'):
                count = 1
                sides = int(dice_str[1:])
            else:
                count, sides = dice_str.split('d')
                count = int(count)
                sides = int(sides)
                
            result = self.dice.roll(sides, count, modifier)
            print(f"🎲 {result['details']}")
            
        except Exception as e:
            print(f"Invalid dice format. Use: d20, 3d6, d20+5, etc.")
            
    def handle_check(self, check_str: str):
        """Handle skill check command"""
        try:
            parts = check_str.strip().split()
            stat = parts[0].lower()
            dc = int(parts[1]) if len(parts) > 1 else 10
            
            # Get player character
            player = next((c for c in self.state.characters.values() if c.is_player), None)
            if not player:
                print("No player character found!")
                return
                
            modifier = player.get_modifier(stat)
            result = self.dice.check(modifier, dc)
            
            print(f"🎲 {stat.capitalize()} check (DC {dc}): {result['details']}")
            print(f"   {'SUCCESS' if result['success'] else 'FAILURE'} (by {abs(result['margin'])})")
            
        except Exception as e:
            print(f"Invalid check format. Use: check [stat] [dc]")
            
    def show_character(self):
        """Display player character sheet"""
        player = next((c for c in self.state.characters.values() if c.is_player), None)
        if player:
            print("\n" + "=" * 60)
            print(player)
            print(f"\nDescription: {player.description}")
            if player.inventory:
                print(f"Inventory: {', '.join(player.inventory)}")
            if player.motivations:
                print(f"Motivations: {', '.join(player.motivations)}")
            print("=" * 60 + "\n")
        else:
            print("No player character found!")
            
    def handle_action(self, action: str):
        """Handle player action - this is where AI DM would respond"""
        print(f"\n[You: {action}]")
        print("\n[AI DM Response would go here]")
        print("Note: This is the framework. To add AI responses, you would:")
        print("  1. Send the action + game state to an LLM API")
        print("  2. Let the LLM decide if dice rolls are needed")
        print("  3. Execute any dice rolls the LLM requests")
        print("  4. Update game state based on outcomes")
        print("  5. Display the LLM's narrative response")
        print()
        
        # Add to history
        self.state.add_to_history(action)
        
    def quit(self):
        """Save and quit"""
        print("\nSaving game...")
        self.state.save()
        print("Game saved. Farewell!")
        self.running = False


def main():
    dm = AIDM()
    dm.start()

if __name__ == "__main__":
    main()
