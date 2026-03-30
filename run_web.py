#!/usr/bin/env python3
"""
AI Dungeon Master — Web UI Entry Point

Usage:
    python run_web.py                # Start on http://localhost:8000
    python run_web.py --port 3000    # Custom port
"""

import argparse

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="AI Dungeon Master — Web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    args = parser.parse_args()

    print(f"Starting AI Dungeon Master web UI at http://{args.host}:{args.port}")
    uvicorn.run("aidm.web:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
