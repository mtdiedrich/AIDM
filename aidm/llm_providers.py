"""
LLM Provider abstraction layer
Allows switching between Claude, OpenAI, local models (via Ollama/LM Studio), etc.
"""

from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Optional
import os


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


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514",
                 max_tokens: int = 1000):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.model = model
        self.max_tokens = max_tokens
        self.client = None
        self._client_initialized = False
        
    def _ensure_client(self):
        if not self._client_initialized:
            self._client_initialized = True
            if self.api_key:
                try:
                    import anthropic
                    self.client = anthropic.Anthropic(api_key=self.api_key)
                except ImportError:
                    print("Warning: anthropic package not installed. Run: pip install anthropic")
                except Exception as e:
                    print(f"Warning: Could not initialize Anthropic client: {e}")
    
    def generate(self, system_prompt: str, user_message: str, 
                 conversation_history: Optional[List[Dict]] = None) -> str:
        self._ensure_client()
        if not self.client:
            return "[Claude API not available - check API key and anthropic package]"
        
        try:
            messages = []
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_message})
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=messages
            )
            
            return response.content[0].text
            
        except Exception as e:
            return f"Error calling Claude API: {e}"
    
    def is_available(self) -> bool:
        return self.client is not None
    
    def get_name(self) -> str:
        return f"Claude ({self.model})"


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible API provider.

    Works with OpenAI, Ollama (base_url=http://localhost:11434/v1),
    LM Studio (base_url=http://localhost:1234/v1), and any other
    OpenAI-compatible server.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4",
                 base_url: Optional[str] = None, max_tokens: int = 1000):
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        # When pointing at a local server, no real key is needed
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY') or ("not-needed" if base_url else None)
        self.client = None
        self._client_initialized = False
        
    def _ensure_client(self):
        if not self._client_initialized:
            self._client_initialized = True
            if self.api_key:
                try:
                    import openai
                    kwargs: dict = {"api_key": self.api_key}
                    if self.base_url:
                        kwargs["base_url"] = self.base_url
                    self.client = openai.OpenAI(**kwargs)
                except ImportError:
                    print("Warning: openai package not installed. Run: pip install openai")
                except Exception as e:
                    print(f"Warning: Could not initialize OpenAI client: {e}")
    
    def generate(self, system_prompt: str, user_message: str, 
                 conversation_history: Optional[List[Dict]] = None) -> str:
        self._ensure_client()
        if not self.client:
            return "[OpenAI API not available - check API key and openai package]"
        
        try:
            messages = [{"role": "system", "content": system_prompt}]
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_message})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error calling OpenAI API: {e}"

    def generate_stream(self, system_prompt: str, user_message: str,
                         conversation_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        self._ensure_client()
        if not self.client:
            yield "[OpenAI API not available - check API key and openai package]"
            return

        try:
            messages = [{"role": "system", "content": system_prompt}]
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_message})

            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices[0].delta else None
                if delta:
                    yield delta

        except Exception as e:
            yield f"Error calling OpenAI API: {e}"

    def is_available(self) -> bool:
        return self.client is not None
    
    def get_name(self) -> str:
        if self.base_url:
            return f"OpenAI-compat ({self.model} @ {self.base_url})"
        return f"OpenAI ({self.model})"


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
        provider_type: 'claude', 'openai', or 'mock'
        **kwargs: Provider-specific arguments
    """
    providers = {
        'claude': ClaudeProvider,
        'openai': OpenAIProvider,
        'mock': MockProvider
    }
    
    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_type}. Choose from: {list(providers.keys())}")
    
    return provider_class(**kwargs)
