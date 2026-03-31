# fix-npc-followup-per-turn — NPC Follow-up Per Character Turn

## Goal

Move NPC follow-up from once-per-round to per-character-turn so that NPCs introduced in any character's narrative are always caught and created.

## Current Behavior

- NPC follow-up runs ONCE at the end of the entire round.
- It only runs if NO NPC commands were emitted across ALL character turns.
- The prompt says "review your last response" but by then the conversation has multiple character turns appended — the "last response" is the last character's turn, not necessarily the one where the NPC was introduced.
- Result: NPCs like "Kael" the ranger are described in the player's turn narrative but never created as Character objects.

## Target Behavior

- NPC follow-up runs **after each character's turn** (after commands are processed).
- For each turn, if that turn had no NPC commands, run the follow-up scoped to that turn's response.
- The follow-up prompt should reference the specific narrative from that character's turn.
- Any NPCs discovered are created immediately and command events emitted within that character's turn box.

## Files to Change

| File | Action | Summary |
|------|--------|---------|
| `aidm/dm.py` | Modify | Move NPC follow-up into per-character loop; update prompt to reference specific turn response |
| `tests/test_turns.py` | Modify | Add test for per-turn NPC follow-up |

## Step-by-Step Instructions

### Step 1: dm.py — Update `_npc_followup_prompt` to accept response text

Change `_npc_followup_prompt(self)` → `_npc_followup_prompt(self, response_text: str)`:
- Instead of "Review your last response", include the actual response text.
- Keep the known-characters list.

### Step 2: dm.py — Move NPC follow-up into per-character loop

Inside the per-character turn loop, after command execution + dice follow-ups:
1. Check if this turn had any NPC commands.
2. If not, call `_npc_followup_prompt(response)` with the character's narrative.
3. Run `generate_sync` with `conversation_for_llm` (which at this point includes only up to the current turn).
4. Parse and execute any NPC commands.
5. Emit command events.

### Step 3: dm.py — Remove round-level NPC follow-up

Delete the `had_npc_commands` / follow-up block after the per-character loop.

## Test Plan

| # | Test | File | Expected |
|---|------|------|----------|
| 1 | `test_npc_followup_runs_per_turn` | test_turns.py | When a turn's LLM response mentions a new NPC (no NPC: line), the follow-up creates it |
| 2 | `test_npc_followup_skipped_when_npc_present` | test_turns.py | When a turn already has NPC: commands, no follow-up call for that turn |

## Out of Scope

- Changing the NPC follow-up prompt wording beyond scoping it to the turn response
- UI changes
