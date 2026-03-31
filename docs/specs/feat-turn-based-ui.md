# feat-turn-based-ui — Turn-Based Character Actions with Discrete UI Boxes

## Goal

Restructure the game loop so each character in a scene acts in discrete turns, each rendered in its own UI box. NPC thoughts are generated before actions (non-streaming "Thinking..." animation), and a spinning hourglass appears before any tokens arrive.

## Current Behavior

- The DM makes ONE LLM call per player action, streaming all narrative as a single DM bubble.
- THINK commands are parsed from the LLM output and routed to the sidebar only.
- All characters' actions are interleaved in a single narrative blob.
- No loading indicator before first token.

## Target Behavior

### Turn Flow

1. Player sends action.
2. UI shows a **spinning ⏳ hourglass bubble** (loading indicator).
3. Backend makes a **planning call** (non-streaming) to determine which characters act this round and in what order. Player character is always first.
4. For each character in turn order:
   a. UI receives `turn_start` → creates a **new turn box** labeled with the character's name.
   b. *(NPCs only)* UI receives `thinking` → shows a **"Thinking..." wave animation** in the turn box.
   c. *(NPCs only)* Backend makes a non-streaming LLM call for the character's thought. UI receives `thinking_done` → **reveals the thought text** (replaces the animation).
   d. Backend streams the character's action narration. UI appends tokens into the turn box.
   e. Backend parses commands (ROLL, DAMAGE, HEAL, NPC) from the response, executes them, sends events.
   f. If dice rolls occurred, a follow-up LLM call resolves the outcome (streamed into the same turn box).
5. NPC follow-up for untagged new NPCs (existing mechanism, per-character).
6. Backend records the round in `self.turns` and sends `state` + `done`.

### UI Turn Box Example

```
┌── Goblin Guard ─────────────────────┐
│ 💭 "This adventurer seems weak..."  │
│                                      │
│ The goblin lunges forward with its   │
│ rusty blade, aiming for your side.   │
│                                      │
│ 🎲 Goblin Guard dexterity DC 13: 17 │
│ - SUCCESS                            │
│ ⚔️ Mitchell takes 4 damage           │
└──────────────────────────────────────┘
```

### Hourglass

- Appears as its own DM-style message bubble with a spinning ⏳ emoji.
- Removed from the DOM when the first `turn_start` event arrives.

### Thinking Animation

- Shows `💭 Thinking` with a CSS dot-wave animation (e.g., `Thinking...` where dots animate).
- When `thinking_done` arrives, the animation is replaced with the actual thought text styled in purple/italic.

## Files to Change

| File | Action | Summary |
|------|--------|---------|
| `aidm/dm.py` | Modify | Rewrite `get_response_events()` for turn-based flow; add planning, thought, and per-character prompts |
| `aidm/static/index.html` | Modify | Add turn box UI, thinking animation, hourglass, handle new event types |
| `tests/test_turns.py` | Create | Tests for turn order planning, thought generation, turn-based event flow |

## Step-by-Step Instructions

### Step 1: dm.py — Add turn planning prompt

Add method `_get_turn_order(player_action: str) -> list[str]`:
- Build a prompt asking the LLM which characters should act, given the game state and player action.
- Parse the comma-separated response into a list of character names.
- Validate each name against `self.state.characters`.
- Player character is always first. If the LLM omits the player, prepend them.
- If the LLM returns no valid names, fall back to `[player_name]`.

### Step 2: dm.py — Add thought generation

Add method `_get_character_thought(character: Character, context: str) -> str`:
- Call `generate_sync()` with a prompt asking for the character's inner thought.
- Prompt includes the character's description, motivations, and current situation.
- Return the thought text (stripped).

### Step 3: dm.py — Add per-character turn prompt

Add method `_build_character_turn_prompt(character: Character, player_action: str, thought: str | None) -> str`:
- For the player character: "Narrate the outcome of [name]'s action: [player_action]. Only describe this character's actions and immediate results."
- For NPCs: "Narrate [name]'s turn. [name] is thinking: '[thought]'. Describe only what [name] does."
- Include the game state context (location, characters, recent history).

### Step 4: dm.py — Rewrite get_response_events()

Replace the current implementation with the turn-based flow:

