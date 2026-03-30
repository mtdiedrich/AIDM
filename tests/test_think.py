"""Tests for THINK command parsing in the DM."""

from aidm.dm import UniversalDM
from aidm.llm_providers import MockProvider


def _make_dm():
    return UniversalDM(MockProvider())


class TestThinkParsing:
    """Tests for the THINK: command format."""

    def test_parse_single_think(self):
        dm = _make_dm()
        narrative, commands = dm.parse_commands(
            "The goblin sneers at you.\nTHINK: Goblin | This fool will fall easily.\n"
        )
        thinks = [c for c in commands if c["type"] == "thought"]
        assert len(thinks) == 1
        assert thinks[0]["character"] == "Goblin"
        assert thinks[0]["text"] == "This fool will fall easily."

    def test_parse_multiple_thinks(self):
        dm = _make_dm()
        text = (
            "Tension fills the room.\n"
            "THINK: Guard | I should call for backup.\n"
            "THINK: Mitchell | Something feels off here.\n"
        )
        _, commands = dm.parse_commands(text)
        thinks = [c for c in commands if c["type"] == "thought"]
        assert len(thinks) == 2
        assert thinks[0]["character"] == "Guard"
        assert thinks[1]["character"] == "Mitchell"

    def test_think_stripped_from_narrative(self):
        dm = _make_dm()
        narrative, _ = dm.parse_commands(
            "You enter the cave.\nTHINK: Goblin | Intruders!\nDarkness surrounds you."
        )
        assert "THINK" not in narrative
        assert "You enter the cave." in narrative
        assert "Darkness surrounds you." in narrative

    def test_mixed_commands(self):
        dm = _make_dm()
        text = (
            "The bandit draws his blade.\n"
            "THINK: Bandit | I need to end this quick.\n"
            "ROLL: Bandit dexterity DC 14 | lunging attack\n"
            "DAMAGE: Mitchell 5\n"
        )
        _, commands = dm.parse_commands(text)
        types = [c["type"] for c in commands]
        assert "thought" in types
        assert "roll" in types
        assert "damage" in types

    def test_execute_thought_command(self):
        dm = _make_dm()
        results = dm.execute_commands([
            {"type": "thought", "character": "Goblin", "text": "Run away!"}
        ])
        assert len(results) == 1
        assert "Goblin" in results[0]
        assert "Run away!" in results[0]
