"""
LLM Provider abstraction layer — Ollama-only (via native HTTP API).

No external SDK required; uses urllib from the standard library.
"""

from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Optional
import json
import urllib.request
import urllib.error


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    def generate(self, system_prompt: str, user_message: str,
                 conversation_history: Optional[List[Dict]] = None) -> str:
        pass

    def generate_stream(self, system_prompt: str, user_message: str,
                         conversation_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        """Yield response tokens as they are generated. Default: yield full response at once."""
        yield self.generate(system_prompt, user_message, conversation_history)

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class OllamaProvider(LLMProvider):
    """Ollama provider using the native /api/chat HTTP endpoint.

    Talks directly to the Ollama server — no openai or other SDK needed.
    """

    def __init__(self, host: str = "http://localhost:11434",
                 model: str = "qwen3.5:9b-q8_0", max_tokens: int = 1000):
        self.host = host.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens

    # -- internal helpers ---------------------------------------------------

    def _build_messages(self, system_prompt: str, user_message: str,
                        conversation_history: Optional[List[Dict]] = None) -> List[Dict]:
        messages: List[Dict] = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def _post(self, path: str, body: dict, *, stream: bool = False):
        """Low-level POST to Ollama, returns the http.client.HTTPResponse."""
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self.host}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return urllib.request.urlopen(req)

    # -- LLMProvider interface ----------------------------------------------

    def generate(self, system_prompt: str, user_message: str,
                 conversation_history: Optional[List[Dict]] = None) -> str:
        body = {
            "model": self.model,
            "messages": self._build_messages(system_prompt, user_message, conversation_history),
            "stream": False,
            "options": {"num_predict": self.max_tokens},
        }
        try:
            with self._post("/api/chat", body) as resp:
                result = json.loads(resp.read())
                return result["message"]["content"]
        except urllib.error.URLError as e:
            return f"[Ollama not reachable at {self.host} — is it running?] ({e.reason})"
        except Exception as e:
            return f"[Error calling Ollama: {e}]"

    def generate_stream(self, system_prompt: str, user_message: str,
                         conversation_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        body = {
            "model": self.model,
            "messages": self._build_messages(system_prompt, user_message, conversation_history),
            "stream": True,
            "options": {"num_predict": self.max_tokens},
        }
        try:
            resp = self._post("/api/chat", body, stream=True)
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

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_name(self) -> str:
        return f"Ollama ({self.model} @ {self.host})"


class MockProvider(LLMProvider):
    """Mock provider for testing without an actual LLM"""

    def generate(self, system_prompt: str, user_message: str,
                 conversation_history: Optional[List[Dict]] = None) -> str:
        return f"""[Mock DM Response]

You: {user_message}

The mock DM would respond here. This is useful for testing the game mechanics
without needing an actual LLM API.

To test dice rolling, the DM might say:
ROLL: TestCharacter strength DC 10 | lifting a rock

Or create an NPC:
NPC: Guard | A stern-looking guard | Protect the gate

Configure a real LLM provider to get actual responses."""

    def is_available(self) -> bool:
        return True

    def get_name(self) -> str:
        return "Mock Provider (Testing)"


# Provider factory
def create_provider(provider_type: str, **kwargs) -> LLMProvider:
    """
    Factory function to create LLM providers.

    Args:
        provider_type: 'ollama' or 'mock'
        **kwargs: Provider-specific arguments
    """
    providers = {
        'ollama': OllamaProvider,
        'mock': MockProvider,
    }

    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_type}. Choose from: {list(providers.keys())}")

    return provider_class(**kwargs)
