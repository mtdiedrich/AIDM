#!/usr/bin/env python3
"""
Universal AI DM with configuration file support
Run with: python universal_dm_config.py
Or: python universal_dm_config.py --provider claude
"""

import argparse
from aidm.config import load_config, create_provider_from_config, get_default_provider
from aidm.dm import UniversalDM, select_provider


def main():
    parser = argparse.ArgumentParser(description='Universal AI Dungeon Master')
    parser.add_argument('--provider', '-p', 
                       choices=['claude', 'openai', 'ollama', 'lmstudio', 'mock'],
                       help='LLM provider to use')
    parser.add_argument('--config', '-c', default='config.ini',
                       help='Configuration file (default: config.ini)')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Select provider interactively')
    
    args = parser.parse_args()
    
    # Load config
    config = load_config(args.config)
    
    # Determine provider
    if args.interactive:
        # Use interactive selection
        provider = select_provider()
    elif args.provider:
        # Use command line argument
        if config:
            provider = create_provider_from_config(config, args.provider)
        else:
            from aidm.llm_providers import create_provider
            provider = create_provider(args.provider)
    elif config:
        # Use default from config
        provider_name = get_default_provider(config)
        provider = create_provider_from_config(config, provider_name)
    else:
        # Fallback to interactive
        provider = select_provider()
    
    # Create and run DM
    dm = UniversalDM(provider)
    dm.run()


if __name__ == "__main__":
    main()
