"""
Configuration management for AI Dungeon Master
"""

import configparser
import os
from typing import Optional
from .llm_providers import create_provider, LLMProvider, OpenAIProvider


def load_config(config_file: str = 'config.ini') -> Optional[configparser.ConfigParser]:
    """Load configuration from file"""
    config = configparser.ConfigParser()
    
    if os.path.exists(config_file):
        config.read(config_file)
        return config
    
    return None


def create_provider_from_config(config: Optional[configparser.ConfigParser], provider_name: str) -> LLMProvider:
    """Create a provider based on config file settings"""
    if config is None:
        return create_provider('mock')

    if provider_name == 'claude':
        return create_provider(
            'claude',
            api_key=config.get('claude', 'api_key', fallback=None),
            model=config.get('claude', 'model', fallback='claude-sonnet-4-20250514'),
            max_tokens=config.getint('claude', 'max_tokens', fallback=1000),
        )
    
    elif provider_name == 'openai':
        return create_provider(
            'openai',
            api_key=config.get('openai', 'api_key', fallback=None),
            model=config.get('openai', 'model', fallback='gpt-4'),
            max_tokens=config.getint('openai', 'max_tokens', fallback=1000),
        )
    
    elif provider_name == 'ollama':
        host = config.get('ollama', 'host', fallback='http://localhost:11434')
        return OpenAIProvider(
            base_url=f"{host.rstrip('/')}/v1",
            api_key="ollama",
            model=config.get('ollama', 'model', fallback='llama2'),
            max_tokens=config.getint('ollama', 'max_tokens', fallback=1000),
        )
    
    elif provider_name == 'lmstudio':
        host = config.get('lmstudio', 'host', fallback='http://localhost:1234')
        return OpenAIProvider(
            base_url=f"{host.rstrip('/')}/v1",
            api_key="lm-studio",
            model=config.get('lmstudio', 'model', fallback='local-model'),
            max_tokens=config.getint('lmstudio', 'max_tokens', fallback=1000),
        )
    
    else:  # mock or fallback
        return create_provider('mock')


def get_save_file(config: Optional[configparser.ConfigParser] = None) -> str:
    """Get the save file path from config or default"""
    if config and config.has_option('game', 'save_file'):
        return config.get('game', 'save_file')
    return 'gamestate.json'


def get_default_provider(config: Optional[configparser.ConfigParser] = None) -> str:
    """Get the default provider name from config"""
    if config and config.has_option('DEFAULT', 'default_provider'):
        return config.get('DEFAULT', 'default_provider')
    return 'mock'
