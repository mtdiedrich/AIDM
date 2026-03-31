"""Tests for turn-based character action system."""

import asyncio
from unittest.mock import patch, MagicMock

from aidm.dm import UniversalDM
from aidm.gamestate import Character


def _make_dm_with_npcs():
    """Create a DM with a player and two NPCs."""
    dm = UniversalDM()
    player = Character(
        "Mitchell",
        stats={
            "strength": 12,
            "dexterity": 14,
            "constitution": 13,
            "intelligence": 10,
            "wisdom": 11,
            "charisma": 12,
        },
        hp=23,
        max_hp=23,
        is_player=True,
        description="A wandering bard",
    )
    goblin = Character(
        "Goblin",
        description="A sneaky goblin",
        motivations=["survive", "steal shiny things"],
        is_player=False,
    )
    merchant = Character(
        "Elara", description="A shrewd merchant", motivations=["maximize profit"], is_player=False
    )
    dm.state.add_character(player)
    dm.state.add_character(goblin)
    dm.state.add_character(merchant)
    dm.state.current_location = "Market Square"
    dm.state.add_location("Market Square", "A bustling town square.")
    return dm


class TestTurnOrderParsing:
    """Tests for _parse_turn_order() — parsing LLM turn-order responses."""

    def test_parse_comma_separated(self):
        dm = _make_dm_with_npcs()
        result = dm._parse_turn_order("Mitchell, Goblin, Elara")
        assert result == ["Mitchell", "Goblin", "Elara"]

    def test_player_always_first(self):
        dm = _make_dm_with_npcs()
        result = dm._parse_turn_order("Goblin, Mitchell, Elara")
        assert result[0] == "Mitchell"

    def test_unknown_names_filtered(self):
        dm = _make_dm_with_npcs()
        result = dm._parse_turn_order("Mitchell, Goblin, FakeGuy, Elara")
        assert "FakeGuy" not in result
        assert "Mitchell" in result

    def test_fallback_on_empty(self):
        dm = _make_dm_with_npcs()
        result = dm._parse_turn_order("")
        # Should fall back to at least the player
        assert len(result) >= 1
        player_names = [c.name for c in dm.state.characters.values() if c.is_player]
        assert result[0] == player_names[0]

    def test_fallback_on_garbage(self):
        dm = _make_dm_with_npcs()
        result = dm._parse_turn_order("NONE\nNo characters act this round.")
        player_names = [c.name for c in dm.state.characters.values() if c.is_player]
        assert result[0] == player_names[0]


class TestTurnPrompts:
    """Tests for per-character turn prompt building."""

    def test_player_turn_prompt_includes_action(self):
        dm = _make_dm_with_npcs()
        char = dm.state.get_character("Mitchell")
        prompt = dm._build_character_turn_prompt(char, "I attack the goblin", thought=None)
        assert "I attack the goblin" in prompt
        assert "Mitchell" in prompt

    def test_npc_turn_prompt_includes_thought(self):
        dm = _make_dm_with_npcs()
        char = dm.state.get_character("Goblin")
        prompt = dm._build_character_turn_prompt(
            char, "I attack the goblin", thought="I need to dodge!"
        )
        assert "I need to dodge!" in prompt
        assert "Goblin" in prompt

    def test_npc_turn_prompt_without_thought(self):
        dm = _make_dm_with_npcs()
        char = dm.state.get_character("Goblin")
        prompt = dm._build_character_turn_prompt(char, "I look around", thought=None)
        assert "Goblin" in prompt
        # Should still work without a thought


class TestThoughtGeneration:
    """Tests for _get_character_thought()."""

    def test_thought_prompt_includes_character_info(self):
        dm = _make_dm_with_npcs()
        char = dm.state.get_character("Goblin")
        prompt = dm._build_thought_prompt(char, "The adventurer draws a sword.")
        assert "Goblin" in prompt
        assert "sneaky goblin" in prompt
        assert "survive" in prompt

    def test_get_character_thought_returns_string(self):
        dm = _make_dm_with_npcs()
        char = dm.state.get_character("Goblin")
        with patch.object(dm, "generate_sync", return_value="Must run away quickly!"):
            thought = dm._get_character_thought(char, "The adventurer attacks.")
        assert thought == "Must run away quickly!"


