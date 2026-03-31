#!/usr/bin/env python3
"""
AI Dungeon Master — Entry Point

Usage:
    python run.py                          # Start web UI on http://localhost:8000
    python run.py -m anubis                # Use model alias from config [models]
    python run.py -m llama3:8b             # Use an arbitrary Ollama model name
    python run.py --port 3000              # Custom port
    python run.py --setup                  # Set up Ollama first, then start
    python run.py --setup -m qwen3.5:9b-q8_0
    python run.py --setup --gguf https://huggingface.co/.../model-Q8_0.gguf
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
        help="Model alias (from config [models]) or full Ollama model name",
    )
    parser.add_argument(
        "--gguf", default=None,
        help="HuggingFace GGUF URL to download and import into Ollama (use with --setup)",
    )
    args = parser.parse_args()

    if args.gguf and not args.setup:
        print("Error: --gguf requires --setup.")
        sys.exit(1)

    if args.setup:
        from aidm.setup import run_setup, DEFAULT_MODEL
        if args.gguf and args.model:
            print("Error: --gguf and --model are mutually exclusive.")
            sys.exit(1)
        model = args.model or DEFAULT_MODEL
        if not run_setup(model=model, gguf_url=args.gguf):
            sys.exit(1)
        print()

    # Pass model override to web module before uvicorn imports it
    if args.model:
        import aidm.web
        aidm.web.model_override = args.model

    print(f"Starting AI Dungeon Master at http://{args.host}:{args.port}")
    uvicorn.run("aidm.web:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
