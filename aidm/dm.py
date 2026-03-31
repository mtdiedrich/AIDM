#!/usr/bin/env python3
"""
AI Dungeon Master — runs locally via Ollama.
"""

import json
import re
import urllib.request
import urllib.error
from typing import Generator, List, Dict, Tuple
from .dice import DiceRoller
from .gamestate import GameState, Character


class UniversalDM:
    """Dungeon Master powered by a local Ollama instance."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "qwen3.5:9b-q8_0",
        max_tokens: int = 1000,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.state = GameState()
        self.dice = DiceRoller()
        self.conversation = []
        # High-level turn log: [{role: 'user'|'assistant', content: str}, ...]
        # Maps 1:1 with visible UI messages (player action, DM response).
        # Internal follow-up calls (dice roll results) are NOT separate turns.
        self.turns: List[Dict] = []

    # ------------------------------------------------------------------
    # Ollama HTTP helpers
    # ------------------------------------------------------------------

    def _ollama_post(self, body: dict):
        """POST JSON to /api/chat and return the HTTPResponse."""
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return urllib.request.urlopen(req)

    def generate_stream(
        self, system_prompt: str, user_message: str, conversation_history: list | None = None
    ) -> Generator[str, None, None]:
        """Stream tokens from Ollama's /api/chat endpoint."""
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"num_predict": self.max_tokens},
        }
        try:
            resp = self._ollama_post(body)
            for line in resp:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break
            resp.close()
        except urllib.error.URLError as e:
            yield f"[Ollama not reachable at {self.host} — is it running?] ({e.reason})"
        except Exception as e:
            yield f"[Error calling Ollama: {e}]"

    def generate_sync(
        self, system_prompt: str, user_message: str, conversation_history: list | None = None
    ) -> str:
        """Non-streaming LLM call. Returns the full response as a string."""
        return "".join(self.generate_stream(system_prompt, user_message, conversation_history))

    def get_display_name(self) -> str:
        return f"Ollama ({self.model})"

    def get_system_prompt(self) -> str:
        """System prompt that teaches any LLM to be a DM"""
        return """You are a dungeon master for a tabletop RPG. Be creative, fair, and engaging.

IMPORTANT RULES:
- Challenge players with meaningful choices and risks
- NPCs have their own goals and may refuse or betray the player
- Say "no" to unreasonable actions - don't let players succeed at everything
- Create consequences for player actions
- Make the world feel alive and reactive

DICE ROLLS AND OUTCOMES:
When you need dice rolls, use this EXACT format:
ROLL: [character_name] [stat] DC [number] | [reason]
Example: ROLL: goblin dexterity DC 12 | dodging arrow

CRITICAL: After requesting rolls, you will receive the results. You MUST then:
1. Describe the outcome based on success/failure
2. Continue the action (enemy attacks, environment reacts, etc.)
3. In combat, NPCs/enemies get their turn after the player

DO NOT describe the outcome before you know the roll result.
DO NOT leave the player hanging - always resolve what happens.
DO NOT forget enemy turns in combat.

COMBAT FLOW:
1. Player declares action → Request roll if needed
2. Receive roll result → Describe player's action outcome
3. Enemy/NPC responds → Request their rolls if needed  
4. Describe full round result
Example: "Your sword misses (roll failed). The goblin seizes the opening and lunges at you. ROLL: goblin dexterity DC 13 | attacking"

NPC CREATION:
When you introduce a named NPC for the FIRST time, you MUST include an NPC: line.
This applies to ALL named characters — merchants, guards, quest-givers, enemies, everyone.
If a player asks you to "create" or "make" a character, you MUST emit an NPC: line.
Do NOT introduce a named NPC in your narrative without an NPC: line. No exceptions.
Use this EXACT format:
NPC: [name] | [brief description] | [motivation]
Example: NPC: Grimwald | rotund merchant with silver rings | maximize profit

DAMAGE AND HEALING:
Use this EXACT format:
DAMAGE: [character] [amount]
HEAL: [character] [amount]
Example: DAMAGE: player 5

CHARACTER THOUGHTS:
Show what characters are thinking using this EXACT format:
THINK: [character_name] | [inner thought]
Example: THINK: Grimwald | This adventurer seems gullible... I could double the price.
Use 1-2 THINK lines per response for key NPCs/PCs reacting to events. Keep thoughts brief.

Keep responses under 200 words. Be descriptive but concise."""

    def _npc_followup_prompt(self, response_text: str | None = None) -> str:
        """Build a follow-up prompt asking the LLM to emit NPC: lines for any new characters."""
        known = [c.name for c in self.state.characters.values()]
        known_str = ", ".join(known) if known else "(none)"
        if response_text:
            review_line = f"Review this response:\n\n{response_text}\n\n"
        else:
            review_line = "Review your last response. "
        return (
            f"{review_line}Characters already in the game state: "
            f"{known_str}.\n"
            "If you introduced any NEW named NPCs not listed above, emit an NPC: line "
            "for each one now. Use the format: NPC: [name] | [description] | [motivation]\n"
            "If no new NPCs were introduced, respond with exactly: NONE"
        )

    def build_context(self, player_action: str) -> str:
        """Build context for the LLM including game state"""
        parts = ["=== GAME STATE ==="]

        # Combat status
        if self.state.in_combat:
            parts.append(f"\n⚔️  COMBAT ACTIVE (Turn {self.state.turn_count})")
            parts.append(f"Participants: {', '.join(self.state.combat_participants)}")
            parts.append("Remember: After player action, enemies/NPCs take their turn!")

        # Characters
        parts.append("\nCHARACTERS:")
        for char in self.state.characters.values():
            role = "PLAYER" if char.is_player else "NPC"
            parts.append(f"- {char.name} ({role}): HP {char.hp}/{char.max_hp}")
            parts.append(
                f"  STR {char.stats['strength']}({char.get_modifier('strength'):+d}) "
                f"DEX {char.stats['dexterity']}({char.get_modifier('dexterity'):+d}) "
                f"CON {char.stats['constitution']}({char.get_modifier('constitution'):+d})"
            )
            if char.description:
                parts.append(f"  {char.description}")
            if char.motivations:
                parts.append(f"  Wants: {', '.join(char.motivations)}")

        # Location
        if self.state.current_location:
            parts.append(f"\nLOCATION: {self.state.current_location}")
            if self.state.current_location in self.state.locations:
                loc = self.state.locations[self.state.current_location]
                parts.append(loc["description"])

        # Recent history
        if self.state.history:
            parts.append("\nRECENT EVENTS:")
            for entry in self.state.history[-3:]:
                parts.append(f"- {entry['entry']}")

        parts.append(f"\n=== PLAYER ACTION ===\n{player_action}")

        return "\n".join(parts)

    def parse_commands(self, response: str) -> Tuple[str, List[Dict]]:
        """Extract game commands from LLM response"""
        commands = []
        narrative = response

        # Extract roll requests - supports multi-word names like "Captain Bran"
        roll_pattern = r"ROLL:\s*(.+?)\s+(strength|dexterity|constitution|intelligence|wisdom|charisma)\s+DC\s+(\d+)\s*\|\s*(.+?)(?:\n|$)"
        for match in re.finditer(roll_pattern, response, re.MULTILINE | re.IGNORECASE):
            char_name, stat, dc, reason = match.groups()
            commands.append(
                {
                    "type": "roll",
                    "character": char_name.strip(),
                    "stat": stat.lower(),
                    "dc": int(dc),
                    "reason": reason.strip(),
                }
            )
            narrative = narrative.replace(match.group(0), "")

        # Extract NPC creation
        npc_pattern = r"NPC:\s*([^|]+)\|\s*([^|]+)\|\s*(.+?)(?:\n|$)"
        for match in re.finditer(npc_pattern, response, re.MULTILINE):
            name, desc, motivation = match.groups()
            commands.append(
                {
                    "type": "npc",
                    "name": name.strip(),
                    "description": desc.strip(),
                    "motivation": motivation.strip(),
                }
            )
            narrative = narrative.replace(match.group(0), "")

        # Extract damage/heal - supports multi-word names like "Captain Bran"
        for match in re.finditer(r"DAMAGE:\s*(.+?)\s+(\d+)(?:\n|$)", response):
            commands.append(
                {"type": "damage", "target": match.group(1).strip(), "amount": int(match.group(2))}
            )
            narrative = narrative.replace(match.group(0), "")

        for match in re.finditer(r"HEAL:\s*(.+?)\s+(\d+)(?:\n|$)", response):
            commands.append(
                {"type": "heal", "target": match.group(1).strip(), "amount": int(match.group(2))}
            )
            narrative = narrative.replace(match.group(0), "")

        # Extract character thoughts
        for match in re.finditer(r"THINK:\s*([^|]+)\|\s*(.+?)(?:\n|$)", response, re.MULTILINE):
            commands.append(
                {
                    "type": "thought",
                    "character": match.group(1).strip(),
                    "text": match.group(2).strip(),
                }
            )
            narrative = narrative.replace(match.group(0), "")

        return narrative.strip(), commands

    def execute_commands(self, commands: List[Dict]) -> List[str]:
        """Execute game commands and return results"""
        results = []

        for cmd in commands:
            if cmd["type"] == "roll":
                char = self.state.get_character(cmd["character"])
                if char:
                    modifier = char.get_modifier(cmd["stat"])
                    roll_result = self.dice.check(modifier, cmd["dc"])
                    success = "SUCCESS" if roll_result["success"] else "FAILURE"
                    results.append(
                        f"🎲 {cmd['character']} {cmd['stat']} check (DC {cmd['dc']}): "
                        f"{roll_result['total']} - {success}"
                    )
                    self.state.add_to_history(
                        f"{cmd['character']} {cmd['reason']}: {success}", roll_result
                    )

            elif cmd["type"] == "npc":
                npc = Character(
                    cmd["name"],
                    description=cmd["description"],
                    motivations=[cmd["motivation"]],
                    is_player=False,
                )
                self.state.add_character(npc)
                results.append(f"✨ Created NPC: {cmd['name']}")

            elif cmd["type"] == "damage":
                char = self.state.get_character(cmd["target"])
                if char:
                    char.take_damage(cmd["amount"])
                    results.append(
                        f"⚔️ {cmd['target']} takes {cmd['amount']} damage (HP: {char.hp}/{char.max_hp})"
                    )

            elif cmd["type"] == "heal":
                char = self.state.get_character(cmd["target"])
                if char:
                    char.heal(cmd["amount"])
                    results.append(
                        f"💚 {cmd['target']} heals {cmd['amount']} HP (HP: {char.hp}/{char.max_hp})"
                    )

            elif cmd["type"] == "thought":
                # Thoughts don't change game state; just surface them
                results.append(f"💭 {cmd['character']}: {cmd['text']}")

        return results

    # ------------------------------------------------------------------
    # Turn-based helpers
    # ------------------------------------------------------------------

    def _get_player_character(self) -> Character | None:
        """Return the player character, or None."""
        for char in self.state.characters.values():
            if char.is_player:
                return char
        return None

    def _parse_turn_order(self, llm_response: str) -> list[str]:
        """Parse a comma-separated LLM response into a validated turn order.

        Rules:
        - Only names matching characters in the game state are kept.
        - Player character is always first.
        - Falls back to [player_name] if nothing valid is returned.
        """
        names = [n.strip() for n in llm_response.split(",") if n.strip()]
        validated = []
        for name in names:
            char = self.state.get_character(name)
            if char and name not in validated:
                validated.append(char.name)  # use canonical name from state

        player = self._get_player_character()
        player_name = player.name if player else None

        if not validated:
            return [player_name] if player_name else []

        # Ensure player is first
        if player_name and player_name in validated:
            validated.remove(player_name)
            validated.insert(0, player_name)
        elif player_name:
            validated.insert(0, player_name)

        return validated

    def _get_turn_order(self, player_action: str) -> list[str]:
        """Ask the LLM which characters should act this round."""
        char_list = ", ".join(
            f"{c.name} ({'PC' if c.is_player else 'NPC'})" for c in self.state.characters.values()
        )
        prompt = (
            f'Given the player\'s action: "{player_action}"\n'
            f"Characters in the game: {char_list}\n"
            f"Location: {self.state.current_location or 'Unknown'}\n\n"
            "Which characters should act or react this round? "
            "Include the player character first, then any NPCs who would "
            "reasonably react in this situation.\n"
            "Respond with ONLY a comma-separated list of character names.\n"
            "Example: Mitchell, Goblin Guard, Barkeep"
        )
        response = self.generate_sync(self.get_system_prompt(), prompt, self.conversation)
        return self._parse_turn_order(response)

    def _build_thought_prompt(self, character: Character, context: str) -> str:
        """Build a prompt asking for a character's inner thought."""
        motivations = ", ".join(character.motivations) if character.motivations else "unknown"
        return (
            f"You are roleplaying as {character.name}.\n"
            f"Description: {character.description}\n"
            f"Motivations: {motivations}\n\n"
            f"Current situation:\n{context}\n\n"
            f"What is {character.name} thinking right now? "
            "Respond with ONLY the inner thought, 1-2 sentences. "
            "No narration, no quotes, no 'I think...' prefix. Just the raw thought."
        )

    def _get_character_thought(self, character: Character, context: str) -> str:
        """Generate an NPC's inner thought via a non-streaming LLM call."""
        prompt = self._build_thought_prompt(character, context)
        return self.generate_sync(self.get_system_prompt(), prompt, self.conversation).strip()

    def _build_character_turn_prompt(
        self, character: Character, player_action: str, thought: str | None
    ) -> str:
        """Build the user-message prompt for a single character's turn narration."""
        context = self.build_context(player_action)

        if character.is_player:
            return (
                f"{context}\n\n"
                f'Narrate the outcome of {character.name}\'s action: "{player_action}". '
                f"Describe ONLY what happens as a result of {character.name}'s action. "
                "Do NOT describe what other characters do — they will act in their own turns. "
                "Keep it concise (under 100 words). "
                "Use game commands (ROLL, DAMAGE, HEAL) as needed."
            )

        thought_line = ""
        if thought:
            thought_line = f'{character.name}\'s current thought: "{thought}"\n'

        motivations = ", ".join(character.motivations) if character.motivations else "unknown"
        return (
            f"{context}\n\n"
            f"Narrate {character.name}'s turn.\n"
            f"{character.name} is an NPC: {character.description}\n"
            f"Motivations: {motivations}\n"
            f"{thought_line}"
            f"Describe ONLY what {character.name} does this turn. "
            "Their actions should be influenced by their thought and motivations. "
            "Keep it concise (under 100 words). "
            "Use game commands (ROLL, DAMAGE, HEAL, NPC) as needed. "
            "Do NOT describe what other characters do."
        )

    # ------------------------------------------------------------------
    # Async event generator for web UI
    # ------------------------------------------------------------------

    async def get_response_events(self, player_action: str):
        """Async generator that yields structured event dicts for a web UI.

        Turn-based flow: each character gets their own turn with optional
        thinking (NPCs only) followed by a streamed action narration.

        Events:
            {"type": "loading"}
            {"type": "turn_start", "character": str, "is_player": bool}
            {"type": "thinking", "character": str}
            {"type": "thinking_done", "character": str, "text": str}
            {"type": "token", "text": str}
            {"type": "narrative_replace", "text": str}
            {"type": "narrative_done"}
            {"type": "command", "subtype": str, "text": str}
            {"type": "thought", "character": str, "text": str}
            {"type": "state", "data": dict}
            {"type": "done", "user_turn": int, "assistant_turn": int}
        """
        import asyncio

        context = self.build_context(player_action)
        system_prompt = self.get_system_prompt()

        async def _stream_tokens(sys_prompt, user_msg, history):
            """Run the blocking provider stream in a thread, yield tokens."""
            q: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            def _produce():
                for tok in self.generate_stream(sys_prompt, user_msg, history):
                    loop.call_soon_threadsafe(q.put_nowait, tok)
                loop.call_soon_threadsafe(q.put_nowait, None)  # sentinel

            loop.run_in_executor(None, _produce)

            while True:
                tok = await q.get()
                if tok is None:
                    break
                yield tok

        def _clean_narrative(text: str) -> str:
            """Strip all command lines from narrative text."""
            cleaned = re.sub(
                r"ROLL:\s*.+?\s+(?:strength|dexterity|constitution|intelligence|wisdom|charisma)"
                r"\s+DC\s+\d+\s*\|[^\n]*\n?",
                "",
                text,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(r"DAMAGE:\s*.+?\s+\d+\n?", "", cleaned)
            cleaned = re.sub(r"HEAL:\s*.+?\s+\d+\n?", "", cleaned)
            cleaned = re.sub(r"NPC:\s*[^|]+\|[^|]+\|[^\n]*\n?", "", cleaned)
            cleaned = re.sub(r"THINK:\s*[^|]+\|[^\n]*\n?", "", cleaned)
            return cleaned.strip()

        def _is_player_character(name: str) -> bool:
            """Check if a character name refers to the player."""
            char = self.state.get_character(name)
            return char.is_player if char else False

        # --- Loading indicator ---
        yield {"type": "loading"}

        # --- Determine turn order ---
        turn_order = await asyncio.to_thread(self._get_turn_order, player_action)

        all_cleaned_parts = []
        conversation_for_llm = list(self.conversation)

        # --- Per-character turns ---
        for char_name in turn_order:
            char = self.state.get_character(char_name)
            if not char:
                continue
            is_player = char.is_player

            yield {"type": "turn_start", "character": char_name, "is_player": is_player}

            # NPC thinking phase
            thought = None
            if not is_player:
                yield {"type": "thinking", "character": char_name}
                thought = await asyncio.to_thread(self._get_character_thought, char, context)
                yield {"type": "thinking_done", "character": char_name, "text": thought}

            # Action narration (streaming)
            turn_prompt = self._build_character_turn_prompt(char, player_action, thought)

            full_tokens: list[str] = []
            async for token in _stream_tokens(system_prompt, turn_prompt, conversation_for_llm):
                full_tokens.append(token)
                yield {"type": "token", "text": token}

            response = "".join(full_tokens)
            cleaned = _clean_narrative(response)
            yield {"type": "narrative_replace", "text": cleaned}
            yield {"type": "narrative_done"}
            all_cleaned_parts.append(cleaned)

            # Parse and execute commands
            turn_had_npc = False
            _, commands = self.parse_commands(response)
            if commands:
                command_results = self.execute_commands(commands)
                has_rolls = any(cmd["type"] == "roll" for cmd in commands)
                turn_had_npc = any(c["type"] == "npc" for c in commands)

                for result, cmd in zip(command_results, commands):
                    if cmd["type"] == "thought":
                        if not _is_player_character(cmd["character"]):
                            yield {
                                "type": "thought",
                                "character": cmd["character"],
                                "text": cmd["text"],
                            }
                    else:
                        yield {"type": "command", "subtype": cmd["type"], "text": result}

                # Handle dice roll follow-ups within the character's turn
                if has_rolls:
                    roll_results = [
                        r for r, c in zip(command_results, commands) if c["type"] == "roll"
                    ]
                    results_text = (
                        "DICE ROLL RESULTS:\n" + "\n".join(roll_results) + "\n\n"
                        f"Based on these results, describe what happens next for "
                        f"{char_name} only. Keep it concise."
                    )

                    full_tokens = []
                    async for token in _stream_tokens(
                        system_prompt, results_text, conversation_for_llm
                    ):
                        full_tokens.append(token)
                        yield {"type": "token", "text": token}

                    follow_up = "".join(full_tokens)
                    cleaned_follow = _clean_narrative(follow_up)
                    yield {"type": "narrative_replace", "text": cleaned_follow}
                    yield {"type": "narrative_done"}
                    all_cleaned_parts.append(cleaned_follow)

                    # Execute any commands from follow-up
                    _, follow_commands = self.parse_commands(follow_up)
                    if follow_commands:
                        follow_results = self.execute_commands(follow_commands)
                        turn_had_npc = turn_had_npc or any(
                            c["type"] == "npc" for c in follow_commands
                        )
                        for result, cmd in zip(follow_results, follow_commands):
                            if cmd["type"] != "thought":
                                yield {
                                    "type": "command",
                                    "subtype": cmd["type"],
                                    "text": result,
                                }

            # Per-turn NPC follow-up: catch named NPCs the LLM forgot to tag
            if not turn_had_npc:
                followup_prompt = self._npc_followup_prompt(response)
                followup_resp = await asyncio.to_thread(
                    self.generate_sync, system_prompt, followup_prompt, conversation_for_llm
                )
                _, npc_commands = self.parse_commands(followup_resp)
                npc_commands = [c for c in npc_commands if c["type"] == "npc"]
                if npc_commands:
                    npc_results = self.execute_commands(npc_commands)
                    for result in npc_results:
                        yield {"type": "command", "subtype": "npc", "text": result}

            # Update conversation context for subsequent characters
            conversation_for_llm.append({"role": "user", "content": turn_prompt})
            conversation_for_llm.append({"role": "assistant", "content": response})

        # --- Finalize ---
        self.state.add_to_history(player_action)
        self.conversation.extend(conversation_for_llm[len(self.conversation) :])
        if len(self.conversation) > 20:
            self.conversation = self.conversation[-20:]

        user_turn_index = len(self.turns)
        self.turns.append({"role": "user", "content": player_action})
        assistant_turn_index = len(self.turns)
        self.turns.append({"role": "assistant", "content": "\n\n".join(all_cleaned_parts)})

        yield {
            "type": "state",
            "data": {
                "characters": {
                    name: char.to_dict() for name, char in self.state.characters.items()
                },
                "location": self.state.current_location,
                "in_combat": self.state.in_combat,
            },
        }
        yield {
            "type": "done",
            "user_turn": user_turn_index,
            "assistant_turn": assistant_turn_index,
        }

    def truncate_to_turn(self, turn_index: int):
        """Truncate turns list to keep entries up to (but not including) turn_index.

        Also rebuilds self.conversation from the remaining turns.
        """
        self.turns = self.turns[:turn_index]
        # Rebuild conversation from turns
        self.conversation = [{"role": t["role"], "content": t["content"]} for t in self.turns]

    def edit_turn(self, turn_index: int, new_text: str):
        """Edit the content of a specific turn entry and truncate everything after.

        Also rebuilds self.conversation.
        """
        if 0 <= turn_index < len(self.turns):
            self.turns[turn_index]["content"] = new_text
            self.turns = self.turns[: turn_index + 1]
            self.conversation = [{"role": t["role"], "content": t["content"]} for t in self.turns]
