"""Application configuration.

Settings live in ``config.json`` at the project root (auto-created with
defaults on first run) and can be overridden with the ``PDFMEDIA_CONFIG``
environment variable pointing at an alternative config file.

Relative ``output_dir`` / ``data_dir`` values are resolved against the
project root. Absolute paths are allowed.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]

# Browsers yt-dlp can extract cookies from (--cookies-from-browser).
COOKIE_BROWSERS = ("brave", "chrome", "chromium", "edge", "firefox",
                   "opera", "safari", "vivaldi", "whale")
COOKIE_SOURCES = ("none", "file", "browser")

DEFAULTS: dict[str, Any] = {
    "host": "127.0.0.1",
    "port": 8756,
    "output_dir": "outputs",
    "data_dir": "data",
    "ffmpeg_path": "",
    "ytdlp_path": "",
    "cookie_source": "none",   # none | file | browser
    "cookie_browser": "",      # e.g. "chrome" when cookie_source == "browser"
    "max_upload_mb": 512,
    "max_download_gb": 2,
    "max_duration_hours": 4,
    "max_concurrent_tasks": 3,
    "history_limit": 100,
    "open_browser": True,
}

# Keys the UI may edit at runtime. host/port/data_dir require a restart.
EDITABLE_KEYS = {
    "output_dir", "ffmpeg_path", "ytdlp_path", "max_upload_mb",
    "max_download_gb", "max_duration_hours", "max_concurrent_tasks",
    "history_limit", "open_browser", "port", "host",
}
RESTART_KEYS = {"port", "host", "data_dir"}

_INT_LIMITS = {
    "port": (1, 65535),
    "max_upload_mb": (1, 8192),
    "max_download_gb": (0, 100),      # 0 = unlimited
    "max_duration_hours": (0, 48),    # 0 = unlimited
    "max_concurrent_tasks": (1, 8),
    "history_limit": (5, 1000),
}


class ConfigError(ValueError):
    pass


class Config:
    def __init__(self, path: Path):
        self.path = path
        self._d: dict[str, Any] = dict(DEFAULTS)
        self._lock = threading.Lock()
        self.load()

    # ------------------------------------------------------------- loading
    def load(self) -> None:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"[warn] {self.path.name} is unreadable ({exc.__class__.__name__}: "
                      f"{exc}) - using default settings", file=sys.stderr)
                raw = {}
            if isinstance(raw, dict):
                for key in DEFAULTS:
                    if key in raw:
                        self._d[key] = raw[key]
        self._validate()

    def _validate(self) -> None:
        for key, (lo, hi) in _INT_LIMITS.items():
            try:
                val = int(self._d[key])
            except (TypeError, ValueError):
                val = DEFAULTS[key]
            self._d[key] = max(lo, min(hi, val))
        if self._d["host"] not in ("127.0.0.1", "localhost", "0.0.0.0"):
            self._d["host"] = "127.0.0.1"

    # ----------------------------------------------------------- resolved
    @property
    def output_dir(self) -> Path:
        p = Path(str(self._d["output_dir"]))
        return p if p.is_absolute() else BASE_DIR / p

    @property
    def data_dir(self) -> Path:
        p = Path(str(self._d["data_dir"]))
        return p if p.is_absolute() else BASE_DIR / p

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def thumbs_dir(self) -> Path:
        return self.data_dir / "thumbs"

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def history_path(self) -> Path:
        return self.data_dir / "history.json"

    @property
    def cookies_path(self) -> Path:
        """Netscape cookies.txt used for site sign-in (sensitive, 0600)."""
        return self.data_dir / "cookies.txt"

    @property
    def max_upload_bytes(self) -> int:
        return int(self._d["max_upload_mb"]) * 1024 * 1024

    def ensure_dirs(self) -> None:
        for d in (self.output_dir, self.uploads_dir, self.thumbs_dir,
                  self.tmp_dir, self.logs_dir, self.data_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- access
    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        d = dict(self._d)
        d["output_dir"] = str(self.output_dir)
        d["data_dir"] = str(self.data_dir)
        return d

    def public_dict(self) -> dict[str, Any]:
        """Config exposed to the UI (absolute paths resolved for display)."""
        return self.as_dict()

    # ------------------------------------------------------------- update
    def update(self, patch: dict[str, Any]) -> list[str]:
        """Validate + apply a settings patch. Returns keys needing restart."""
        with self._lock:
            new = dict(self._d)
            for key, value in (patch or {}).items():
                if key not in EDITABLE_KEYS:
                    raise ConfigError(f"Unknown or read-only setting: {key}")
                if key in _INT_LIMITS:
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        raise ConfigError(f"{key} must be an integer")
                    lo, hi = _INT_LIMITS[key]
                    if not (lo <= value <= hi):
                        raise ConfigError(f"{key} must be between {lo} and {hi}")
                elif key in ("open_browser",):
                    value = bool(value)
                elif key in ("output_dir", "ffmpeg_path", "ytdlp_path"):
                    value = "" if value is None else str(value).strip()
                    if key == "output_dir":
                        if not value:
                            raise ConfigError("output_dir cannot be empty")
                        p = Path(value)
                        if not p.is_absolute():
                            p = BASE_DIR / p
                        try:
                            p.mkdir(parents=True, exist_ok=True)
                            if not p.is_dir():
                                raise NotADirectoryError()
                        except Exception as exc:
                            raise ConfigError(f"Cannot use output_dir '{value}': {exc}")
                        value = str(p)
                new[key] = value
            self._d = new
            self._validate()
            self.save()
            return sorted(set(patch or {}) & RESTART_KEYS)

    def set_cookie_prefs(self, source: str, browser: str = "") -> None:
        """Validate and persist cookie sign-in preferences (via dedicated API).

        Deliberately NOT reachable through the generic settings PATCH so the
        cookie file and browser value are always validated together.
        """
        if source not in COOKIE_SOURCES:
            raise ConfigError(f"cookie source must be one of {', '.join(COOKIE_SOURCES)}")
        if source == "browser":
            browser = (browser or "").strip().lower()
            if browser not in COOKIE_BROWSERS:
                raise ConfigError(
                    f"Unsupported browser '{browser}'. Supported: "
                    f"{', '.join(COOKIE_BROWSERS)}")
        else:
            browser = ""
        with self._lock:
            self._d["cookie_source"] = source
            self._d["cookie_browser"] = browser
            self.save()

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._d, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass  # config persistence is best-effort; runtime keeps working


_config: Config | None = None
_config_lock = threading.Lock()


def get_config() -> Config:
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                cfg_path = os.environ.get("PDFMEDIA_CONFIG", str(BASE_DIR / "config.json"))
                _config = Config(Path(cfg_path))
    return _config
