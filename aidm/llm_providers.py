"""
LLM Provider abstraction layer
Allows switching between Claude, OpenAI, local models, etc.
"""

from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Optional
import os


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def generate(self, system_prompt: str, user_message: str, 
                 conversation_history: Optional[List[Dict]] = None) -> str:
        """
        Generate a response from the LLM
        
        Args:
            system_prompt: System instructions for the LLM
            user_message: The user's message
            conversation_history: Optional list of previous messages
            
        Returns:
            The LLM's response as a string
        """
        pass
    
    def generate_stream(self, system_prompt: str, user_message: str,
                         conversation_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        """Yield response tokens as they are generated. Default: yield full response at once."""
        yield self.generate(system_prompt, user_message, conversation_history)

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and available"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the name of this provider"""
        pass


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.model = model
        self.client = None
        self._client_initialized = False
        
    def _ensure_client(self):
        """Lazy initialization of client"""
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
            # Build messages from history if provided
            messages = []
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_message})
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
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
    """OpenAI API provider (GPT-4, GPT-3.5, etc.)"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        self.model = model
        self.client = None
        self._client_initialized = False
        
    def _ensure_client(self):
        """Lazy initialization of client"""
        if not self._client_initialized:
            self._client_initialized = True
            if self.api_key:
                try:
                    import openai
                    self.client = openai.OpenAI(api_key=self.api_key)
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
            # Build messages
            messages = [{"role": "system", "content": system_prompt}]
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_message})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error calling OpenAI API: {e}"
    
    def is_available(self) -> bool:
        return self.client is not None
    
    def get_name(self) -> str:
        return f"OpenAI ({self.model})"


class OllamaProvider(LLMProvider):
    """Local Ollama provider for running models locally"""
    
    def __init__(self, model: str = "llama2", host: str = "http://localhost:11434",
                 num_ctx: int = 4096):
        self.model = model
        self.host = host
        self.num_ctx = num_ctx
        self._available = None

    def _build_messages(self, system_prompt: str, user_message: str,
                        conversation_history: Optional[List[Dict]] = None) -> List[Dict]:
        """Build structured messages list for /api/chat."""
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        return messages
        
    def generate(self, system_prompt: str, user_message: str, 
                 conversation_history: Optional[List[Dict]] = None) -> str:
        try:
            import requests
            
            messages = self._build_messages(system_prompt, user_message, conversation_history)
            
            response = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_ctx": self.num_ctx,
                        "num_predict": 1000,
                    },
                },
                timeout=300
            )
            
            if response.status_code == 200:
                return response.json()['message']['content']
            else:
                return f"Ollama error: {response.status_code}"
                
        except ImportError:
            return "[requests package not installed. Run: pip install requests]"
        except Exception as e:
            return f"Error calling Ollama: {e}"
    
    def is_available(self) -> bool:
        # Only check if explicitly requested, not during init
        if self._available is not None:
            return self._available
            
        # Return True by default for faster startup - will fail gracefully in generate() if not available
        return True
    
    def check_connection(self) -> bool:
        """Explicitly check if Ollama is available"""
        try:
            import requests
            response = requests.get(f"{self.host}/api/tags", timeout=2)
            self._available = response.status_code == 200
            return self._available
        except:
            self._available = False
            return False
    
    def generate_stream(self, system_prompt: str, user_message: str,
                         conversation_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        try:
            import requests
            import json as _json

            messages = self._build_messages(system_prompt, user_message, conversation_history)

            resp = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "think": False,
                    "options": {
                        "num_ctx": self.num_ctx,
                        "num_predict": 1000,
                    },
                },
                stream=True,
                timeout=300,
            )
            if resp.status_code != 200:
                yield f"Ollama error: {resp.status_code}"
                return

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = _json.loads(line)
                except ValueError:
                    continue
                token = data.get("message", {}).get("content", "")
                if token:
                    yield token
                if data.get("done"):
                    break

        except ImportError:
            yield "[requests package not installed. Run: pip install requests]"
        except Exception as e:
            yield f"Error calling Ollama: {e}"

    def get_name(self) -> str:
        return f"Ollama ({self.model})"


class LMStudioProvider(LLMProvider):
    """LM Studio local provider (OpenAI-compatible API)"""
    
    def __init__(self, host: str = "http://localhost:1234", model: str = "local-model"):
        self.host = host
        self.model = model
        self._available = None
        
    def generate(self, system_prompt: str, user_message: str, 
                 conversation_history: Optional[List[Dict]] = None) -> str:
        try:
            import requests
            
            # Build messages
            messages = [{"role": "system", "content": system_prompt}]
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_message})
            
            response = requests.post(
                f"{self.host}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 1000
                },
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                return f"LM Studio error: {response.status_code}"
                
        except ImportError:
            return "[requests package not installed. Run: pip install requests]"
        except Exception as e:
            return f"Error calling LM Studio: {e}"
    
    def is_available(self) -> bool:
        # Only check if explicitly requested, not during init  
        if self._available is not None:
            return self._available
            
        # Return True by default for faster startup - will fail gracefully in generate() if not available
        return True
    
    def check_connection(self) -> bool:
        """Explicitly check if LM Studio is available"""
        try:
            import requests
            response = requests.get(f"{self.host}/v1/models", timeout=2)
            self._available = response.status_code == 200
            return self._available
        except:
            self._available = False
            return False
    
    def generate_stream(self, system_prompt: str, user_message: str,
                         conversation_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        try:
            import requests
            import json as _json

            messages = [{"role": "system", "content": system_prompt}]
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_message})

            resp = requests.post(
                f"{self.host}/v1/chat/completions",
                json={"model": self.model, "messages": messages, "max_tokens": 1000, "stream": True},
                stream=True,
                timeout=300,
            )
            if resp.status_code != 200:
                yield f"LM Studio error: {resp.status_code}"
                return

            for line in resp.iter_lines():
                if not line:
                    continue
                text = line.decode("utf-8", errors="replace")
                if not text.startswith("data: "):
                    continue
                payload = text[len("data: "):]
                if payload.strip() == "[DONE]":
                    break
                try:
                    data = _json.loads(payload)
                except ValueError:
                    continue
                delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    yield delta

        except ImportError:
            yield "[requests package not installed. Run: pip install requests]"
        except Exception as e:
            yield f"Error calling LM Studio: {e}"

    def get_name(self) -> str:
        return f"LM Studio ({self.model})"


class LlamaCppProvider(LLMProvider):
    """Local llama-cpp-python provider for running GGUF models directly"""

    def __init__(self, model_path: str = "models/model.gguf", n_ctx: int = 4096,
                 n_gpu_layers: int = -1, flash_attn: bool = True):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.flash_attn = flash_attn
        self._llm = None

    def _ensure_model(self):
        if self._llm is not None:
            return
        try:
            from llama_cpp import Llama
            self._llm = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                flash_attn=self.flash_attn,
                verbose=False,
            )
        except ImportError:
            raise RuntimeError("llama-cpp-python not installed. Run: pip install llama-cpp-python")
        except Exception as e:
            raise RuntimeError(f"Failed to load model {self.model_path}: {e}")

    def _build_messages(self, system_prompt: str, user_message: str,
                        conversation_history: Optional[List[Dict]] = None) -> List[Dict]:
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def generate(self, system_prompt: str, user_message: str,
                 conversation_history: Optional[List[Dict]] = None) -> str:
        try:
            self._ensure_model()
            messages = self._build_messages(system_prompt, user_message, conversation_history)
            response = self._llm.create_chat_completion(
                messages=messages,
                max_tokens=1000,
            )
            return response["choices"][0]["message"]["content"]
        except RuntimeError as e:
            return f"[llama-cpp error: {e}]"
        except Exception as e:
            return f"Error calling llama-cpp: {e}"

    def generate_stream(self, system_prompt: str, user_message: str,
                         conversation_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        try:
            self._ensure_model()
            messages = self._build_messages(system_prompt, user_message, conversation_history)
            for chunk in self._llm.create_chat_completion(
                messages=messages,
                max_tokens=1000,
                stream=True,
            ):
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    yield delta
        except RuntimeError as e:
            yield f"[llama-cpp error: {e}]"
        except Exception as e:
            yield f"Error calling llama-cpp: {e}"

    def is_available(self) -> bool:
        try:
            import llama_cpp  # noqa: F401
            return os.path.isfile(self.model_path)
        except ImportError:
            return False

    def get_name(self) -> str:
        return f"llama-cpp ({os.path.basename(self.model_path)})"


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
    Factory function to create LLM providers
    
    Args:
        provider_type: Type of provider ('claude', 'openai', 'ollama', 'lmstudio', 'mock')
        **kwargs: Provider-specific arguments
        
    Returns:
        An LLMProvider instance
    """
    providers = {
        'claude': ClaudeProvider,
        'openai': OpenAIProvider,
        'ollama': OllamaProvider,
        'lmstudio': LMStudioProvider,
        'llamacpp': LlamaCppProvider,
        'mock': MockProvider
    }
    
    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_type}. Choose from: {list(providers.keys())}")
    
    return provider_class(**kwargs)


def list_available_providers() -> List[LLMProvider]:
    """Return a list of all potentially available providers (fast check)"""
    # Just return all providers - they'll fail gracefully if not actually available
    return [
        ClaudeProvider(),
        OpenAIProvider(), 
        OllamaProvider(),
        LMStudioProvider(),
        LlamaCppProvider(),
        MockProvider()
    ]


if __name__ == "__main__":
    # Test providers
    print("Testing LLM Providers:\n")
    
    available = list_available_providers()
    print(f"Available providers: {len(available)}")
    for provider in available:
        print(f"  - {provider.get_name()}")
    
    # Test mock provider
    print("\nTesting Mock Provider:")
    mock = MockProvider()
    response = mock.generate(
        "You are a helpful assistant",
        "Hello, how are you?"
    )
    print(response)
