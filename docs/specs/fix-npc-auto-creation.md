# Fix: NPC Auto-Creation

## Goal

Ensure that named NPCs introduced in the DM's narrative are always registered in the game state with a `Character` object, even when the LLM forgets to emit `NPC:` command tags.

## Current Behavior

The system prompt tells the LLM to use `NPC: [name] | [description] | [motivation]` format when creating NPCs. However, the LLM often introduces named NPCs in pure narrative without emitting these tags. Result: NPCs appear in the story but have no character entry, no stats, no HP — the game state doesn't know they exist.

Example: Sila Blackwood is introduced across multiple turns. The player even explicitly asks "Create her character" but the LLM just continues narrating.

## Target Behavior

1. The system prompt more strongly requires NPC: tags whenever a named NPC is first introduced.
2. After processing the main LLM response, if no NPC commands were emitted, the system sends a short follow-up prompt asking the LLM to emit NPC: tags for any new named characters it just introduced.
3. NPC: tags from the follow-up are parsed and executed, creating `Character` objects in the game state.
4. The follow-up is cheap (non-streaming, short response expected).

## Files to Change

- **`aidm/dm.py`**:
  - Strengthen NPC creation rules in `get_system_prompt()`.
  - Add `_npc_followup_prompt()` method to build follow-up prompt.
  - Add `_generate_sync()` method for non-streaming LLM calls.
  - In `get_response_events()`, after the command loop, if no NPC commands were found, do a follow-up call and parse/execute NPC tags.
- **`tests/test_npc_creation.py`** (new):
  - Test that `parse_commands` extracts NPC tags correctly.
  - Test NPC follow-up prompt generation.
  - Test that the execute_commands flow correctly creates NPC characters.

## Step-by-Step Instructions

### 1. Strengthen system prompt in `get_system_prompt()`

Add a clear rule block emphasizing mandatory NPC creation:

```
CRITICAL NPC RULE:
When you introduce a named NPC for the FIRST time, you MUST include an NPC: line.
This applies to ALL named characters — merchants, guards, quest-givers, enemies, everyone.
If a player asks you to "create" or "make" a character, emit an NPC: line for them.
Do NOT introduce a named NPC without an NPC: line. No exceptions.
```

### 2. Add `_npc_followup_prompt` property/method

Returns a prompt string like:
```
Review your last response. If you introduced any NEW named NPCs that are not already in the game state, emit NPC: lines for each one now. Use the format: NPC: [name] | [description] | [motivation]. If no new NPCs were introduced, respond with exactly: NONE
```

### 3. Add `_generate_sync()` method

A non-streaming version of `generate_stream` that collects all tokens and returns a single string. Used for cheap follow-up calls.

### 4. Modify `get_response_events()`

After the command loop, check if any NPC commands were found. If not:
1. Call `_generate_sync()` with the NPC follow-up prompt.
2. Parse the result for NPC commands.
3. Execute any found NPC commands and emit events.

### 5. Add tests

Test the prompt generation, NPC parsing, and execute flow.

## Test Plan

| # | Test | Expected |
|---|------|----------|
| 1 | `parse_commands` with NPC: line | Extracts name, description, motivation |
| 2 | `parse_commands` with multiple NPC: lines | Extracts all NPCs |
| 3 | `execute_commands` with NPC command | Creates Character in game state |
| 4 | NPC follow-up prompt contains known character names | Prompt lists existing characters so LLM knows what's "new" |
| 5 | `_generate_sync` collects all tokens | Returns complete string |

## Out of Scope

- NER-based name detection in narrative text
- Generating stats beyond defaults for NPCs
- Changing dice/combat mechanics
