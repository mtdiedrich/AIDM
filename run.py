#!/usr/bin/env python3
"""
AI Dungeon Master — Entry Point

Usage:
    python run.py                          # Start web UI on http://localhost:8000
    python run.py --port 3000              # Custom port
    python run.py --setup                  # Set up Ollama first, then start
    python run.py --setup -m qwen3.5:9b-q8_0
"""

import argparse
import sys

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="AI Dungeon Master")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument(
        "--setup", action="store_true",
        help="Run Ollama setup (check/start server, pull model, update config) before starting",
    )
    parser.add_argument(
        "--model", "-m", default=None,
        help="Ollama model to pull during --setup (default: qwen3.5:9b-q8_0)",
    )
    args = parser.parse_args()

    if args.setup:
        from aidm.setup import run_setup, DEFAULT_MODEL
        model = args.model or DEFAULT_MODEL
        if not run_setup(model=model):
            sys.exit(1)
        print()

    print(f"Starting AI Dungeon Master at http://{args.host}:{args.port}")
    uvicorn.run("aidm.web:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
