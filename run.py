#!/usr/bin/env python3
"""
AI Dungeon Master - Main Entry Point
Quick start with config file defaults for instant startup

Usage:
    python run.py              # Play with config.ini defaults
    python run.py --setup      # Set up Ollama + pull model, then play
    python run.py --setup -m qwen3.5:9b-q8_0   # Specify model
"""

import argparse
import sys

from aidm.config import load_config, create_provider_from_config, get_default_provider
from aidm.dm import UniversalDM


def main():
    """Fast startup using config file default"""
    parser = argparse.ArgumentParser(description="AI Dungeon Master")
    parser.add_argument(
        "--setup", action="store_true",
        help="Run Ollama setup (check/start server, pull model, update config) before playing",
    )
    parser.add_argument(
        "--model", "-m", default=None,
        help="Ollama model to pull during --setup (default: qwen3.5:9b-q8_0)",
    )
    args = parser.parse_args()

    if args.setup:
        from aidm.setup import run_setup, DEFAULT_MODEL
        model = args.model or DEFAULT_MODEL
        success = run_setup(model=model, launch=False)
        if not success:
            sys.exit(1)
        print()  # blank line before game starts

    # Load config
    config = load_config()
    
    if not config:
        print("Warning: config.ini not found!")
        print("Copy config.ini.example to config.ini and configure your preferred provider.")
        print("Using mock provider for now...\n")
    
    # Get default provider from config
    provider_name = get_default_provider(config)
    
    # Create provider
    provider = create_provider_from_config(config, provider_name) if config else create_provider_from_config(None, 'mock')
    
    # Create and run DM
    dm = UniversalDM(provider)
    dm.run()


if __name__ == "__main__":
    main()