class TestTurnBasedEvents:
    """Tests for the turn-based get_response_events() flow."""

    def _collect_events(
        self,
        dm,
        player_action,
        turn_order_response="Mitchell, Goblin",
        thought_response="I should be careful.",
        action_tokens=None,
    ):
        """Helper: collect all events from get_response_events with mocked LLM."""
        if action_tokens is None:
            action_tokens = ["The goblin ", "lunges forward."]

        call_count = {"n": 0}

        def mock_generate_sync(system_prompt, user_message, conversation_history=None):
            call_count["n"] += 1
            # First sync call = turn order, subsequent = thoughts
            if "turn order" in user_message.lower() or "which characters" in user_message.lower():
                return turn_order_response
            return thought_response

        def mock_generate_stream(system_prompt, user_message, conversation_history=None):
            for tok in action_tokens:
                yield tok

        with patch.object(dm, "generate_sync", side_effect=mock_generate_sync):
            with patch.object(dm, "generate_stream", side_effect=mock_generate_stream):
                loop = asyncio.new_event_loop()
                try:
                    events = loop.run_until_complete(self._async_collect(dm, player_action))
                finally:
                    loop.close()
        return events

    async def _async_collect(self, dm, player_action):
        events = []
        async for ev in dm.get_response_events(player_action):
            events.append(ev)
        return events

    def test_loading_event_is_first(self):
        dm = _make_dm_with_npcs()
        events = self._collect_events(dm, "I look around")
        assert events[0]["type"] == "loading"

    def test_turn_start_events_emitted(self):
        dm = _make_dm_with_npcs()
        events = self._collect_events(
            dm, "I attack the goblin", turn_order_response="Mitchell, Goblin"
        )
        turn_starts = [e for e in events if e["type"] == "turn_start"]
        assert len(turn_starts) == 2
        assert turn_starts[0]["character"] == "Mitchell"
        assert turn_starts[1]["character"] == "Goblin"

    def test_player_turn_has_no_thinking(self):
        dm = _make_dm_with_npcs()
        events = self._collect_events(
            dm, "I attack the goblin", turn_order_response="Mitchell, Goblin"
        )
        # Find events between Mitchell's turn_start and Goblin's turn_start
        turn_starts = [i for i, e in enumerate(events) if e["type"] == "turn_start"]
        player_events = events[turn_starts[0] : turn_starts[1]]
        thinking_events = [e for e in player_events if e["type"] in ("thinking", "thinking_done")]
        assert len(thinking_events) == 0

    def test_npc_thinking_events(self):
        dm = _make_dm_with_npcs()
        events = self._collect_events(
            dm, "I attack the goblin", turn_order_response="Mitchell, Goblin"
        )
        # Find events after Goblin's turn_start
        turn_starts = [i for i, e in enumerate(events) if e["type"] == "turn_start"]
        goblin_events = events[turn_starts[1] :]
        thinking = [e for e in goblin_events if e["type"] == "thinking"]
        thinking_done = [e for e in goblin_events if e["type"] == "thinking_done"]
        assert len(thinking) == 1
        assert thinking[0]["character"] == "Goblin"
        assert len(thinking_done) == 1
        assert thinking_done[0]["character"] == "Goblin"
        assert thinking_done[0]["text"] == "I should be careful."

    def test_turn_start_includes_is_player(self):
        dm = _make_dm_with_npcs()
        events = self._collect_events(dm, "I look around", turn_order_response="Mitchell, Goblin")
        turn_starts = [e for e in events if e["type"] == "turn_start"]
        assert turn_starts[0]["is_player"] is True
        assert turn_starts[1]["is_player"] is False

    def test_tokens_emitted_per_turn(self):
        dm = _make_dm_with_npcs()
        events = self._collect_events(
            dm,
            "I look around",
            turn_order_response="Mitchell, Goblin",
            action_tokens=["Hello ", "world."],
        )
        # Each turn should have tokens
        token_events = [e for e in events if e["type"] == "token"]
        # 2 characters × 2 tokens each = 4
        assert len(token_events) == 4

    def test_narrative_replace_per_turn(self):
        dm = _make_dm_with_npcs()
        events = self._collect_events(
            dm,
            "I look around",
            turn_order_response="Mitchell, Goblin",
            action_tokens=["Hello world."],
        )
        replace_events = [e for e in events if e["type"] == "narrative_replace"]
        # One per character turn
        assert len(replace_events) == 2

    def test_done_event_last(self):
        dm = _make_dm_with_npcs()
        events = self._collect_events(dm, "I look around", turn_order_response="Mitchell")
        assert events[-1]["type"] == "done"
        assert "user_turn" in events[-1]
        assert "assistant_turn" in events[-1]

    def test_state_event_before_done(self):
        dm = _make_dm_with_npcs()
        events = self._collect_events(dm, "I look around", turn_order_response="Mitchell")
        state_events = [e for e in events if e["type"] == "state"]
        assert len(state_events) >= 1
        done_idx = next(i for i, e in enumerate(events) if e["type"] == "done")
        state_idx = next(i for i, e in enumerate(events) if e["type"] == "state")
        assert state_idx < done_idx

    def test_npc_followup_runs_per_turn(self):
        """When a turn's narrative mentions a new NPC without NPC: line,
        the per-turn follow-up should catch it and create the character.
        Critically, this must work even when the NPC is introduced in an
        EARLIER turn (not the last one), which the round-level follow-up misses."""
        dm = _make_dm_with_npcs()
        stream_calls = {"n": 0}

        def mock_generate_sync(system_prompt, user_message, conversation_history=None):
            if "which characters" in user_message.lower():
                return "Mitchell, Goblin"
            # Thought call for Goblin
            if "thinking right now" in user_message.lower():
                return "I should keep watch."
            # NPC follow-up should include the turn's actual narrative
            # Mitchell's turn follow-up should trigger NPC creation
            if "Kael" in user_message:
                return "NPC: Kael | scarred ranger with a worn blade | find work"
            return "NONE"

        def mock_generate_stream(system_prompt, user_message, conversation_history=None):
            stream_calls["n"] += 1
            if stream_calls["n"] == 1:
                # Mitchell's turn — introduces Kael without NPC: line
                yield "You greet the scarred ranger. "
                yield '"Name\'s Kael," he says.'
            else:
                # Goblin's turn — no new NPCs
                yield "The goblin eyes you warily."

        with patch.object(dm, "generate_sync", side_effect=mock_generate_sync):
            with patch.object(dm, "generate_stream", side_effect=mock_generate_stream):
                loop = asyncio.new_event_loop()
                try:
                    events = loop.run_until_complete(self._async_collect(dm, "greet the ranger"))
                finally:
                    loop.close()

        # Kael should have been created via per-turn follow-up on Mitchell's turn
        assert dm.state.get_character("Kael") is not None
        npc_commands = [e for e in events if e["type"] == "command" and e["subtype"] == "npc"]
        assert len(npc_commands) >= 1
        assert "Kael" in npc_commands[0]["text"]

    def test_npc_followup_skipped_when_npc_present(self):
        """When a turn already emits NPC: commands, no follow-up is needed for that turn."""
        dm = _make_dm_with_npcs()
        sync_calls = []

        def mock_generate_sync(system_prompt, user_message, conversation_history=None):
            sync_calls.append(user_message)
            if "which characters" in user_message.lower():
                return "Mitchell"
            return "NONE"

        def mock_generate_stream(system_prompt, user_message, conversation_history=None):
            yield "A guard approaches. "
            yield "NPC: Guard | armored town guard | keep the peace\n"
            yield "He nods at you."

        with patch.object(dm, "generate_sync", side_effect=mock_generate_sync):
            with patch.object(dm, "generate_stream", side_effect=mock_generate_stream):
                loop = asyncio.new_event_loop()
                try:
                    events = loop.run_until_complete(self._async_collect(dm, "look around"))
                finally:
                    loop.close()

        # Guard should be created from the inline NPC: command
        assert dm.state.get_character("Guard") is not None
        # No follow-up call should have been made (only turn-order sync call)
        followup_calls = [
            c for c in sync_calls if "introduced" in c.lower() or "review" in c.lower()
        ]
        assert len(followup_calls) == 0
