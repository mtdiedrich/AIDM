"""Tests for NPC auto-creation: prompt strengthening and follow-up mechanism."""

from unittest.mock import patch
from aidm.dm import UniversalDM
from aidm.gamestate import Character


def _make_dm():
    return UniversalDM()


class TestNpcParsingExisting:
    """Verify NPC: parsing works correctly (baseline)."""

    def test_single_npc_parsed(self):
        dm = _make_dm()
        _, commands = dm.parse_commands(
            "A scarred woman sits in the corner.\n"
            "NPC: Sila Blackwood | scarred former caravan guard | investigate missing shipments\n"
        )
        npcs = [c for c in commands if c["type"] == "npc"]
        assert len(npcs) == 1
        assert npcs[0]["name"] == "Sila Blackwood"
        assert "scarred" in npcs[0]["description"]
        assert "missing shipments" in npcs[0]["motivation"]

    def test_multiple_npcs_parsed(self):
        dm = _make_dm()
        text = (
            "Two figures approach.\n"
            "NPC: Guard Captain | stern woman in plate armor | maintain order\n"
            "NPC: Merchant Tav | nervous halfling with a ledger | sell goods safely\n"
        )
        _, commands = dm.parse_commands(text)
        npcs = [c for c in commands if c["type"] == "npc"]
        assert len(npcs) == 2

    def test_execute_npc_creates_character(self):
        dm = _make_dm()
        dm.execute_commands([{
            "type": "npc",
            "name": "Sila Blackwood",
            "description": "scarred former caravan guard",
            "motivation": "investigate missing shipments",
        }])
        char = dm.state.get_character("Sila Blackwood")
        assert char is not None
        assert char.is_player is False
        assert "scarred" in char.description

    def test_duplicate_npc_not_doubled(self):
        dm = _make_dm()
        dm.state.add_character(Character("Sila Blackwood", description="existing"))
        dm.execute_commands([{
            "type": "npc",
            "name": "Sila Blackwood",
            "description": "scarred former caravan guard",
            "motivation": "investigate missing shipments",
        }])
        # Should overwrite, not create a second entry
        assert len([c for c in dm.state.characters.values()
                     if c.name == "Sila Blackwood"]) == 1


class TestNpcFollowUp:
    """Tests for the NPC follow-up mechanism that catches missed NPCs."""

    def test_system_prompt_contains_npc_rules(self):
        dm = _make_dm()
        prompt = dm.get_system_prompt()
        assert "NPC:" in prompt
        # The strengthened prompt should emphasize mandatory creation
        assert "MUST" in prompt.upper()

    def test_npc_followup_prompt_lists_known_characters(self):
        dm = _make_dm()
        dm.state.add_character(Character("PlayerChar", is_player=True))
        dm.state.add_character(Character("Old NPC", is_player=False))
        prompt = dm._npc_followup_prompt()
        assert "Old NPC" in prompt
        assert "PlayerChar" in prompt

    def test_npc_followup_prompt_mentions_format(self):
        dm = _make_dm()
        prompt = dm._npc_followup_prompt()
        assert "NPC:" in prompt

    def test_generate_sync_returns_string(self):
        dm = _make_dm()
        fake_tokens = ["NPC: ", "Test | ", "desc | ", "motive"]
        with patch.object(dm, "generate_stream", return_value=iter(fake_tokens)):
            result = dm.generate_sync("sys", "user")
        assert result == "NPC: Test | desc | motive"

    def test_generate_sync_empty_response(self):
        dm = _make_dm()
        with patch.object(dm, "generate_stream", return_value=iter([])):
            result = dm.generate_sync("sys", "user")
        assert result == ""
