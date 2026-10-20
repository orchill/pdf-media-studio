#!/usr/bin/env python3
"""Launcher for PDF & Media Studio.

Usage:
  python run.py [--host 127.0.0.1] [--port 8756] [--no-browser]

Reads config.json for defaults; CLI flags override. Binds to 127.0.0.1
unless explicitly told otherwise.
"""
from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF & Media Studio launcher")
    parser.add_argument("--host", default=None, help="bind address (default: config, 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="port (default: config, 8756)")
    parser.add_argument("--no-browser", action="store_true", help="do not open the web browser")
    args = parser.parse_args()

    from backend.app.config import get_config
    cfg = get_config()
    host = args.host or cfg.get("host")
    port = args.port or int(cfg.get("port"))
    url = f"http://{'localhost' if host in ('127.0.0.1',) else host}:{port}"

    print("=" * 62)
    print("  PDF & Media Studio")
    print(f"  URL          : {url}")
    print(f"  Output folder: {cfg.output_dir}")
    print("  Press Ctrl+C to stop. Do not close this window while downloading.")
    print("=" * 62)

    open_browser = (not args.no_browser) and bool(cfg.get("open_browser", True))
    if open_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    import uvicorn
    uvicorn.run("backend.app.main:app", host=host, port=port, log_level="info", workers=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
