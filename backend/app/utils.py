"""Small shared helpers: ids, timestamps, filename sanitation, formatting."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


def new_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_STEM_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_stem(name: str, max_len: int = 80) -> str:
    """Turn an arbitrary filename into a safe output stem."""
    stem = Path(name or "").stem or "output"
    stem = _STEM_RE.sub("_", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    if not stem:
        stem = "output"
    return stem[:max_len].strip(" .") or "output"


def unique_path(path: Path) -> Path:
    """Return `path`, or `stem (n).ext` for the first free n. Never overwrites."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for i in range(1, 10000):
        cand = path.with_name(f"{stem} ({i}){suffix}")
        if not cand.exists():
            return cand
    raise RuntimeError("Could not allocate a free filename in the output directory")


def human_size(num: float | int | None) -> str:
    if num is None:
        return "-"
    num = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024.0 or unit == "TB":
            return (f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B")
        num /= 1024.0
    return "-"


def fmt_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "-"
    try:
        seconds = int(float(seconds))
    except (TypeError, ValueError):
        return "-"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
