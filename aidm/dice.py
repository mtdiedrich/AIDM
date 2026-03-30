import random
import json
from typing import Optional

class DiceRoller:
    """Handles all dice rolling with true randomness"""
    
    def roll(self, sides: int, count: int = 1, modifier: int = 0) -> dict:
        """
        Roll dice and return results
        
        Args:
            sides: Number of sides on each die
            count: Number of dice to roll
            modifier: Modifier to add to total
            
        Returns:
            dict with rolls, total, and description
        """
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + modifier
        
        desc = f"{count}d{sides}"
        if modifier > 0:
            desc += f"+{modifier}"
        elif modifier < 0:
            desc += f"{modifier}"
            
        return {
            "rolls": rolls,
            "modifier": modifier,
            "total": total,
            "description": desc,
            "details": f"{desc} = {rolls} {'+' if modifier >= 0 else ''}{modifier if modifier != 0 else ''} = {total}"
        }
    
    def d20(self, modifier: int = 0) -> dict:
        """Roll a d20 with optional modifier"""
        return self.roll(20, 1, modifier)
    
    def d6(self, count: int = 1, modifier: int = 0) -> dict:
        """Roll d6s with optional modifier"""
        return self.roll(6, count, modifier)
    
    def check(self, modifier: int, dc: int) -> dict:
        """
        Make a d20 check against a DC
        
        Args:
            modifier: Modifier to add to roll
            dc: Difficulty class to beat
            
        Returns:
            dict with roll info and success/failure
        """
        result = self.d20(modifier)
        success = result["total"] >= dc
        
        return {
            **result,
            "dc": dc,
            "success": success,
            "margin": result["total"] - dc
        }

if __name__ == "__main__":
    # Test the dice roller
    roller = DiceRoller()
    
    print("Testing dice roller:")
    print(f"d20: {roller.d20()}")
    print(f"d20+5: {roller.d20(5)}")
    print(f"3d6: {roller.d6(3)}")
    print(f"Check (modifier +3, DC 15): {roller.check(3, 15)}")
