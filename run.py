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

# import name -> pip package name (shown in the error message)
REQUIRED_MODULES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "multipart": "python-multipart",
    "pydantic": "pydantic",
    "fitz": "PyMuPDF",
    "pypdf": "pypdf",
    "PIL": "Pillow",
}

# Needed only for the media tab; the app runs and reports it as missing
# in the UI (System page) when absent.
OPTIONAL_MODULES = {
    "yt_dlp": "yt-dlp",
}


def _not_importable(modules: dict[str, str]) -> list[str]:
    missing = []
    for module, package in modules.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    return missing


def main() -> int:
    missing = _not_importable(REQUIRED_MODULES)
    if missing:
        print("=" * 62)
        print("  Missing Python packages:")
        for pkg in missing:
            print(f"    - {pkg}")
        print()
        print("  Fix (recommended): run scripts\\setup.bat once, then start")
        print("  the app with scripts\\start.bat (uses an isolated .venv).")
        print()
        print("  Or install into the current Python:")
        print(f"    {Path(sys.executable).name} -m pip install -r requirements.txt")
        print("=" * 62)
        return 1

    opt_missing = _not_importable(OPTIONAL_MODULES)
    if opt_missing:
        print("[warn] Missing optional packages: " + ", ".join(opt_missing))
        print("       The app will start, but media downloads stay disabled")
        print("       until you install them (see the System page in the UI).")

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