```python
async def get_response_events(self, player_action: str):
    yield {"type": "loading"}

    # 1. Planning: determine turn order
    turn_order = await asyncio.to_thread(self._get_turn_order, player_action)

    all_narratives = []
    conversation_for_llm = list(self.conversation)

    context = self.build_context(player_action)

    for char_name in turn_order:
        char = self.state.get_character(char_name)
        if not char:
            continue
        is_player = char.is_player

        yield {"type": "turn_start", "character": char_name, "is_player": is_player}

        thought = None
        if not is_player:
            # Thinking phase
            yield {"type": "thinking", "character": char_name}
            thought = await asyncio.to_thread(
                self._get_character_thought, char, context
            )
            yield {"type": "thinking_done", "character": char_name, "text": thought}

        # Action phase (streaming)
        turn_prompt = self._build_character_turn_prompt(char, player_action, thought)
        system_prompt = self.get_system_prompt()

        full_tokens = []
        async for token in _stream_tokens(system_prompt, turn_prompt, conversation_for_llm):
            full_tokens.append(token)
            yield {"type": "token", "text": token}

        response = "".join(full_tokens)
        cleaned = _clean_narrative(response)
        yield {"type": "narrative_replace", "text": cleaned}
        yield {"type": "narrative_done"}
        all_narratives.append(cleaned)

        # Parse and execute commands
        _, commands = self.parse_commands(response)
        if commands:
            command_results = self.execute_commands(commands)
            has_rolls = any(cmd["type"] == "roll" for cmd in commands)

            for result, cmd in zip(command_results, commands):
                if cmd["type"] == "thought":
                    if not _is_player_character(cmd["character"]):
                        yield {"type": "thought", "character": cmd["character"], "text": cmd["text"]}
                else:
                    yield {"type": "command", "subtype": cmd["type"], "text": result}

            # Handle dice roll follow-ups within the character's turn
            if has_rolls:
                roll_results = [r for r, c in zip(command_results, commands) if c["type"] == "roll"]
                results_text = "DICE ROLL RESULTS:\n" + "\n".join(roll_results)
                results_text += f"\n\nBased on these results, describe what happens next for {char_name} only."

                full_tokens = []
                async for token in _stream_tokens(system_prompt, results_text, conversation_for_llm):
                    full_tokens.append(token)
                    yield {"type": "token", "text": token}

                follow_up = "".join(full_tokens)
                cleaned_follow = _clean_narrative(follow_up)
                yield {"type": "narrative_replace", "text": cleaned_follow}
                yield {"type": "narrative_done"}
                all_narratives.append(cleaned_follow)

                # Execute any commands from follow-up
                _, follow_commands = self.parse_commands(follow_up)
                if follow_commands:
                    follow_results = self.execute_commands(follow_commands)
                    for result, cmd in zip(follow_results, follow_commands):
                        if cmd["type"] != "thought":
                            yield {"type": "command", "subtype": cmd["type"], "text": result}

        # Add this character's response to conversation context
        conversation_for_llm.append({"role": "user", "content": turn_prompt})
        conversation_for_llm.append({"role": "assistant", "content": response})

    # NPC follow-up (existing mechanism)
    # ... (simplified, check if any NPC commands were emitted)

    # Record turn
    self.state.add_to_history(player_action)
    self.conversation = conversation_for_llm[-20:]

    user_turn_index = len(self.turns)
    self.turns.append({"role": "user", "content": player_action})
    assistant_turn_index = len(self.turns)
    self.turns.append({"role": "assistant", "content": "\n\n".join(all_narratives)})

    yield {"type": "state", "data": {
        "characters": {n: c.to_dict() for n, c in self.state.characters.items()},
        "location": self.state.current_location,
        "in_combat": self.state.in_combat,
    }}
    yield {"type": "done", "user_turn": user_turn_index, "assistant_turn": assistant_turn_index}
```

### Step 5: index.html — Add CSS for turn boxes, thinking animation, hourglass

**Turn box:**
```css
.turn-box {
  align-self: flex-start;
  max-width: 85%;
  background: var(--surface);
  border: 1px solid #ffffff10;
  border-radius: var(--radius);
  overflow: hidden;
  margin-bottom: 4px;
}
.turn-box-header {
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--gold);
  background: #ffffff08;
  border-bottom: 1px solid #ffffff10;
}
.turn-box-header.player { color: var(--blue); }
.turn-box-content {
  padding: 10px 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-wrap: break-word;
}
```

**Thinking animation:**
```css
.thinking-indicator {
  color: var(--thought);
  font-style: italic;
  padding: 4px 0;
}
.thinking-indicator .dots::after {
  content: '';
  animation: wave 1.5s steps(4) infinite;
}
@keyframes wave {
  0% { content: ''; }
  25% { content: '.'; }
  50% { content: '..'; }
  75% { content: '...'; }
}
```

**Hourglass:**
```css
.loading-bubble {
  align-self: flex-start;
  padding: 10px 14px;
  font-size: 20px;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

### Step 6: index.html — Handle new event types in handleEvent()

Add cases for:
- `loading`: create hourglass bubble, store reference for removal
- `turn_start`: remove hourglass if present, create new turn box with character name header
- `thinking`: add thinking indicator inside current turn box
- `thinking_done`: replace thinking indicator with actual thought text
- `token`: append to current turn box content area (instead of DM bubble)
- `narrative_replace`: replace current turn box content text
- `narrative_done`: finalize current turn box

## Test Plan

### tests/test_turns.py

| # | Test | Expected Result |
|---|------|----------------|
| 1 | `test_turn_order_player_first` | Player character is always first in turn order |
| 2 | `test_turn_order_includes_npcs` | NPCs from game state are included when relevant |
| 3 | `test_turn_order_fallback` | Falls back to player-only if LLM returns garbage |
| 4 | `test_thought_generation` | `_get_character_thought()` returns a non-empty string |
| 5 | `test_player_turn_prompt` | Player turn prompt includes action and context |
| 6 | `test_npc_turn_prompt_includes_thought` | NPC turn prompt includes the generated thought |
| 7 | `test_loading_event_first` | First event from `get_response_events()` is `{"type": "loading"}` |
| 8 | `test_turn_start_events` | `turn_start` events emitted for each character |
| 9 | `test_npc_thinking_events` | NPCs get `thinking` + `thinking_done` events |
| 10 | `test_player_no_thinking` | Player character does NOT get thinking events |
| 11 | `test_commands_within_turn` | Commands parsed and executed within each character's turn |

## Out of Scope

- Initiative/turn order based on stats (future enhancement)
- Combat-specific turn handling (currently same for combat and non-combat)
- Persisting turn structure to save files
- Mobile/responsive layout changes
- Changes to the edit/regenerate system (it operates on the combined round)
